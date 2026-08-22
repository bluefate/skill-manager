"""Prepare web-ready logo and banner assets from source images.

Usage:
    python scripts/prepare_assets.py assets/logo-dark.png assets/logo-light.png \
        assets/banner-dark.png assets/banner-light.png

The script crops, resizes, and compresses PNG images for use in the web UI.
Default output sizes:
    - logo: 32x32 (favicon/header), 192x192 (large icon/PWA)
    - banner: max width 1200px, keeping aspect ratio

You can override the logo crop region with environment variables:
    ASM_LOGO_CROP_LEFT, ASM_LOGO_CROP_TOP, ASM_LOGO_CROP_RIGHT, ASM_LOGO_CROP_BOTTOM
    (values are pixels or 0-1 fractions relative to image size)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence


def _fraction_or_int(value: str, full: int) -> int:
    v = float(value)
    if 0 <= v <= 1 and "." in value:
        return int(v * full)
    return int(v)


def _crop_box(image_size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = image_size
    left = _fraction_or_int(os.environ.get("ASM_LOGO_CROP_LEFT", "0"), width)
    top = _fraction_or_int(os.environ.get("ASM_LOGO_CROP_TOP", "0"), height)
    right = _fraction_or_int(os.environ.get("ASM_LOGO_CROP_RIGHT", str(width)), width)
    bottom = _fraction_or_int(os.environ.get("ASM_LOGO_CROP_BOTTOM", str(height)), height)
    return (left, top, right, bottom)


def process_logo(src: Path, dest: Path, sizes: Sequence[int] = (32, 192)) -> None:
    """Crop and resize a logo to square icons."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Pillow is required. Run: pip install Pillow") from exc

    with Image.open(src) as img:
        img = img.convert("RGBA")
        crop = _crop_box(img.size)
        cropped = img.crop(crop)

        # Determine the largest square that fits inside the cropped region
        width, height = cropped.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        square = cropped.crop((left, top, left + side, top + side))

        for size in sizes:
            out_path = Path(str(dest).replace(".png", f"-{size}.png"))
            resized = square.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(out_path, "PNG", optimize=True)
            print(f"Saved {out_path} ({size}x{size})")


def process_banner(src: Path, dest: Path, max_width: int = 1200) -> None:
    """Resize a banner to a web-friendly width."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Pillow is required. Run: pip install Pillow") from exc

    with Image.open(src) as img:
        img = img.convert("RGBA")
        width, height = img.size
        if width > max_width:
            new_height = int(height * max_width / width)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        img.save(dest, "PNG", optimize=True)
        print(f"Saved {dest} ({img.size[0]}x{img.size[1]})")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare web-ready logo and banner assets")
    parser.add_argument("logo_dark", type=Path, help="Source dark logo PNG")
    parser.add_argument("logo_light", type=Path, help="Source light logo PNG")
    parser.add_argument("banner_dark", type=Path, help="Source dark banner PNG")
    parser.add_argument("banner_light", type=Path, help="Source light banner PNG")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "src"
        / "agent_skills_manager"
        / "web"
        / "static",
        help="Output directory for processed assets",
    )
    args = parser.parse_args(argv)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    for src in (args.logo_dark, args.logo_light, args.banner_dark, args.banner_light):
        if not src.exists():
            print(f"Source file not found: {src}", file=sys.stderr)
            return 1

    name_map = {
        args.logo_dark: out_dir / "logo-dark.png",
        args.logo_light: out_dir / "logo-light.png",
        args.banner_dark: out_dir / "banner-dark.png",
        args.banner_light: out_dir / "banner-light.png",
    }

    for src, dest in name_map.items():
        if "logo" in dest.name:
            process_logo(src, dest)
        else:
            process_banner(src, dest)

    return 0


if __name__ == "__main__":
    sys.exit(main())
