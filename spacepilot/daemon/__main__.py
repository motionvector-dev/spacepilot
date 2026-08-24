"""Run the SpacePilot daemon in the foreground."""

from __future__ import annotations

import argparse
from pathlib import Path

from spacepilot.daemon.server import run_daemon
from spacepilot.paths import daemon_socket_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m spacepilot.daemon")
    parser.add_argument(
        "--socket",
        type=Path,
        default=daemon_socket_path(),
    )
    parser.add_argument("--no-tailnet", action="store_true")
    args = parser.parse_args(argv)
    run_daemon(socket_path=args.socket, discover_tailnet=not args.no_tailnet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
