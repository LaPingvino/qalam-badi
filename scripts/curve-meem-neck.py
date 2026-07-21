#!/usr/bin/env python3
"""Sweep the meem's eye-neck into its tail, eating the flat shoulder.

Between the round eye and the descending tail the seed leaves a flat
horizontal bar — one pen thick, sitting in the join band — then turns a corner
into the tail. That shelf is a monospace stub; a reed pen flows the neck of the
eye straight down into the tail in one turn. (The isolated and final forms even
carry DIFFERENT shelf lengths, a tell the cell set it, not a hand.)

This is the initial-form elbow rotated ninety degrees: there a vertical stem
curves up into a horizontal connector; here the horizontal connector-band
curves down into the vertical tail. Both walls are rebuilt as concentric arcs
about one centre — inner at radius r, outer at r + pen — so the pen stays one
width through the turn, and the flat run is absorbed into the sweep.

The radius is clamped to the flat run actually present, so it eats the shelf
without biting into the eye, and self-sizes the two forms to match.

Runs BEFORE curve-meem-tail (the tail bow), so the bow's fixed top anchor is
the already-swept rod.

Usage:
    python3 scripts/curve-meem-neck.py --src sources/QalamBadi-Curved.ufo \
                                       --out sources/QalamBadi-MeemNeck.ufo
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
MEEM_SKELETON = {0x0645, 0x0765, 0x0766, 0x08A7, 0x06FE}


def find_tail_walls(contour):
    """The tail rod's two vertical LINE edges: returns (outer_x, inner_x, top_y)
    — the lower x is the outer wall, and top_y is where the rod meets the turn."""
    verticals = []
    pts = list(contour.points)
    n = len(pts)
    for i, p in enumerate(pts):
        nxt = pts[(i + 1) % n]
        if p.type is None or nxt.type != "line":
            continue
        if abs(nxt.x - p.x) > 12 or abs(nxt.y - p.y) < 300:
            continue
        top = max(p.y, nxt.y)
        verticals.append((p.x, top))
    if len(verticals) < 2:
        return None
    verticals.sort()
    outer_x = verticals[0][0]
    inner_x = verticals[-1][0]
    top_y = max(v[1] for v in verticals)
    return outer_x, inner_x, top_y


def _set(pt, xy, typ=None):
    pt.x, pt.y = xy
    if typ is not None:
        pt.type = typ
    if pt.type is not None:      # on-curve points only; off-curves can't be smooth
        pt.smooth = True


def sweep_neck(glyph, radius, join):
    bottom, top = join                       # 225, 369
    for contour in glyph.contours:
        walls = find_tail_walls(contour)
        if walls is None:
            continue
        outer_x, inner_x, _ = walls
        width = inner_x - outer_x

        pts = list(contour.points)
        n = len(pts)

        # Inner fillet: on-curve A on the inner tail wall (x≈inner_x), two
        # off-curves, on-curve B on the connector bottom (y≈bottom).
        inner = outer = None
        for i, A in enumerate(pts):
            if A.type is None:
                continue
            if pts[(i + 1) % n].type is not None or pts[(i + 2) % n].type is not None:
                continue
            B = pts[(i + 3) % n]
            if B.type is None:
                continue
            o1, o2 = pts[(i + 1) % n], pts[(i + 2) % n]
            if abs(A.x - inner_x) <= 14 and abs(B.y - bottom) <= 20:
                inner = (A, o1, o2, B)
            if abs(A.y - top) <= 20 and abs(B.x - outer_x) <= 14:
                outer = (A, o1, o2, B)
        if inner is None or outer is None:
            continue

        # The flat run present on the connector bottom sets the ceiling on the
        # radius, so the sweep eats the shelf without reaching into the eye.
        flat = abs(inner[3].x - inner_x)     # B.x is where the flat currently starts
        r = min(radius, max(flat, width))
        ox, oy = inner_x + r, bottom - r     # shared arc centre
        r_out = ox - outer_x

        # Inner arc: A down the tail wall (vertical tangent) -> B along the
        # connector bottom (horizontal tangent).
        A, o1, o2, B = inner
        _set(A, (inner_x, oy))
        _set(o1, (inner_x, oy + KAPPA * r))
        _set(o2, (ox - KAPPA * r, bottom))
        _set(B, (ox, bottom))

        # Outer arc, concentric: A2 along the connector top (horizontal tangent)
        # -> B2 down the tail outer wall (vertical tangent).
        A2, p1, p2, B2 = outer
        _set(A2, (ox, top))
        _set(p1, (ox - KAPPA * r_out, top))
        _set(p2, (outer_x, oy + KAPPA * r_out))
        _set(B2, (outer_x, oy))
        return True
    return False


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
    radius = (config.get("tails") or {}).get("meem_neck", 0.55) * nuqta

    font = ufoLib2.Font.open(args.src)
    from importlib.machinery import SourceFileLoader as _S
    PolygonPen = _S("classify_widths",
                    os.path.join(_here, "classify-widths.py")).load_module().PolygonPen
    join = _joins.measure_join_height(font, PolygonPen) or (225.0, 369.0)

    swept = 0
    for glyph in font:
        base, form = _flatness.base_and_form(glyph)
        if base not in MEEM_SKELETON or form not in ("fina", "isol"):
            continue
        if glyph.contours and sweep_neck(glyph, radius, join):
            swept += 1
            if args.verbose:
                print(f"  {glyph.name} neck swept")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)
    print(f"swept the neck of {swept} meem-family glyphs (radius {radius:.0f}) -> {args.out}")


if __name__ == "__main__":
    main()
