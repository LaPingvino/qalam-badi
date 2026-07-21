#!/usr/bin/env python3
"""Bow the meem tail so it sweeps instead of dropping like a plumb line.

The seed draws the final and isolated meem as a round eye with a dead-straight
vertical rod hanging 754 units straight down — the foot is already a rounded
turn, but the rod itself is a ruler line, which is the cell showing through. A
reed pen does not draw a 754-unit perpendicular; the meem tail curves as it
falls.

The fix is a horizontal translation field along the tail — the bend-strokes
idea turned on its side. The rod is a vertical stroke, so its thickness is a
HORIZONTAL measurement; displacing every point in x by an amount that varies
smoothly with y bows the rod into a curve while keeping the pen exactly one
width wide (perpendicular thinning is cos(slope), a couple of percent at these
amplitudes). Both edges at a given height move together, so the stroke never
fattens — the one rule holds.

Only the tail is moved: points low and to the left, the rod, identified by
x below the eye and y below the connector. The eye, the connector and the
already-rounded foot ride along or stay put as their height dictates.

Usage:
    python3 scripts/curve-meem-tail.py --src sources/QalamBadi-Curved.ufo \
                                       --out sources/QalamBadi-Meem.ufo
"""

import argparse
import os
import shutil

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_flatness = SourceFileLoader(
    "classify_flatness", os.path.join(_here, "classify-flatness.py")).load_module()

# meem and the extended-Arabic letters that share its exact tail.
MEEM_SKELETON = {0x0645, 0x0765, 0x0766, 0x08A7, 0x06FE}

# The tail rod: ink left of the eye and below the connector band. X_MAX is
# tight so only the rod moves, not the eye's left edge (which would kink the
# join). The bow stays flat down to a knee, then curves — the tail leaves the
# eye vertically and hooks near the foot, which is what a hand draws.
TAIL_X_MAX = 245
TAIL_Y_TOP = 190
KNEE_FRACTION = 0.45   # top 45% of the drop stays straight; the rest curves


def bow(y, y_top, y_foot, amount):
    """Horizontal offset at height y: zero from the top down to the knee, then
    a quadratic ease to `amount` at the foot, so the rod falls straight and
    then curves into a hook."""
    if y >= y_top:
        return 0.0
    knee = y_top - (y_top - y_foot) * KNEE_FRACTION
    if y >= knee:
        return 0.0
    t = (knee - y) / (knee - y_foot)
    t = max(0.0, min(1.0, t))
    return amount * t * t


def curve_tail(glyph, amount):
    ys = [p.y for c in glyph.contours for p in c.points
          if p.x < TAIL_X_MAX and p.y < TAIL_Y_TOP]
    if not ys:
        return False
    y_foot = min(ys)
    if TAIL_Y_TOP - y_foot < 200:
        return False
    for contour in glyph.contours:
        for point in contour.points:
            if point.x < TAIL_X_MAX and point.y < TAIL_Y_TOP:
                point.x += bow(point.y, TAIL_Y_TOP, y_foot, amount)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Curved.ufo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    nuqta = config["module"]["nuqta"]
    amount = (config.get("tails") or {}).get("meem_bow", 0.55) * nuqta

    font = ufoLib2.Font.open(args.src)

    curved = 0
    for glyph in font:
        base, form = _flatness.base_and_form(glyph)
        if base not in MEEM_SKELETON or form not in ("fina", "isol"):
            continue
        if not glyph.contours:
            continue
        if curve_tail(glyph, amount):
            curved += 1
            if args.verbose:
                print(f"  {glyph.name:16} tail bowed {amount:+.0f}")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)
    print(f"bowed the tail of {curved} meem-family glyphs "
          f"({amount:+.0f} units) -> {args.out}")


if __name__ == "__main__":
    main()
