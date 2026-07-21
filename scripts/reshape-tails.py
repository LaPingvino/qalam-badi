#!/usr/bin/env python3
"""Turn the deep dip into a long undertail. DISABLED — DO NOT USE AS WRITTEN.

    This script is out of the build because it breaks monolinearity, which is
    the one property the whole design rests on.

    It scales the tail region anisotropically: y by `depth` (0.85) and x by up
    to `extend` (2.6). An anisotropic scale only preserves stroke width for
    strokes that are exactly axis-aligned. Everywhere the tail runs vertically
    the stroke gets up to 2.6x FATTER; where it runs horizontally it gets 15%
    thinner; diagonals land in between. The seen/sheen/sad tails came out
    visibly too fat.

    The fix is the principle every other transform here already uses and this
    one forgot: translate, do not scale. Lengthening a tail without fattening it
    means stretching x ONLY across the stretch where the stroke is horizontal —
    there thickness is a vertical measurement, so an x-stretch is free — and
    rigidly translating everything beyond it. That is exactly how
    narrow-serifs.py pins the stem and how widen-seen-family.py repositions
    rather than scales.

    The proportional targets below are sound and worth keeping; only the
    mechanism is wrong.

Original description follows.

The seed's seen, sheen and sad end in a tail that plunges: it drops 555 units
below the writing line and travels barely further than it falls. That is a
naskh gesture, and a cell-bound one — a deep narrow hook was the only tail shape
that fitted in a 1228-unit box.

The hand we are after does the opposite. Its finals are **wide and shallow**:
measured on Mishkín-Qalam's own Greatest Name, a final runs about 1.5-1.7 alef
heights wide against only ~0.9 deep, and the tail returns rightward underneath
the letters that precede it rather than hanging below the one it belongs to.
With no cell left to fit, the shape can finally do that.

So the tail is flattened and lengthened at once, both ramped by depth so the
join to the body stays smooth:

    depth   how much of the original dip to keep (below 1 = shallower)
    extend  how much further the tail reaches (above 1 = longer)

Both are applied only below the writing line, and both ramp from nothing at the
writing line to full effect at the deepest point, so the tail leaves the letter
at exactly the angle it always did and only diverges as it descends. A hard
switch at the writing line would put a visible kink where the tail meets the
bowl.

The writing line is not y=0 in this font: the alef's foot and the bottom of
every connector sit at y=225, so that is the line the tail hangs from and the
line this transform measures from. It is read from the font rather than assumed.

Usage:
    python3 scripts/reshape-tails.py --src sources/QalamBadi-Connected.ufo \
                                     --out sources/QalamBadi-Tailed.ufo
"""

import argparse
import os
import shutil

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_classify = SourceFileLoader(
    "classify_widths",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "classify-widths.py")
).load_module()
_joins = SourceFileLoader(
    "joins", os.path.join(os.path.dirname(os.path.abspath(__file__)), "joins.py")
).load_module()

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)


def is_arabic(glyph):
    cp = glyph.unicode
    if cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def reshape(glyph, writing_line, depth, extend, min_drop):
    """Flatten and lengthen everything hanging below the writing line."""
    tail_points = [
        point
        for contour in glyph.contours
        for point in contour.points
        if point.y < writing_line
    ]
    if not tail_points:
        return 0.0, 0.0

    lowest = min(point.y for point in tail_points)
    drop = writing_line - lowest
    if drop < min_drop:
        return 0.0, 0.0  # not a tail, just a letter that dips slightly

    # The tail sweeps left, so it hangs from its rightmost point. Lengthening
    # means moving points further left the deeper they are; that anchor must
    # stay put or the tail detaches from the bowl.
    anchor = max(point.x for point in tail_points)

    for point in tail_points:
        ramp = (writing_line - point.y) / drop  # 0 at the writing line, 1 at the deepest
        point.y = writing_line - (writing_line - point.y) * depth
        point.x = anchor - (anchor - point.x) * (1.0 + (extend - 1.0) * ramp)

    return drop, drop * depth


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Connected.ufo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)

    nuqta = config["module"]["nuqta"]
    settings = config.get("tails") or {}
    depth = settings.get("depth", 0.62)
    extend = settings.get("extend", 1.45)
    min_drop = settings.get("min_drop", 0.85) * nuqta

    font = ufoLib2.Font.open(args.src)

    join_height = _joins.measure_join_height(font, _classify.PolygonPen)
    if join_height is None:
        raise SystemExit("no single Arabic join height found")
    writing_line = join_height[0]
    print(f"writing line: y={writing_line:.0f}")

    reshaped = 0
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours:
            continue
        before, after = reshape(glyph, writing_line, depth, extend, min_drop)
        if before:
            reshaped += 1
            if args.verbose and before > nuqta * 1.5:
                print(f"  {glyph.name:20} dip {before:6.0f} -> {after:6.0f} "
                      f"({before / nuqta:.2f} -> {after / nuqta:.2f} nuqta)")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)

    print(f"reshaped {reshaped} tails (depth x{depth}, reach x{extend}) -> {args.out}")


if __name__ == "__main__":
    main()
