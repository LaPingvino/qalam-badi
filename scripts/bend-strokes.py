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


def apply_field(glyph, region, ramp, amplitude, dot_limit, spread=0.0):
    """Lower the tail by the dip field; optionally fan it out into a bowl.

    `spread` (units) pushes each point OUT toward the tip along the same ramp
    profile: the tip end moves the whole `spread`, a point the ramp barely
    touched barely moves. The push is toward the tip end of the region, so a
    tight plunging hook opens into a low wide bowl. Because the amount is a
    function of x (through the profile), it is a translation field on both
    axes — no scaling, so nothing can fatten.

    The spread is deliberately DECOUPLED from the vertical dip: it keys on the
    unit profile, not on how far the dip lowered the point, so a letter whose
    dip is capped to nothing by its below-dots (the dotted ya against its dots)
    still fans out to the full width its dotless twin (the alef maksura) does.
    Widening a tail leftward costs no vertical room, so the dot cap has no say
    over it — which is what un-folds the monospace-cramped ya and keeps it
    consistent with the maksura.
    """
    left, right = region
    # The tip is the far end of the tail region from the letter body. The
    # letter sits at region_right (the join side, field 0), so "out toward the
    # tip" is toward region_left; push in that direction.
    out = -1.0 if left <= right else 1.0

    def profile(x):
        # The ramp shape normalised to 0..1 (field is linear in amplitude, so
        # this is the amplitude=1 field), valid even when amplitude is 0.
        return field(x, left, right, ramp, 1.0)

    def push(point, x_ref):
        point.y -= amplitude * profile(x_ref)
        point.x += out * spread * profile(x_ref)

    for contour in glyph.contours:
        xs = [p.x for p in contour.points]
        ys = [p.y for p in contour.points]
        if not xs:
            continue
        if max(xs) - min(xs) <= dot_limit and max(ys) - min(ys) <= dot_limit:
            # A dot rides the field rigidly at its centre's offset.
            centre = (min(xs) + max(xs)) / 2
            for point in contour.points:
                push(point, centre)
        else:
            for point in contour.points:
                push(point, point.x)
    for component in glyph.components:
        xx, xy, yx, yy, dx, dy = component.transformation
        p = profile(dx)
        component.transformation = (
            xx, xy, yx, yy, dx + out * spread * p, dy - amplitude * p)
    for anchor in glyph.anchors:
        p = profile(anchor.x)
        anchor.x += out * spread * p
        anchor.y -= amplitude * p


def bowl_fan(glyph, font, spread, dot_limit, writing_line=225):
    """Open a round U bowl into a low wide bowl by a symmetric horizontal fan.

    Below the writing line, every point is pushed AWAY from the bowl's
    horizontal centre in proportion to how far below the line it sits — deepest
    fans widest, the line itself not at all. Tapering to zero at the writing
    line leaves the connector (which lives at and above the join height)
    untouched, so the join is unchanged; the fanned flanks drop below the
    baseline and sweep under the neighbour like a tail, so the advance need not
    grow. The amount is a function of (x-side, depth), a translation on both
    axes — nothing scales, so nothing fattens. Dots ride rigidly at their
    centre's offset, as everywhere else.
    """
    below = [(p.x, p.y) for contour in glyph.contours for p in contour.points
             if p.y < writing_line]
    if not below:
        return False
    ymin = min(y for _, y in below)
    span = writing_line - ymin
    if span < 1:
        return False
    centre = (min(x for x, _ in below) + max(x for x, _ in below)) / 2

    def shift(x, depth_frac, side_x):
        return (1.0 if side_x >= centre else -1.0) * spread * depth_frac

    for contour in glyph.contours:
        xs = [p.x for p in contour.points]
        ys = [p.y for p in contour.points]
        if not xs:
            continue
        if max(xs) - min(xs) <= dot_limit and max(ys) - min(ys) <= dot_limit:
            cy = (min(ys) + max(ys)) / 2
            if cy < writing_line:
                cx = (min(xs) + max(xs)) / 2
                dx = shift(cx, (writing_line - cy) / span, cx)
                for point in contour.points:
                    point.x += dx
        else:
            for point in contour.points:
                if point.y < writing_line:
                    point.x += shift(point.x, (writing_line - point.y) / span, point.x)
    return True


def round_finial(glyph, zone, strength, floor=None):
    """Inflate the tight terminal hook into a rounder curve.

    The hook has no sharp CORNER to fillet — soften-corners already ran, so
    every junction is smooth. It reads hard because it is drawn tight: a small,
    nearly-square arc. Rounding it therefore means making the arc bulge, not
    cutting a corner. For each cubic segment whose midpoint lands in the hook
    zone, the two off-curve control points are pushed away from the segment's
    chord — outward, on the side the curve already bulges — by `strength` times
    the segment length. A tight arc becomes a generous one; a straight segment
    (control points on the chord) is untouched, so this only ever rounds what
    is already curved.
    """
    if strength <= 0:
        return 0
    rounded = 0
    for contour in glyph.contours:
        pts = list(contour.points)
        n = len(pts)
        if n < 4:
            continue
        # Walk on-curve -> off -> off -> on cubic groups.
        for i, p in enumerate(pts):
            if p.type not in ("curve", "qcurve"):
                continue
            a = pts[(i - 3) % n]        # previous on-curve
            c1 = pts[(i - 2) % n]
            c2 = pts[(i - 1) % n]
            if a.type not in ON_CURVE or c1.type is not None or c2.type is not None:
                continue
            mx, my = (a.x + p.x) / 2, (a.y + p.y) / 2
            if not (zone[0] <= mx <= zone[1] and my < zone[2]):
                continue
            chord, length = unit(p.x - a.x, p.y - a.y)
            if chord is None or length < 20:
                continue
            # Normal to the chord; push each control point along the outward
            # normal (the side it already sits on) by strength * length.
            nx, ny = -chord[1], chord[0]
            for cp in (c1, c2):
                side = (cp.x - a.x) * nx + (cp.y - a.y) * ny
                sign = 1.0 if side >= 0 else -1.0
                cp.x += nx * sign * strength * length
                cp.y += ny * sign * strength * length
                # Inflation must not push a curve past the descender — that is
                # the clip the guard catches. Clamp the control point; the arc
                # stays below its on-curve neighbours, just not below the line.
                if floor is not None and cp.y < floor + 20:
                    cp.y = floor + 20
            rounded += 1
        if rounded:
            contour.points = pts
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
    tail_spread = settings.get("tail_spread", 0.0) * nuqta
    noon_fan = settings.get("noon_fan", 0.0) * nuqta
    hook_round = settings.get("hook_round", 0.0)
    dot_limit = nuqta * 1.35
    # The connector stroke sits at 225..369; the hook and bowl curves live
    # below it. Rounding only sub-connector curves keeps the join edges sharp.
    HOOK_CEIL = 210

    font = ufoLib2.Font.open(args.src)
    floor = font.info.openTypeOS2TypoDescender or -838

    bowls = tails = finials = fans = 0
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
            # The dip may be capped to nothing by below-dots, but the spread
            # still un-folds the tail sideways (no vertical room needed), so
            # run the field whenever EITHER axis has work to do.
            if amplitude > 2 or tail_spread > 0:
                apply_field(glyph, region, tail_ramp, amplitude, dot_limit,
                            spread=tail_spread)
                tails += 1
            finials += 1 if round_finial(
                glyph, (bounds.xMin, bounds.xMax, HOOK_CEIL), hook_round, floor) else 0
            if args.verbose:
                print(f"  tail {glyph.name:18} region {region[0]:5.0f}..{region[1]:5.0f}"
                      f" dip {amplitude:4.0f}")
            continue

        if base in TAH_FAMILY:
            continue

        # The noon family's round U bowl: open it sideways into a low wide
        # bowl. Not the beh boat (that gets the vertical dip below) — the noon
        # bowl has no flat bottom run to dip, it is a curve, so it wants the
        # symmetric fan instead.
        if base in _flatness.NOON_SKELETON and noon_fan > 0:
            if bowl_fan(glyph, font, noon_fan, dot_limit):
                fans += 1
            if args.verbose:
                print(f"  fan  {glyph.name:18} noon bowl +/-{noon_fan:.0f}")
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
            glyph, (bounds.xMin, bounds.xMax, HOOK_CEIL), hook_round, floor) else 0
        if args.verbose:
            print(f"  bowl {glyph.name:18} run {region[0]:5.0f}..{region[1]:5.0f}"
                  f" dip {amplitude:4.0f}")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)
    print(f"fanned {fans} noon bowls; "
          f"bent {bowls} bowls and {tails} tails, rounded finials on {finials} glyphs"
          f" -> {args.out}")


if __name__ == "__main__":
    main()
