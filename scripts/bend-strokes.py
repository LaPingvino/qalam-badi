#!/usr/bin/env python3
"""Bend the flat bowls and shallow tails: round, with a slight dip.

The cell drew every final's bowl as a dead-flat bar with a bracket bolted on
the end, and the seen family's tail as a long shallow shelf. A written hand
does neither: a beh leaves its tooth, sinks a fraction of a dot below the
writing line, and rises into a rounded finial; a seen's tail plunges and
returns. Both are the same correction — the stroke needs a BEND.

The mechanism is a vertical translation field, which is the x-remap machinery
rotated ninety degrees and therefore inherits its safety argument: each point
moves only in y, by an amount that varies smoothly with x. Nothing is scaled,
so nothing can fatten — the failure mode that killed reshape-tails. Vertical
thickness is exactly preserved; perpendicular thickness thins by cos(slope),
and the amplitudes here keep that under ~12%, which reads as a pen easing
through a curve rather than as a weight error.

The field is a plateau-and-ramp: zero at the letter side of the region, a
half-cosine ramp down, then full amplitude for the rest — so the hook or tail
tip TRANSLATES rigidly (a shape, moved whole) while only the stroke between
bends. Dots ride the field rigidly at their centre's offset, and the
amplitude is capped per glyph so no below-dot group is pushed back out of the
descender that tuck-dots just brought them inside.

A bend also converts length into depth at near-constant arc length, which is
the direction the seen tail has needed all along (too long x too shallow →
shorter x deeper). This pass is deliberately conservative on amplitude; the
knob lives in spacing.yaml (bends:) to be turned by eye.

Selection is measured, not guessed. Bowls: final/isolated glyphs with a
declared-straight bottom run of 1.5+ nuqta ON the writing line — excluding
the seen family (its flat run is a kashida, which is deliberately flat), the
tah family (its base is a loop), the tatweel (IS a kashida) and the U+060x
signs. Tails: the seen and yeh skeletons' finals/isolateds, region taken from
where the glyph's lower envelope actually hangs.

Usage:
    python3 scripts/bend-strokes.py --src sources/QalamBadi-Connected.ufo \
                                    --out sources/QalamBadi-Bent.ufo
"""

import argparse
import math
import os
import shutil

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_flatness = SourceFileLoader(
    "classify_flatness", os.path.join(_here, "classify-flatness.py")).load_module()
_soften = SourceFileLoader(
    "soften_corners", os.path.join(_here, "soften-corners.py")).load_module()
_classify = SourceFileLoader(
    "classify_widths", os.path.join(_here, "classify-widths.py")).load_module()
_joins = SourceFileLoader("joins", os.path.join(_here, "joins.py")).load_module()

PolygonPen = _classify.PolygonPen
unit = _soften.unit
corner_angle = _soften.corner_angle
KAPPA = _soften.KAPPA
ON_CURVE = _soften.ON_CURVE

is_arabic = _flatness.is_arabic

# The writing line: bowls sit on it, and their flat bottoms are found there.
WRITING_LINE_BAND = (180, 260)
# A tail is ink hanging well below the writing line.
TAIL_BELOW = 100

TAH_FAMILY = {0x0637, 0x0638, 0x069F, 0x08A2}
EXCLUDED_NAMES = {"uni0640"}  # the tatweel is a kashida; a kashida is flat


def field(x, region_left, region_right, ramp_fraction, amplitude):
    """Downward offset at x: plateau at the left, half-cosine ramp to zero."""
    if x >= region_right or amplitude <= 0:
        return 0.0
    ramp = max(1.0, (region_right - region_left) * ramp_fraction)
    ramp_start = region_right - ramp
    if x <= ramp_start:
        return amplitude
    t = (region_right - x) / ramp
    return amplitude * (1 - math.cos(math.pi * t)) / 2


def lower_envelope_region(polygons, bounds, below):
    """The x range where the glyph's tail hangs below `below`.

    The CONTIGUOUS run containing the deepest point, not min..max of every
    dipping sample — a dot below the teeth also dips, and taking the extremes
    would stretch the region under the letter body and lower the teeth with
    the tail. That is the same min..max mistake the body detector once made.
    """
    samples = []
    x = bounds.xMin + 1
    while x < bounds.xMax:
        spans = _joins.spans_at(polygons, x)
        depth = min((s[0] for s in spans), default=None) if spans else None
        samples.append((x, depth))
        x += 8
    dipping = [(x, d) for x, d in samples if d is not None and d < below]
    if not dipping:
        return None
    deepest_x = min(dipping, key=lambda s: s[1])[0]
    index = next(i for i, (x, _) in enumerate(samples) if x == deepest_x)
    lo = hi = index
    while lo > 0 and samples[lo - 1][1] is not None and samples[lo - 1][1] < below:
        lo -= 1
    while hi < len(samples) - 1 and samples[hi + 1][1] is not None and samples[hi + 1][1] < below:
        hi += 1
    return samples[lo][0], samples[hi][0]


def bowl_region(glyph):
    """The longest declared-flat bottom run on the writing line, or None."""
    runs = [r for r in _flatness.flat_runs(glyph)
            if WRITING_LINE_BAND[0] <= r[1] <= WRITING_LINE_BAND[1]]
    if not runs:
        return None
    longest = max(runs, key=lambda r: r[0])
    return longest[2], longest[3]


def dot_room(glyph, region, floor, dot_limit):
    """How far below-dot groups inside the region can still fall, in units."""
    room = None
    for contour in glyph.contours:
        xs = [p.x for p in contour.points]
        ys = [p.y for p in contour.points]
        if not xs:
            continue
        if max(xs) - min(xs) > dot_limit or max(ys) - min(ys) > dot_limit:
            continue
        centre = (min(xs) + max(xs)) / 2
        if not (region[0] <= centre <= region[1]) or min(ys) > 0:
            continue
        available = min(ys) - floor
        room = available if room is None else min(room, available)
    return room


def apply_field(glyph, region, ramp, amplitude, dot_limit):
    left, right = region
    for contour in glyph.contours:
        xs = [p.x for p in contour.points]
        ys = [p.y for p in contour.points]
        if not xs:
            continue
        if max(xs) - min(xs) <= dot_limit and max(ys) - min(ys) <= dot_limit:
            # A dot rides the field rigidly at its centre's offset.
            shift = field((min(xs) + max(xs)) / 2, left, right, ramp, amplitude)
            for point in contour.points:
                point.y -= shift
        else:
            for point in contour.points:
                point.y -= field(point.x, left, right, ramp, amplitude)
    for component in glyph.components:
        xx, xy, yx, yy, dx, dy = component.transformation
        component.transformation = (
            xx, xy, yx, yy, dx, dy - field(dx, left, right, ramp, amplitude))
    for anchor in glyph.anchors:
        anchor.y -= field(anchor.x, left, right, ramp, amplitude)


def round_finial(glyph, zone, radius, min_turn=22, max_turn=155):
    """A larger fillet on corners inside the hook/tip zone only.

    Same construction as soften-corners — that pass already ran with its
    modest global radius; this revisits just the finial with a radius that
    turns a bracket into a curve.
    """
    rounded = 0
    for contour in glyph.contours:
        points = list(contour.points)
        count = len(points)
        if count < 3:
            continue
        is_open = points[0].type == "move"
        new_points = []
        changed = 0
        for index, point in enumerate(points):
            if (point.type not in ON_CURVE or point.smooth or point.type == "move"
                    or (is_open and index in (0, count - 1))
                    or not (zone[0] <= point.x <= zone[1])):
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
            effective = min(radius, 0.42 * min(in_len, out_len))
            if effective < 4:
                new_points.append(point)
                continue
            p1 = (point.x - incoming[0] * effective, point.y - incoming[1] * effective)
            p2 = (point.x + outgoing[0] * effective, point.y + outgoing[1] * effective)
            c1 = (p1[0] + (point.x - p1[0]) * KAPPA, p1[1] + (point.y - p1[1]) * KAPPA)
            c2 = (p2[0] + (point.x - p2[0]) * KAPPA, p2[1] + (point.y - p2[1]) * KAPPA)
            Point = type(point)
            new_points.append(Point(x=p1[0], y=p1[1], type=point.type, smooth=True))
            new_points.append(Point(x=c1[0], y=c1[1], type=None))
            new_points.append(Point(x=c2[0], y=c2[1], type=None))
            new_points.append(Point(x=p2[0], y=p2[1], type="curve", smooth=True))
            changed += 1
        if changed:
            contour.points = new_points
            rounded += changed
    return rounded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    nuqta = config["module"]["nuqta"]
    settings = config.get("bends") or {}
    bowl_dip = settings.get("bowl_dip", 0.25) * nuqta
    bowl_ramp = settings.get("bowl_ramp", 0.62)
    tail_dip = settings.get("tail_dip", 0.60) * nuqta
    tail_ramp = settings.get("tail_ramp", 0.60)
    finial_radius = settings.get("finial_radius", 0.50) * nuqta
    dot_limit = nuqta * 1.35

    font = ufoLib2.Font.open(args.src)
    floor = font.info.openTypeOS2TypoDescender or -838

    bowls = tails = finials = 0
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours or glyph.name in EXCLUDED_NAMES:
            continue
        base, form = _flatness.base_and_form(glyph)
        if form not in ("fina", "isol") or base is None:
            continue
        cp = glyph.unicode
        if cp is not None and 0x0600 <= cp <= 0x0605:
            continue

        bounds = glyph.getBounds(font)
        if bounds is None:
            continue

        if base in _flatness.SEEN_SKELETON or base in _flatness.YEH_SKELETON:
            pen = PolygonPen(font)
            glyph.draw(pen)
            region = lower_envelope_region(pen.polygons, bounds, TAIL_BELOW)
            if region is None or region[1] - region[0] < nuqta:
                continue
            room = dot_room(glyph, region, floor, dot_limit)
            amplitude = tail_dip if room is None else max(0.0, min(tail_dip, room))
            # The whole region must stay inside the descender too.
            amplitude = max(0.0, min(amplitude, bounds.yMin - floor))
            if amplitude > 2:
                apply_field(glyph, region, tail_ramp, amplitude, dot_limit)
                tails += 1
            finials += 1 if round_finial(
                glyph, (region[0], region[0] + (region[1] - region[0]) * 0.35),
                finial_radius) else 0
            if args.verbose:
                print(f"  tail {glyph.name:18} region {region[0]:5.0f}..{region[1]:5.0f}"
                      f" dip {amplitude:4.0f}")
            continue

        if base in TAH_FAMILY:
            continue

        region = bowl_region(glyph)
        if region is None or region[1] - region[0] < nuqta * 1.5:
            continue
        room = dot_room(glyph, region, floor, dot_limit)
        amplitude = bowl_dip if room is None else max(0.0, min(bowl_dip, room))
        if amplitude > 2:
            apply_field(glyph, region, bowl_ramp, amplitude, dot_limit)
            bowls += 1
        finials += 1 if round_finial(
            glyph, (region[0] - nuqta, region[0] + (region[1] - region[0]) * 0.30),
            finial_radius) else 0
        if args.verbose:
            print(f"  bowl {glyph.name:18} run {region[0]:5.0f}..{region[1]:5.0f}"
                  f" dip {amplitude:4.0f}")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)
    print(f"bent {bowls} bowls and {tails} tails, rounded finials on {finials} glyphs"
          f" -> {args.out}")


if __name__ == "__main__":
    main()
