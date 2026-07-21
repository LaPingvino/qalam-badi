#!/usr/bin/env python3
"""Turn the initial forms' hard elbow into a curve.

The seed draws the initial (and some medial) tooth-letters as a literal L: a
tall vertical stem that meets the horizontal baseline connector at a right
angle, softened only by the tiny global corner fillet. A written hand does not
make that corner — the stem sweeps down into the baseline in one continuous
curve. Reported on word-initial ba and ya, which "are basically a corner and
need to be a curve instead."

The fix is a big fillet on that one concave elbow. soften-corners cannot do it:
it already ran, so the elbow is a smooth 48-unit arc, not a sharp corner it
would re-round — and its radius is clamped to a fraction of the adjacent
segments anyway. This pass finds the elbow by its exact geometry — a vertical
stem segment above, a fillet, then the horizontal connector at the join height
— reconstructs the original corner, and rebuilds the fillet at a generous
radius so the stem curves into the connector.

Only the tooth families (beh, yeh, noon skeletons) are touched, and only where
the vertical-stem-into-horizontal-connector elbow actually exists, so a slanted
medial tooth or a round letter is never affected.

Usage:
    python3 scripts/curve-initials.py --src sources/QalamBadi-Short.ufo \
                                      --out sources/QalamBadi-Curved.ufo
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
_joins = SourceFileLoader("joins", os.path.join(_here, "joins.py")).load_module()

KAPPA = 0.5523

FAMILIES = _flatness.BEH_SKELETON | _flatness.YEH_SKELETON | _flatness.NOON_SKELETON

STEM_TOL = 10        # max x-wander for a segment to count as a vertical stem
CONNECTOR_TOL = 30   # max distance from the join height for the elbow foot
FLAT_TOL = 10        # max y-wander for the connector to count as horizontal


def enlarge_elbow(glyph, radius, join_top):
    """Grow the vertical-stem -> horizontal-connector fillet to `radius`.

    Walks each contour for the pattern: an on-curve A reached from a vertical
    stem, two off-curve control points, an on-curve B that continues into a
    horizontal run at the join-top height. Reconstructs the sharp corner C at
    (stem x, connector y) and lays a quarter-circle of the given radius from up
    the stem to along the connector.
    """
    changed = 0
    for contour in glyph.contours:
        pts = list(contour.points)
        n = len(pts)
        for i, A in enumerate(pts):
            if A.type not in ("line", "curve"):
                continue
            # Two off-curves then an on-curve B: the existing fillet.
            if pts[(i + 1) % n].type is not None or pts[(i + 2) % n].type is not None:
                continue
            off1, off2 = pts[(i + 1) % n], pts[(i + 2) % n]
            B = pts[(i + 3) % n]
            if B.type not in ("line", "curve"):
                continue

            before = pts[(i - 1) % n]                 # on-curve above A
            after = pts[(i + 4) % n]                  # on-curve after B
            if after.type is None:
                continue

            # A sits on a vertical stem descending into the elbow.
            if abs(before.x - A.x) > STEM_TOL or before.y <= A.y:
                continue
            # B leads into a horizontal connector at the join top.
            if abs(B.y - join_top) > CONNECTOR_TOL or abs(after.y - B.y) > FLAT_TOL:
                continue

            corner_x, corner_y = A.x, B.y
            stem_room = before.y - corner_y
            conn_room = abs(after.x - corner_x)
            r = min(radius, stem_room * 0.9, conn_room * 0.9)
            if r < 60:
                continue
            conn_sign = -1.0 if after.x < corner_x else 1.0

            a_new = (corner_x, corner_y + r)
            b_new = (corner_x + conn_sign * r, corner_y)
            A.x, A.y = a_new
            A.type, A.smooth = "line", True
            off1.x, off1.y = corner_x, corner_y + r * (1 - KAPPA)
            off2.x, off2.y = corner_x + conn_sign * r * (1 - KAPPA), corner_y
            B.x, B.y = b_new
            B.type, B.smooth = "curve", True
            changed += 1
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Short.ufo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    nuqta = config["module"]["nuqta"]
    settings = config.get("initials") or {}
    radius = settings.get("elbow_radius", 0.9) * nuqta

    font = ufoLib2.Font.open(args.src)

    # The join height the elbow foot must sit at, measured, not assumed.
    from importlib.machinery import SourceFileLoader as _S
    PolygonPen = _S("classify_widths",
                    os.path.join(_here, "classify-widths.py")).load_module().PolygonPen
    join = _joins.measure_join_height(font, PolygonPen)
    join_top = join[1] if join else 369.0

    curved = 0
    for glyph in font:
        base, form = _flatness.base_and_form(glyph)
        if base not in FAMILIES or form not in ("init", "medi", "isol"):
            continue
        if not glyph.contours:
            continue
        n = enlarge_elbow(glyph, radius, join_top)
        if n:
            curved += 1
            if args.verbose:
                print(f"  {glyph.name:18} {n} elbow(s) curved")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)
    print(f"curved the elbow of {curved} initial-form glyphs "
          f"(radius {radius:.0f}) -> {args.out}")


if __name__ == "__main__":
    main()
