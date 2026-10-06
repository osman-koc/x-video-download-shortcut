"""Command line entry point: `python -m xvideo_shortcut`."""

from __future__ import annotations

import argparse
from pathlib import Path

from .flow import build_flow
from .model import Builder

ICON_COLOR = 4282601983
ICON_GLYPH = 59511  # download arrow


def build_shortcut(debug: bool = False) -> bytes:
    builder = Builder(debug=debug)
    build_flow(builder)
    return builder.dumps(ICON_COLOR, ICON_GLYPH)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the X Video Downloader shortcut (unsigned).")
    parser.add_argument(
        "-o", "--output",
        default="dist/X Video Downloader.unsigned.shortcut",
        help="Output path (default: %(default)s)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Add on-screen result popups after key steps (for troubleshooting).",
    )
    args = parser.parse_args(argv)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_shortcut(debug=args.debug))
    print(f"Wrote {out} ({out.stat().st_size} bytes). Sign it before importing on iOS; see README.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
