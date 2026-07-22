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
# join).
TAIL_X_MAX = 245
TAIL_Y_TOP = 200
FOOT_MARGIN = 100      # how far up from the deepest ink the rounded foot reaches
TANGENT = 0.42         # cubic handle length as a fraction of the edge height


def weld_seam(glyph):
    """Remove the redundant join-band spike points at the meem's tail-loop seam.

    The seed bolts the tail rod onto the loop, leaving a short backtracking
    LINE segment on each join-band edge (a two-dot spike where one dot would
    do). Unioned at build time those spikes read as an acute white wedge biting
    into the loop — visible on the final meem in لم. A spike is a LINE-type
    on-curve point whose segment from its (on-curve) predecessor is short
    (<160u) and runs flat along a join-band edge (y~225 or y~369); the real
    connector edges are longer (~190u) and are not touched. Deleting the spike
    point lets the surrounding curve flow straight, so the loop meets the tail
    cleanly. The predecessor keeps its own controls, so the path stays valid.
    """
    removed = 0
    for contour in glyph.contours:
        pts = list(contour.points)
        n = len(pts)
        kill = set()
        for i, p in enumerate(pts):
            if p.type != "line":
                continue
            prev = pts[(i - 1) % n]
            if prev.type is None:            # predecessor must be on-curve
                continue
            if not (abs(p.y - 369) < 12 or abs(p.y - 225) < 12):
                continue
            if abs(prev.y - p.y) > 10:       # both ends on the same band edge
                continue
            if not (5 < abs(p.x - prev.x) < 160):   # short spike, not a connector edge
                continue
            kill.add(i)
        if kill:
            contour.points = [p for i, p in enumerate(pts) if i not in kill]
            removed += len(kill)
    return removed


def curve_tail(glyph, amount):
    """Bow the meem tail into an even curve.

    The rod is two long straight edges with no interior points, so shifting
    their ends only tilts them into a slant with a knee — what read as uneven.
    Instead: translate the already-rounded foot sideways as one rigid piece,
    then rebuild each straight rod edge as a cubic with vertical tangents at
    both ends, so the edge sweeps smoothly from the fixed top to the shifted
    foot. Both edges get the same profile, so the pen stays one width wide.
    """
    tail = [p for c in glyph.contours for p in c.points
            if p.x < TAIL_X_MAX and p.y < TAIL_Y_TOP]
    if not tail:
        return False
    y_foot = min(p.y for p in tail)
    if TAIL_Y_TOP - y_foot < 200:
        return False
    foot_top = y_foot + FOOT_MARGIN

    # Find the rod edges first (before the foot moves): consecutive on-curve
    # pairs forming a long, near-vertical line in the tail region.
    edges = []
    for contour in glyph.contours:
        pts = list(contour.points)
        n = len(pts)
        for i, p in enumerate(pts):
            nxt = pts[(i + 1) % n]
            if p.type is None or nxt.type != "line":
                continue
            if abs(nxt.x - p.x) > 15 or abs(nxt.y - p.y) < 350:
                continue
            if max(p.x, nxt.x) > TAIL_X_MAX:
                continue
            edges.append((contour, id(p), id(nxt)))

    if not edges:
        return False

    # Translate the foot (and each edge's bottom end) rigidly.
    for contour in glyph.contours:
        for point in contour.points:
            if point.x < TAIL_X_MAX and point.y <= foot_top:
                point.x += amount

    # Rebuild each edge as a smooth cubic between its (fixed) top and (moved)
    # foot end.
    Point = None
    for contour, top_id, bot_id in edges:
        pts = list(contour.points)
        n = len(pts)
        idx = next((i for i, p in enumerate(pts)
                    if id(p) == top_id and id(pts[(i + 1) % n]) == bot_id), None)
        if idx is None:
            continue
        A = pts[idx]                      # segment start
        B = pts[(idx + 1) % n]            # segment end (its .type is "line")
        if Point is None:
            Point = type(A)
        dy = B.y - A.y
        c1 = Point(x=A.x, y=A.y + TANGENT * dy, type=None)
        c2 = Point(x=B.x, y=B.y - TANGENT * dy, type=None)
        B.type, B.smooth = "curve", True
        A.smooth = True
        contour.points[idx + 1:idx + 1] = [c1, c2]
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
        welded = weld_seam(glyph)
        if curve_tail(glyph, amount):
            curved += 1
            if args.verbose:
                print(f"  {glyph.name:16} tail bowed {amount:+.0f}, welded {welded} seam(s)")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)
    print(f"bowed the tail of {curved} meem-family glyphs "
          f"({amount:+.0f} units) -> {args.out}")


if __name__ == "__main__":
    main()
