#!/usr/bin/env python3
"""Bring the transliteration modifier letters into line with the quotes.

ʿ (U+02BF) and ʾ (U+02BE) are not decoration in a Bahá'í face — they are the
ayn and hamza of ʿAbdu'l-Bahá, Ḥuqúqu'lláh, nastaʿlīq. They sit directly beside
an apostrophe in running text, so any mismatch between them is conspicuous.

In the seed they mismatch, measurably:

    ʿ U+02BF     ink 604 x 680   y 457..1137   stroke 140
    ' quoteright ink 366 x 555   y 714..1269   stroke 125..262

Bigger, and sitting 257 units lower than the mark it stands beside. It came
through the proportional pass untouched because it is neither a cell-padded
serif nor an under-filled glyph, so no classifier had reason to look at it.

It also reads LIGHTER than the apostrophe, but measurement says that is not a
thin stroke: at 140 against a 141 pen it is exactly on weight. It is a long,
open arc, so the same weight covers more distance and less of it is ink. That
distinction decides what this script may do.

**This script only moves them vertically.** Scaling to match the quote's size
is the obvious fix and is deliberately not done: a uniform scale takes the
stroke from 140 to 115, and restoring it needs a genuine offset along the curve
normals. Dilating radially from the centroid — the cheap approximation — does
not work on a crescent, whose centroid lies on the arc itself, so the outward
directions are incoherent. Trading a correct 140 stroke for a 115 one in order
to fix an apparent size problem would make the glyph lighter, which is half of
what looked wrong in the first place.

Resizing these wants a redraw or a real offset-curve dilation. Until then, the
position fix is free and correct on its own.

Usage:
    python3 scripts/normalize-modifiers.py --src IN.ufo --out OUT.ufo
"""

import argparse
import math
import os
import shutil

import ufoLib2
import yaml


def measure_stroke(font, glyph, samples=9):
    """Median horizontal stroke width through the glyph."""
    from importlib.machinery import SourceFileLoader
    here = os.path.dirname(os.path.abspath(__file__))
    classify = SourceFileLoader(
        "classify_widths", os.path.join(here, "classify-widths.py")).load_module()
    joins = SourceFileLoader("joins", os.path.join(here, "joins.py")).load_module()

    pen = classify.PolygonPen(font)
    glyph.draw(pen)
    if not pen.polygons:
        return None
    bounds = glyph.getBounds(font)
    if bounds is None:
        return None

    transposed = [[(y, x) for x, y in poly] for poly in pen.polygons]
    widths = []
    span = bounds.yMax - bounds.yMin
    for i in range(1, samples + 1):
        y = bounds.yMin + span * i / (samples + 1)
        spans = joins.spans_at(transposed, y)
        if spans:
            widths.append(min(b - a for a, b in spans))
    if not widths:
        return None
    widths.sort()
    return widths[len(widths) // 2]


def dilate(glyph, amount):
    """Push every point outward from the glyph's centre by `amount`.

    Crude next to a real offset curve, but these are small single-stroke marks
    with no counters to collapse, and it restores the stroke weight without
    disturbing the shape.
    """
    points = [p for c in glyph.contours for p in c.points]
    if not points:
        return
    cx = sum(p.x for p in points) / len(points)
    cy = sum(p.y for p in points) / len(points)
    for point in points:
        dx, dy = point.x - cx, point.y - cy
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        point.x += dx / length * amount
        point.y += dy / length * amount


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    pen_width = config["module"]["pen"]
    targets = (config.get("modifiers") or {}).get("match", {})

    font = ufoLib2.Font.open(args.src)

    for name, reference_name in targets.items():
        glyph = font.get(name)
        reference = font.get(reference_name)
        if glyph is None or reference is None:
            continue
        bounds = glyph.getBounds(font)
        ref_bounds = reference.getBounds(font)
        if bounds is None or ref_bounds is None:
            continue

        before = (bounds.xMax - bounds.xMin, bounds.yMax - bounds.yMin)
        stroke_before = measure_stroke(font, glyph)

        # TRANSLATE ONLY. Resizing is deliberately not done here, and the
        # reason is worth recording.
        #
        # The glyph reads oversized next to an apostrophe, so scaling it down
        # is the obvious move. But its stroke already measures 140 against a
        # 141 pen — it is not thin, it is a long open arc that reads light —
        # and scaling to the quote's height takes that stroke to 115. Restoring
        # it needs a real outline offset along the curve normals; dilating
        # radially from the centroid does not work on a crescent, whose
        # centroid sits on the arc itself, so the outward directions are
        # incoherent.
        #
        # Trading a correct 140 stroke for a 115 one to fix an apparent size
        # problem makes the glyph lighter, which is half of what was wrong with
        # it. So only the part that is provably right and costs nothing is done:
        # the vertical position, where it sat 257 units below the quote it
        # stands beside.
        #
        # Resizing wants a redraw, or an offset-curve dilation, not a scale.
        dy = ref_bounds.yMax - bounds.yMax
        glyph.move((0, dy))

        after_bounds = glyph.getBounds(font)
        if args.verbose:
            print(f"  {name}: {before[0]:.0f}x{before[1]:.0f} stroke {stroke_before:.0f}"
                  f" -> {after_bounds.xMax - after_bounds.xMin:.0f}"
                  f"x{after_bounds.yMax - after_bounds.yMin:.0f}"
                  f" stroke {measure_stroke(font, glyph):.0f}"
                  f"  y {after_bounds.yMin:.0f}..{after_bounds.yMax:.0f}")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)
    print(f"normalized {len(targets)} modifier letters -> {args.out}")


if __name__ == "__main__":
    main()
