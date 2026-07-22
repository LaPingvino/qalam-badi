#!/usr/bin/env python3
"""Reshape the ya/maksura FINAL loop into a small, even, round crossing.

The cell draws the final ya (and maksura, and their dotted kin) as a big open
S with a tall middle and a loose eye. A written hand contracts that middle and
resolves it into a small round loop where the strokes cross. Joop drove the
shape by hand on the ya final; this reproduces it deterministically:

  1. Contract — pull the loop's outer top+left and its inner edge down, easing
     the two connector transitions so nothing tears.
  2. Collapse — merge the inner U (the three points 27/30/33 that bound the old
     eye) into a single crossing point, deleting the interior between them, so
     the closed eye is gone.
  3. Place — put the crossing at the exact midpoint of the loop top and bottom,
     then set the loop-left the same distance from it, so top/left/bottom sit
     equidistant around the centre and the stroke reads even width.
  4. Round — lay circular-arc bezier handles (radius R, tangents perpendicular
     to the radius) so the loop is a clean round curve, not a pointy beak.

The final forms share one body, so the six loop roles live at fixed contour
indices (27,30,33 inner; 40,43,46 outer); a guard checks they really are the
loop before touching a glyph. The ISOLATED forms are a different drawing (the
tall-terminal ya) with no such loop, so they never match and are left alone —
which is also how classical hands treat isolated vs final ya. Runs late on the
finished Regular; the derived masters inherit the reshaped body.

Usage:
    python3 scripts/reshape-ya-loop.py --src sources/QalamBadi-Regular.ufo
"""

import argparse
import math
import os

import ufoLib2

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_flatness = SourceFileLoader(
    "classify_flatness", os.path.join(_here, "classify-flatness.py")).load_module()

# The loop roles at their fixed contour indices in the shared final-form body.
I27, I30, I33, I40, I43, I46 = 27, 30, 33, 40, 43, 46
DL, DI = -300.0, -240.0     # contraction of the outer (top+left) and inner edges


def _has_loop(points):
    """True when indices 27/30/33/40/43/46 really are the S-loop, not something
    else (an isolated form's differently-drawn body fails this)."""
    if len(points) <= I46:
        return False
    for i in (I27, I30, I33, I40, I43, I46):
        if points[i].type is None:
            return False
    p = points
    return (p[I40].y > 200 and p[I46].y < 60 and p[I43].x < 400 and p[I27].x > 500)


def reshape(glyph):
    contour = max(glyph.contours, key=lambda c: len(c.points))
    p = list(contour.points)
    if not _has_loop(p):
        return None

    # 1) contract outer top+left (40, its two controls, 43, its control) and
    #    ease the two controls before 40 down toward the connector.
    for i in (I40, I40 + 1, I40 + 2, I43, I43 + 1):
        p[i].y += DL
    p[I40 - 1].y += DL * 0.75
    p[I40 - 2].y += DL * 0.35
    p[I43 + 2].y += DL * 0.40
    # contract the inner edge (30, 33 and the controls between them) and ease
    # the two controls after 33 (inner->connector) and before 30 (inner->cross).
    for i in (I30, I33, I30 + 1, I30 + 2):
        p[i].y += DI
    p[I33 + 1].y += DI * 0.85
    p[I33 + 2].y += DI * 0.35
    p[I30 - 1].y += DI * 0.75
    p[I30 - 2].y += DI * 0.30

    # 2+3) collapse 27/30/33 to the crossing M = midpoint(loop-top, loop-bottom).
    M = ((p[I40].x + p[I46].x) / 2, (p[I40].y + p[I46].y) / 2)
    p[I27].x, p[I27].y = M
    dele = set(range(I27 + 1, I33 + 1))     # delete the old eye interior

    # place the loop-left the same distance from M as the top/bottom, so all
    # three sit equidistant (even stroke width).
    R = math.hypot(M[0] - p[I40].x, M[1] - p[I40].y)
    vx, vy = p[I43].x - M[0], p[I43].y - M[1]
    length = math.hypot(vx, vy) or 1.0
    p[I43].x = M[0] + vx / length * R
    p[I43].y = M[1] + vy / length * R

    # 4) circular-arc handles for the loop 40 ->(41,42)-> 43 ->(44,45)-> 46.
    def angle(i):
        return math.atan2(p[i].y - M[1], p[i].x - M[0])

    def tangent(a):
        return (-math.sin(a), math.cos(a))      # CCW forward direction

    def arc(iA, iB, h_out, h_in):
        aA, aB = angle(iA), angle(iB)
        d = (aB - aA) % (2 * math.pi)
        hl = R * (4 / 3) * math.tan(d / 4)
        tA, tB = tangent(aA), tangent(aB)
        p[h_out].x = p[iA].x + tA[0] * hl
        p[h_out].y = p[iA].y + tA[1] * hl
        p[h_in].x = p[iB].x - tB[0] * hl
        p[h_in].y = p[iB].y - tB[1] * hl

    arc(I40, I43, I40 + 1, I43 - 1)
    arc(I43, I46, I43 + 1, I46 - 1)

    contour.points = [q for k, q in enumerate(p) if k not in dele]
    return round(R)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    font = ufoLib2.Font.open(args.src)
    done = 0
    for glyph in font:
        base, form = _flatness.base_and_form(glyph)
        if base not in _flatness.YEH_SKELETON or form not in ("fina", "isol"):
            continue
        if not glyph.contours:
            continue
        R = reshape(glyph)
        if R:
            done += 1
            if args.verbose:
                print(f"  {glyph.name}: round loop R={R}")

    font.save(args.src, overwrite=True)
    print(f"reshaped the loop of {done} ya/maksura final forms -> {args.src}")


if __name__ == "__main__":
    main()
