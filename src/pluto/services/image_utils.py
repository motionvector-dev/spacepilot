"""Image parsing, dimensions detection, and upload sanitization utilities."""

import re
import math
import struct
from pathlib import Path
from typing import Optional

MAX_IMAGE_SIZE = 25 * 1024 * 1024  # 25MB limit
ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


def sanitize_upload_filename(filename: str, fallback_ext: str = ".png") -> str:
    """Sanitize filename to prevent directory traversal and remove unsafe chars."""
    if not filename:
        clean = "upload"
    else:
        normalized = filename.replace("\\", "/").replace("\x00", "")
        clean = normalized.split("/")[-1]
        clean = clean.replace("..", "")
        clean = re.sub(r"[^A-Za-z0-9_.-]", "_", clean)
        while ".." in clean:
            clean = clean.replace("..", "_")
        clean = clean.strip(". _-")
        if not clean:
            clean = "upload"
    ext = Path(clean).suffix.lower()
    if not ext:
        ext = fallback_ext
        clean = f"{clean}{ext}"
    return clean


def parse_image_dimensions_fallback(content: bytes) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """Header parsing fallback for PNG, JPEG, GIF, WEBP."""
    if len(content) < 16:
        return None, None, None

    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        w, h = struct.unpack(">II", content[16:24])
        return w, h, "image/png"

    # GIF: GIF87a or GIF89a
    if content.startswith((b"GIF87a", b"GIF89a")) and len(content) >= 10:
        w, h = struct.unpack("<HH", content[6:10])
        return w, h, "image/gif"

    # WEBP: RIFF....WEBP
    if content.startswith(b"RIFF") and len(content) >= 30 and content[8:12] == b"WEBP":
        vp8 = content[12:16]
        if vp8 == b"VP8 " and len(content) >= 30:
            w = struct.unpack("<H", content[26:28])[0] & 0x3FFF
            h = struct.unpack("<H", content[28:30])[0] & 0x3FFF
            return w, h, "image/webp"
        elif vp8 == b"VP8L" and len(content) >= 25:
            b0, b1, b2, b3 = content[21:25]
            w = 1 + (((b1 & 0x3F) << 8) | b0)
            h = 1 + (((content[25] & 0x0F) << 10) | (b3 << 2) | ((b2 & 0xC0) >> 6))
            return w, h, "image/webp"
        elif vp8 == b"VP8X" and len(content) >= 30:
            w = 1 + struct.unpack("<I", content[24:27] + b"\x00")[0]
            h = 1 + struct.unpack("<I", content[27:30] + b"\x00")[0]
            return w, h, "image/webp"
        return None, None, "image/webp"

    # JPEG: FF D8 FF
    if content.startswith(b"\xff\xd8\xff"):
        idx = 2
        while idx < len(content) - 8:
            if content[idx] != 0xFF:
                idx += 1
                continue
            marker = content[idx + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", content[idx + 5:idx + 9])
                return w, h, "image/jpeg"
            else:
                length = struct.unpack(">H", content[idx + 2:idx + 4])[0]
                idx += 2 + length
        return None, None, "image/jpeg"

    return None, None, None


def get_image_info(content: bytes) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """Get dimensions and MIME type using PIL, falling back to header parsing."""
    width, height, mime = None, None, None
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(content)) as img:
            width, height = img.size
            fmt = (img.format or "").upper()
            fmt_map = {
                "PNG": "image/png",
                "JPEG": "image/jpeg",
                "JPG": "image/jpeg",
                "WEBP": "image/webp",
                "GIF": "image/gif",
            }
            mime = fmt_map.get(fmt)
    except Exception:
        pass

    if width is None or height is None or mime is None:
        fb_w, fb_h, fb_mime = parse_image_dimensions_fallback(content)
        width = width or fb_w
        height = height or fb_h
        mime = mime or fb_mime

    return width, height, mime


def get_aspect_ratio_str(width: int, height: int) -> str:
    """Determine aspect ratio string ('16:9', '9:16', '1:1', '4:3', etc.)."""
    if not width or not height or width <= 0 or height <= 0:
        return "16:9"
    ratio = width / height
    known = [
        ("16:9", 16 / 9),
        ("9:16", 9 / 16),
        ("1:1", 1.0),
        ("4:3", 4 / 3),
        ("3:4", 3 / 4),
        ("3:2", 3 / 2),
        ("2:3", 2 / 3),
        ("21:9", 21 / 9),
        ("9:21", 9 / 21),
        ("4:5", 4 / 5),
        ("5:4", 5 / 4),
    ]
    best_name, best_val = min(known, key=lambda x: abs(ratio - x[1]))
    if abs(ratio - best_val) / best_val < 0.05:
        return best_name
    g = math.gcd(width, height)
    sw, sh = width // g, height // g
    if sw <= 32 and sh <= 32:
        return f"{sw}:{sh}"
    return f"{width}:{height}"


def parse_multipart_form_data(body: bytes, content_type_header: str) -> tuple[Optional[bytes], str, Optional[str]]:
    """Parse multipart/form-data using standard library without external dependencies."""
    boundary = None
    for part in content_type_header.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("boundary=", 1)[1].strip('"\'')
            break

    if not boundary:
        if body.startswith(b"--"):
            first_line = body.split(b"\r\n", 1)[0] if b"\r\n" in body else body.split(b"\n", 1)[0]
            boundary = first_line.lstrip(b"-").decode("utf-8", errors="replace").strip()
        else:
            return None, "upload.png", None

    boundary_bytes = f"--{boundary}".encode()
    sections = body.split(boundary_bytes)

    for section in sections:
        if not section or section in (b"--", b"--\r\n", b"\r\n", b"--\n", b"\n"):
            continue
        if section.startswith(b"\r\n"):
            section = section[2:]
        elif section.startswith(b"\n"):
            section = section[1:]

        if section.endswith(b"\r\n--"):
            section = section[:-4]
        elif section.endswith(b"\r\n"):
            section = section[:-2]
        elif section.endswith(b"\n--"):
            section = section[:-3]
        elif section.endswith(b"\n"):
            section = section[:-1]

        if b"\r\n\r\n" in section:
            headers_raw, content_part = section.split(b"\r\n\r\n", 1)
        elif b"\n\n" in section:
            headers_raw, content_part = section.split(b"\n\n", 1)
        else:
            continue

        headers_text = headers_raw.decode("utf-8", errors="replace")
        filename = "upload.png"
        content_type = None

        for line in headers_text.splitlines():
            line_lower = line.lower()
            if line_lower.startswith("content-disposition:"):
                fn_match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)["\']?', line, re.IGNORECASE)
                if fn_match:
                    filename = fn_match.group(1).strip()
            elif line_lower.startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip()

        if content_part:
            return content_part, filename, content_type

    return None, "upload.png", None
