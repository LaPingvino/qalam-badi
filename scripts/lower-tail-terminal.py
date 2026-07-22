#!/usr/bin/env python3
"""Lower the seen/sad tail's inner terminal so it stops curling up.

The cell draws the seen/sad family's tail with its inner edge sweeping back up
well above the writing line into a tight hook. A written hand lets the tail end
low, out in the descender. This compresses the terminal's rise toward a low
baseline so the up-curl opens into a clean sweep — Joop's "point 9 -> height of
3" for the whole seen/sad/sheen family.

Why a late pass on the finished Regular, not inside bend-strokes: the terminal
is a POINTED peak at the bend-strokes (Connected) stage, and scaling a point
squishes it into a spike. Only after the proportional chain does the terminal
top settle flat, and scaling a flat top stays clean. So this runs after
make-proportional, in the Regular frame, and is copied into the derived masters
like every other Regular-frame edit.

Two guards keep it on the terminal and off the rest of the letter:
  * a horizontal CUTOFF — only the far (low-x) end of the tail region, never
    the body-side neck;
  * a vertical CEILING — only ink up to the writing-line band, never the eye or
    shoulder of the sad (whose lower-left sits well above the terminal and would
    otherwise be dragged down into a spike).

Usage:
    python3 scripts/lower-tail-terminal.py --src sources/QalamBadi-Regular.ufo
"""

import argparse
import os

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_flatness = SourceFileLoader(
    "classify_flatness", os.path.join(_here, "classify-flatness.py")).load_module()
_bend = SourceFileLoader(
    "bend_strokes", os.path.join(_here, "bend-strokes.py")).load_module()

PolygonPen = _bend.PolygonPen
TAIL_BELOW = _bend.TAIL_BELOW

BASE_Y = -124.0     # where the terminal should settle (the tail's descender level)
CEILING = 400.0     # above this is eye/shoulder, not terminal — leave it alone
CUTOFF_FRAC = 0.55  # only the far end of the tail region is the terminal


def compress_terminal(glyph, region, factor):
    left, right = region
    cutoff = left + CUTOFF_FRAC * (right - left)
    moved = 0
    for contour in glyph.contours:
        for p in contour.points:
            if p.x <= cutoff and BASE_Y < p.y < CEILING:
                p.y = BASE_Y + (p.y - BASE_Y) * factor
                moved += 1
    return moved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(open(args.config))
    factor = (config.get("bends") or {}).get("tail_terminal", 1.0)
    if factor >= 1.0:
        print("lower-tail-terminal: nothing to do (bends.tail_terminal unset)")
        return

    font = ufoLib2.Font.open(args.src)
    lowered = 0
    for glyph in font:
        base, form = _flatness.base_and_form(glyph)
        if base not in _flatness.SEEN_SKELETON or form not in ("fina", "isol"):
            continue
        if not glyph.contours:
            continue
        bounds = glyph.getBounds(font)
        if bounds is None:
            continue
        pen = PolygonPen(font)
        glyph.draw(pen)
        region = _bend.lower_envelope_region(pen.polygons, bounds, TAIL_BELOW)
        if region is None or region[1] - region[0] < 1:
            continue
        if compress_terminal(glyph, region, factor):
            lowered += 1
            if args.verbose:
                print(f"  {glyph.name}")

    font.save(args.src, overwrite=True)
    print(f"lowered the tail terminal of {lowered} seen/sad-family glyphs -> {args.src}")


if __name__ == "__main__":
    main()
