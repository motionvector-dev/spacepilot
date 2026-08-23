"""SpacePilot — inference orchestration across the machines you can reach.

This is a placeholder release. It carries the name and reports its own
status honestly; it does not yet carry the product.
"""

__version__ = "0.0.1"

HOMEPAGE = "https://spacepilot.dev"

STATUS = (
    "SpacePilot is under active development and this release is a placeholder.\n"
    "It installs, tells you this, and does nothing else.\n"
    f"Follow along at {HOMEPAGE}"
)


def status() -> str:
    """Return what this release actually is. Importable, so a caller can
    check rather than guess."""
    return STATUS


def main() -> int:
    print(STATUS)
    return 0
