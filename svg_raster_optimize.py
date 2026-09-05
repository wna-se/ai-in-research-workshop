#!/usr/bin/env python3
"""Resize/recompress base64 PNG/JPEG images embedded in an SVG.

Requires ImageMagick 7 (`brew install imagemagick`).

Examples:
  # Write artwork.optimized.svg, preserving PNG/JPEG formats
  python3 svg_raster_optimize.py artwork.svg --max-width 1200 --max-height 1200

  # Replace the SVG, retaining artwork.svg.bak
  python3 svg_raster_optimize.py artwork.svg --in-place \
      --max-width 1200 --max-height 1200 --quality 82

  # Convert opaque embedded images to WebP (test your SVG consumers first)
  python3 svg_raster_optimize.py artwork.svg --in-place \
      --format webp --max-width 1600 --max-height 1600 --quality 80

  # Lossy PNG palette reduction for flat graphics/screenshots
  python3 svg_raster_optimize.py artwork.svg --in-place \
      --png-colors 256 --max-width 1200 --max-height 1200
"""

from __future__ import annotations

import argparse
import base64
import binascii
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


# Match only <image> elements while allowing > characters inside quoted attrs.
IMAGE_TAG_RE = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?image\b(?:\"[^\"]*\"|'[^']*'|[^'\">])*>",
    re.IGNORECASE | re.DOTALL,
)

# SVG 2 href and legacy xlink:href are both supported. Base64 may be wrapped.
DATA_URI_RE = re.compile(
    r"(?P<prefix>\b(?:xlink:)?href\s*=\s*)"
    r"(?P<quote>[\"'])"
    r"data:(?P<mime>image/(?:png|jpe?g));base64,(?P<data>.*?)"
    r"(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)

MIME_TO_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}

FORMAT_TO_MIME = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "avif": "image/avif",
}

FORMAT_TO_SUFFIX = {
    "png": ".png",
    "jpeg": ".jpg",
    "webp": ".webp",
    "avif": ".avif",
}


@dataclass
class Result:
    index: int
    changed: bool
    old_mime: str
    new_mime: str
    old_size: int
    new_size: int
    old_dimensions: str
    new_dimensions: str
    note: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimize base64 PNG/JPEG <image> elements inside an SVG."
    )
    parser.add_argument("svg", type=Path, help="Input SVG")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("-o", "--output", type=Path, help="Output SVG")
    destination.add_argument(
        "--in-place", action="store_true", help="Replace input and make a .bak backup"
    )
    parser.add_argument("--max-width", type=positive_int, help="Maximum raster width")
    parser.add_argument("--max-height", type=positive_int, help="Maximum raster height")
    parser.add_argument(
        "--format",
        choices=("keep", "png", "jpeg", "webp", "avif"),
        default="keep",
        help="Output format for embedded rasters (default: keep)",
    )
    parser.add_argument(
        "--quality",
        type=quality,
        default=82,
        help="JPEG/WebP/AVIF quality, 1-100 (default: 82)",
    )
    parser.add_argument(
        "--png-colors",
        type=png_colors,
        help="Lossily reduce PNGs to at most this many colors (2-256)",
    )
    parser.add_argument(
        "--background",
        default="white",
        help="Background when converting transparency to JPEG (default: white)",
    )
    parser.add_argument(
        "--allow-larger",
        action="store_true",
        help="Use processed data even when it is larger than the original",
    )
    parser.add_argument(
        "--keep-metadata",
        action="store_true",
        help="Do not strip raster profiles and metadata",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report potential changes without writing"
    )
    return parser.parse_args()


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def quality(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return number


def png_colors(value: str) -> int:
    number = int(value)
    if not 2 <= number <= 256:
        raise argparse.ArgumentTypeError("must be between 2 and 256")
    return number


def normalize_mime(mime: str) -> str:
    lowered = mime.lower()
    return "image/jpeg" if lowered in ("image/jpeg", "image/jpg") else lowered


def output_path(args: argparse.Namespace) -> Path:
    if args.in_place:
        return args.svg
    if args.output:
        return args.output
    return args.svg.with_name(f"{args.svg.stem}.optimized{args.svg.suffix}")


def resize_geometry(args: argparse.Namespace) -> str | None:
    if args.max_width and args.max_height:
        return f"{args.max_width}x{args.max_height}>"
    if args.max_width:
        return f"{args.max_width}x>"
    if args.max_height:
        return f"x{args.max_height}>"
    return None


def identify(path: Path) -> str:
    completed = subprocess.run(
        ["magick", "identify", "-format", "%wx%h", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def optimize_bytes(
    raw: bytes, source_mime: str, target_format: str, args: argparse.Namespace
) -> tuple[bytes, str, str]:
    source_suffix = MIME_TO_SUFFIX[source_mime]
    target_suffix = FORMAT_TO_SUFFIX[target_format]

    with tempfile.TemporaryDirectory(prefix="svg-raster-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / f"input{source_suffix}"
        target = temp / f"output{target_suffix}"
        source.write_bytes(raw)

        old_dimensions = identify(source)
        command = ["magick", str(source), "-auto-orient"]
        geometry = resize_geometry(args)
        if geometry:
            command.extend(["-resize", geometry])
        if not args.keep_metadata:
            command.append("-strip")

        if target_format == "jpeg":
            command.extend(
                [
                    "-background",
                    args.background,
                    "-alpha",
                    "remove",
                    "-alpha",
                    "off",
                    "-sampling-factor",
                    "4:2:0",
                    "-interlace",
                    "Plane",
                    "-quality",
                    str(args.quality),
                ]
            )
        elif target_format == "png":
            if args.png_colors:
                command.extend(["-dither", "FloydSteinberg", "-colors", str(args.png_colors)])
            command.extend(
                [
                    "-define",
                    "png:compression-level=9",
                    "-define",
                    "png:compression-strategy=1",
                ]
            )
        elif target_format == "webp":
            command.extend(
                ["-define", "webp:method=6", "-quality", str(args.quality)]
            )
        elif target_format == "avif":
            command.extend(["-quality", str(args.quality)])

        command.append(str(target))
        subprocess.run(command, check=True, capture_output=True)
        return target.read_bytes(), old_dimensions, identify(target)


def main() -> int:
    args = parse_args()
    if shutil.which("magick") is None:
        print("error: ImageMagick 7 is required; run: brew install imagemagick", file=sys.stderr)
        return 2
    if not args.svg.is_file():
        print(f"error: SVG not found: {args.svg}", file=sys.stderr)
        return 2

    try:
        svg_text = args.svg.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print("error: input is not a UTF-8 SVG", file=sys.stderr)
        return 2

    results: list[Result] = []
    image_index = 0

    def replace_tag(tag_match: re.Match[str]) -> str:
        nonlocal image_index
        tag = tag_match.group(0)

        def replace_uri(uri_match: re.Match[str]) -> str:
            nonlocal image_index
            image_index += 1
            source_mime = normalize_mime(uri_match.group("mime"))
            compact_base64 = re.sub(r"\s+", "", uri_match.group("data"))
            try:
                raw = base64.b64decode(compact_base64, validate=True)
            except (binascii.Error, ValueError) as exc:
                results.append(
                    Result(
                        image_index,
                        False,
                        source_mime,
                        source_mime,
                        0,
                        0,
                        "?",
                        "?",
                        f"invalid base64: {exc}",
                    )
                )
                return uri_match.group(0)

            target_format = (
                "jpeg" if source_mime == "image/jpeg" else "png"
            ) if args.format == "keep" else args.format
            target_mime = FORMAT_TO_MIME[target_format]

            try:
                optimized, old_dimensions, new_dimensions = optimize_bytes(
                    raw, source_mime, target_format, args
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr
                if isinstance(stderr, bytes):
                    stderr = stderr.decode(errors="replace")
                detail = stderr.strip() if stderr else str(exc)
                results.append(
                    Result(
                        image_index,
                        False,
                        source_mime,
                        target_mime,
                        len(raw),
                        len(raw),
                        "?",
                        "?",
                        f"ImageMagick failed: {detail}",
                    )
                )
                return uri_match.group(0)

            changed = args.allow_larger or len(optimized) < len(raw)
            results.append(
                Result(
                    image_index,
                    changed,
                    source_mime,
                    target_mime if changed else source_mime,
                    len(raw),
                    len(optimized) if changed else len(raw),
                    old_dimensions,
                    new_dimensions if changed else old_dimensions,
                    "" if changed else "kept original because processed image was not smaller",
                )
            )
            if not changed:
                return uri_match.group(0)

            encoded = base64.b64encode(optimized).decode("ascii")
            quote = uri_match.group("quote")
            return f'{uri_match.group("prefix")}{quote}data:{target_mime};base64,{encoded}{quote}'

        return DATA_URI_RE.sub(replace_uri, tag)

    optimized_svg = IMAGE_TAG_RE.sub(replace_tag, svg_text)

    if not results:
        print("No base64 PNG/JPEG <image> elements found.")
        return 0

    for result in results:
        status = "changed" if result.changed else "unchanged"
        saving = result.old_size - result.new_size
        percent = (saving / result.old_size * 100) if result.old_size else 0
        description = (
            f"image {result.index}: {status}; {result.old_mime} {result.old_dimensions} "
            f"{result.old_size:,} B -> {result.new_mime} {result.new_dimensions} "
            f"{result.new_size:,} B ({percent:.1f}% smaller)"
        )
        if result.note:
            description += f"; {result.note}"
        print(description)

    changed_count = sum(result.changed for result in results)
    if args.dry_run:
        print(f"Dry run: {changed_count} embedded image(s) would change; no file written.")
        return 0
    if changed_count == 0:
        print("Nothing was written because no embedded image became smaller.")
        return 0

    destination = output_path(args)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if args.in_place:
        backup = args.svg.with_name(f"{args.svg.name}.bak")
        shutil.copy2(args.svg, backup)
        print(f"Backup: {backup}")
    destination.write_text(optimized_svg, encoding="utf-8")
    print(f"Wrote: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
