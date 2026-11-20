"""Build the unsigned Firefox companion XPI without development fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "browser_extension"
FILES = (
    "manifest.json",
    "background.js",
    "content.js",
    "logic.js",
    "options.html",
    "options.js",
)
ICON_FILES = (
    "jeff-icon.svg",
    "icon-16.png",
    "icon-32.png",
    "icon-48.png",
    "icon-96.png",
    "icon-128.png",
    "icon-512.png",
)


def build(destination: Path) -> Path:
    package_files = [*FILES, *(f"icons/{name}" for name in ICON_FILES)]
    missing = [name for name in package_files if not (SOURCE / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing Firefox extension files: " + ", ".join(missing))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as package:
        for name in package_files:
            package.write(SOURCE / name, arcname=name)
    with ZipFile(destination) as package:
        corrupt_entry = package.testzip()
        if corrupt_entry:
            destination.unlink(missing_ok=True)
            raise ValueError(f"Corrupt package entry: {corrupt_entry}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "jeff-browser-companion.xpi",
        help="XPI destination (default: dist/jeff-browser-companion.xpi)",
    )
    args = parser.parse_args()
    destination = build(args.output.expanduser().resolve())
    print(f"Created unsigned Firefox extension: {destination} ({destination.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
