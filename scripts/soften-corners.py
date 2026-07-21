#!/usr/bin/env python3
"""Round the corners, so the strokes read as a pen rather than a machine.

Courier's corners are perfectly sharp and its serifs are square slabs, because
a typewriter face is drawn as engineering. A reed pen does not do that: it lays
a stroke down and lifts it off, and every junction it makes carries a small
radius. Rounding the corners is the cheapest and most far-reaching way to move
the inherited outlines toward a written hand, and — unlike stroke modulation —
it costs us nothing we are trying to keep, since a fillet does not change stroke
width anywhere.

It applies across every script at once, which is the point: Latin serifs, Greek
terminals, Cyrillic corners and Arabic tooth junctions all soften together on
one shared radius, so the scripts stay siblings rather than drifting into
separate treatments.

Each corner is replaced by a circular-ish arc: the outline is trimmed back along
both incoming and outgoing tangents by the radius, and the two new points are
joined with a cubic whose handles point at where the corner used to be. The
radius is clamped per corner to a fraction of the shorter adjacent segment, so
short segments soften proportionally instead of collapsing.

Deliberately left alone:
  * Smooth points — already curves, nothing to round.
  * Near-straight junctions — rounding them does nothing but add points.
  * Very sharp spikes — the apex of A, W, v. A pen makes these sharp too, and
    filleting them reads as a blunted mistake rather than as fluency.
  * Arabic joining connectors at the advance edge — rounding the corner where
    one letter meets the next would round off the join itself and leave a visible
    notch in the connected line.

Usage:
    python3 scripts/soften-corners.py --src sources/QalamBadi-Regular.ufo \
                                      --out sources/QalamBadi-Regular.ufo
"""

import argparse
import math
import os
import shutil

import ufoLib2
import yaml

# Handle length for approximating a circular arc with a cubic. The exact value
# for a quarter circle is 0.5523; corners here are rarely exact quarters and a
# slightly shorter handle keeps the arc from bulging past the original corner.
KAPPA = 0.53

ON_CURVE = {"line", "curve", "qcurve", "move"}


def unit(dx, dy):
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return None, 0.0
    return (dx / length, dy / length), length


def corner_angle(incoming, outgoing):
    """Turn angle in degrees: 0 = straight on, 180 = folded back on itself."""
    dot = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def soften_contour(contour, radius, min_turn, max_turn, protect_x):
    points = list(contour.points)
    count = len(points)
    if count < 3:
        return 0, points

    # An open contour (starts with a 'move') must keep its endpoints put.
    is_open = points[0].type == "move"

    new_points = []
    softened = 0

    for index, point in enumerate(points):
        if point.type not in ON_CURVE or point.smooth or point.type == "move":
            new_points.append(point)
            continue
        if is_open and index in (0, count - 1):
            new_points.append(point)
            continue

        prev_point = points[(index - 1) % count]
        next_point = points[(index + 1) % count]

        incoming, in_len = unit(point.x - prev_point.x, point.y - prev_point.y)
        outgoing, out_len = unit(next_point.x - point.x, next_point.y - point.y)
        if incoming is None or outgoing is None:
            new_points.append(point)
            continue

        turn = corner_angle(incoming, outgoing)
        if turn < min_turn or turn > max_turn:
            new_points.append(point)
            continue

        # Never round an Arabic joining connector: the corner sitting on the
        # advance edge is where the next letter attaches, and softening it puts
        # a notch in the middle of the connected line.
        if protect_x is not None and any(
            abs(point.x - edge) <= 2.0 for edge in protect_x
        ):
            new_points.append(point)
            continue

        limit = 0.42 * min(in_len, out_len)
        effective = min(radius, limit)
        if effective < 4:
            new_points.append(point)
            continue

        p1 = (point.x - incoming[0] * effective, point.y - incoming[1] * effective)
        p2 = (point.x + outgoing[0] * effective, point.y + outgoing[1] * effective)
        c1 = (p1[0] + (point.x - p1[0]) * KAPPA, p1[1] + (point.y - p1[1]) * KAPPA)
        c2 = (p2[0] + (point.x - p2[0]) * KAPPA, p2[1] + (point.y - p2[1]) * KAPPA)

        Point = type(point)
        # The first new point inherits the segment type that arrived at the old
        # corner; the second closes the fillet and is therefore always a curve.
        new_points.append(Point(x=p1[0], y=p1[1], type=point.type, smooth=True))
        new_points.append(Point(x=c1[0], y=c1[1], type=None))
        new_points.append(Point(x=c2[0], y=c2[1], type=None))
        new_points.append(Point(x=p2[0], y=p2[1], type="curve", smooth=True))
        softened += 1

    return softened, new_points


def join_edges(glyph):
    """x positions that must not be rounded, because a letter attaches there."""
    return (0.0, float(glyph.width))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--radius", type=float, default=None,
                        help="corner radius in units; overrides spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)

    softening = config.get("softening") or {}
    radius = args.radius if args.radius is not None else softening.get("radius", 26)
    min_turn = softening.get("min_turn", 22)
    max_turn = softening.get("max_turn", 155)

    font = ufoLib2.Font.open(args.src)

    total = 0
    touched = 0
    for glyph in font:
        protect = join_edges(glyph)
        glyph_softened = 0
        for contour in glyph.contours:
            softened, new_points = soften_contour(
                contour, radius, min_turn, max_turn, protect
            )
            if softened:
                contour.points[:] = new_points
                glyph_softened += softened
        if glyph_softened:
            touched += 1
            total += glyph_softened
            if args.verbose and glyph_softened > 6:
                print(f"  {glyph.name:16} {glyph_softened} corners")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)

    print(f"softened {total} corners across {touched} glyphs "
          f"(radius {radius}) -> {args.out}")


if __name__ == "__main__":
    main()
