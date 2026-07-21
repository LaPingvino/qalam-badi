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

# The elbow is detected by GEOMETRY — a vertical stem dropping into the
# horizontal connector at the join height — but it is scoped to the families
# that actually carry the cell's L: the tooth letters (beh, yeh, noon) and the
# round-headed feh/qaf, whose initial stem is a cell artifact. It is NOT run
# font-wide: the same geometry occurs incidentally in round letters (heh's
# knot, the seen teeth) where it is not an L to be undone, and on the letters
# whose vertical is deliberate (alef, lam, kaf/gaf, tah), where curving it
# would be wrong. Add a family here when its initial shows the same L.
FEH_SKELETON = {
    0x0641, 0x0642, 0x066F, 0x06A1, 0x06A2, 0x06A3, 0x06A4, 0x06A5, 0x06A6,
    0x06A7, 0x06A8, 0x0760, 0x0761, 0x08A4, 0x08BB, 0x08BC,
}
FAMILIES = (_flatness.BEH_SKELETON | _flatness.YEH_SKELETON
            | _flatness.NOON_SKELETON | FEH_SKELETON)

STEM_TOL = 10        # max x-wander for a segment to count as a vertical stem
CONNECTOR_TOL = 30   # max distance from the join height for the elbow foot
FLAT_TOL = 10        # max y-wander for the connector to count as horizontal


def _fit_fillet(A, off1, off2, B, p_start, p_end, c_start, c_end):
    """Lay a cubic quarter-arc from p_start (tangent set by c_start) to p_end.

    A.type is left untouched: it describes the segment arriving AT A from the
    stem, which this reshape does not change. Forcing it to "line" broke any
    glyph whose stem arrived on a curve (an off-curve before a line point is
    an invalid contour)."""
    A.x, A.y = p_start
    A.smooth = True
    off1.x, off1.y = c_start
    off2.x, off2.y = c_end
    B.x, B.y = p_end
    B.type, B.smooth = "curve", True


def enlarge_elbow(glyph, radius, join):
    """Round the whole stem->connector bend, BOTH walls, to a big radius.

    The elbow is a bend in a constant-width stroke, not one corner. Rounding
    only the inner (concave) wall — which the first version did — leaves the
    outer wall cornered, so the stroke fattens through the turn and reads as a
    little ramp. Here both walls are rebuilt as CONCENTRIC arcs about one
    centre: the inner wall at radius r, the outer at r + w where w is the pen
    width (measured as the connector thickness), so the pen stays exactly one
    width wide all the way round.

    The inner fillet is found by its geometry (vertical stem above, fillet,
    horizontal connector at the join top); the outer fillet is then found on
    the same contour (horizontal connector bottom, fillet, vertical outer stem)
    and rebuilt concentric with it.
    """
    join_bottom, join_top = join
    width = join_top - join_bottom
    changed = 0
    for contour in glyph.contours:
        pts = list(contour.points)
        n = len(pts)
        for i, A in enumerate(pts):
            if A.type not in ("line", "curve"):
                continue
            if pts[(i + 1) % n].type is not None or pts[(i + 2) % n].type is not None:
                continue
            off1, off2 = pts[(i + 1) % n], pts[(i + 2) % n]
            B = pts[(i + 3) % n]
            if B.type not in ("line", "curve"):
                continue
            before = pts[(i - 1) % n]                 # on-curve above A (stem)
            after = pts[(i + 4) % n]                  # on-curve after B (connector)
            if after.type is None:
                continue
            if abs(before.x - A.x) > STEM_TOL or before.y <= A.y:
                continue
            if abs(B.y - join_top) > CONNECTOR_TOL or abs(after.y - B.y) > FLAT_TOL:
                continue

            corner_x, corner_y = A.x, B.y
            r = min(radius, (before.y - corner_y) * 0.9, abs(after.x - corner_x) * 0.9)
            if r < 60:
                continue
            conn_sign = -1.0 if after.x < corner_x else 1.0

            # Centre of both arcs.
            ox = corner_x + conn_sign * r
            oy = corner_y + r
            outer_stem_x = corner_x - conn_sign * width
            r_out = r + width

            # Inner wall: from up the stem, down to along the connector top.
            # The second handle points back INTO the arc (opposite conn_sign),
            # like the outer wall's; the earlier + here bent it the wrong way
            # and lumped the concave wall.
            _fit_fillet(
                A, off1, off2, B,
                (corner_x, corner_y + r),
                (ox, corner_y),
                (corner_x, corner_y + r * (1 - KAPPA)),
                (ox - conn_sign * r * KAPPA, corner_y))
            changed += 1

            # Outer wall: the fillet joining the connector bottom to the outer
            # stem. Find it on this contour and rebuild concentric.
            for j, A2 in enumerate(pts):
                if A2.type not in ("line", "curve"):
                    continue
                if pts[(j + 1) % n].type is not None or pts[(j + 2) % n].type is not None:
                    continue
                o1, o2 = pts[(j + 1) % n], pts[(j + 2) % n]
                B2 = pts[(j + 3) % n]
                if B2.type not in ("line", "curve"):
                    continue
                b2_before = pts[(j - 1) % n]          # connector bottom
                b2_after = pts[(j + 4) % n]           # outer stem
                if b2_after.type is None:
                    continue
                on_bottom = (abs(b2_before.y - join_bottom) <= CONNECTOR_TOL
                             and abs(A2.y - b2_before.y) <= FLAT_TOL)
                on_outer = (abs(b2_after.x - outer_stem_x) <= STEM_TOL + 8
                            and abs(B2.x - b2_after.x) <= STEM_TOL + 8
                            and b2_after.y > B2.y)
                if not (on_bottom and on_outer):
                    continue
                _fit_fillet(
                    A2, o1, o2, B2,
                    (ox, join_bottom),
                    (outer_stem_x, oy),
                    (ox - conn_sign * r_out * KAPPA, join_bottom),
                    (outer_stem_x, oy - r_out * KAPPA))
                break

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
    join = _joins.measure_join_height(font, PolygonPen) or (225.0, 369.0)

    curved = 0
    for glyph in font:
        base, form = _flatness.base_and_form(glyph)
        if base not in FAMILIES or form not in ("init", "medi", "isol"):
            continue
        if not glyph.contours:
            continue
        n = enlarge_elbow(glyph, radius, join)
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
