#!/usr/bin/env python3
"""Shorten the flat connector plateaus the monospace cell stretched into Arabic.

This is the same operation as scripts/narrow-serifs.py, pointed at a different
script — which is the point. In the Latin, the cell stretched serifs sideways
until they hit the walls; in the Arabic it stretched the baseline connectors the
same way, for the same reason. Both are fixed by pinning the part of the glyph
that carries the letter's identity and compressing the flat approach either side
of it. One idea, both scripts, so they stay siblings.

Why it matters here specifically: nastaʿlīq is one-sixth to one-third straight
(*saṭḥ*), the rest curve (*dowr*). Measured on the seed, 504 Arabic glyphs carry
a flat baseline run of exactly 1228 units — the entire cell — and the mean saṭḥ
share is 43%, which is naskh proportion, not nastaʿlīq. A medial letter in this
hand is a small tooth, not a plateau with a bump on it.

It is also why الله needs a hand-drawn ligature to look right: composed from
these forms it joins along stretched plateaus and reads as a fence rather than a
word. Shorten the connectors and the composed form comes out much closer to
correct on its own.

The body is found by vertical scanning — the x range over which the glyph rises
meaningfully above the connector band. Everything outside it is approach, and
gets compressed to the target. Join edges stay exactly where they are: the
compression happens between the edge and the body, so the connector still lands
on the advance edge and letters still meet.

Usage:
    python3 scripts/shorten-connectors.py --src sources/QalamBadi-Softened.ufo \
                                          --out sources/QalamBadi-Connected.ufo
"""

import argparse
import os
import shutil

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_classify = SourceFileLoader(
    "classify_widths", os.path.join(os.path.dirname(__file__), "classify-widths.py")
).load_module()
_narrow = SourceFileLoader(
    "narrow_serifs", os.path.join(os.path.dirname(__file__), "narrow-serifs.py")
).load_module()
_joins = SourceFileLoader(
    "joins", os.path.join(os.path.dirname(os.path.abspath(__file__)), "joins.py")
).load_module()

PolygonPen = _classify.PolygonPen
make_remap = _narrow.make_remap
apply_remap = _narrow.apply_remap

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)


JOIN_EDGE_TOLERANCE = 45
CONNECTOR_BAND = (-40, 420)


def join_sides(glyph, bounds):
    """Which edges carry a joining connector, by the same test the fitter uses."""
    left = right = False
    width = glyph.width
    lo, hi = CONNECTOR_BAND
    for contour in glyph.contours:
        for point in contour.points:
            if not (lo <= point.y <= hi):
                continue
            if point.x <= JOIN_EDGE_TOLERANCE:
                left = True
            if point.x >= width - JOIN_EDGE_TOLERANCE:
                right = True
    return left, right


def is_arabic(glyph):
    cp = glyph.unicode
    if cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def vertical_extent(polygons, x):
    """Highest and lowest ink at this x."""
    crossings = []
    for poly in polygons:
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if x0 == x1:
                continue
            if (x0 <= x < x1) or (x1 <= x < x0):
                t = (x - x0) / (x1 - x0)
                crossings.append(y0 + t * (y1 - y0))
    if not crossings:
        return None
    return min(crossings), max(crossings)


def baseline_thickness(polygons, x, probe):
    """Thickness of the ink span that contains the baseline stroke at this x.

    This is the shape test that height thresholds could not do. A connector is
    a stroke exactly one pen thick lying on the baseline; a tooth, a bowl or a
    loop is thicker, because the stroke goes up and comes back or dives below.
    Measuring the span that actually contains the baseline also ignores dots
    and marks floating above or below, which is what defeated the earlier
    approach — those inflate a naive yMax-yMin and make bare connector look
    like letter.
    """
    crossings = []
    for poly in polygons:
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if x0 == x1:
                continue
            if (x0 <= x < x1) or (x1 <= x < x0):
                t = (x - x0) / (x1 - x0)
                crossings.append(y0 + t * (y1 - y0))
    if len(crossings) < 2:
        return 0.0
    crossings.sort()
    # Walk the spans in pairs and return the one straddling the probe height.
    for lo, hi in zip(crossings[0::2], crossings[1::2]):
        if lo <= probe <= hi:
            return hi - lo
    return 0.0


def body_interval_by_join_height(font, glyph, join_height, step=12):
    """The x range that is the LETTER, i.e. not bare connector.

    Uses the font's single join height directly. At any x, if the only ink is a
    span matching that height exactly, the pen is simply travelling along the
    join line and nothing is being written — that stretch is whitespace as far
    as the letter is concerned, and is free to be shortened. Anywhere the ink
    departs from the join signature, the pen is drawing the letter.

    This replaces a thickness heuristic that guessed at the same thing and got
    it wrong on round forms: meem's loop never exceeded the thickness threshold,
    so the detector found a "body" a few units wide and would have compressed
    the letter away.
    """
    bottom, top = join_height
    tolerance = _joins.JOIN_TOLERANCE

    pen_pen = PolygonPen(font)
    glyph.draw(pen_pen)
    if not pen_pen.polygons:
        return None
    bounds = glyph.getBounds(font)
    if bounds is None:
        return None

    # Sample the whole glyph first, then decide where the letter starts and
    # ends — a single sample cannot be trusted on its own.
    samples = []
    x = bounds.xMin + 1
    while x < bounds.xMax:
        spans = _joins.spans_at(pen_pen.polygons, x)
        is_body = False
        if spans:
            only_join_line = all(
                abs(span_bottom - bottom) <= tolerance and abs(span_top - top) <= tolerance
                for span_bottom, span_top in spans
            )
            is_body = not only_join_line
        samples.append((x, is_body))
        x += step

    if not any(is_body for _, is_body in samples):
        return None

    # Take the LONGEST CONTIGUOUS RUN of body samples, not min..max of all of
    # them. Taking the extremes lets one stray sample define the whole letter,
    # and there is reliably a stray one: at the very edge of the overlap the
    # fillet rounds the connector's corner just enough to push its span outside
    # the join tolerance. That single false positive at x=-34 made medial lam
    # report a 768-unit body — 2.83 nuqta for what is a 141-unit vertical
    # stroke — so nothing was compressed and Allah stayed long.
    best_start = best_end = None
    best_length = 0
    run_start = None
    for index, (x, is_body) in enumerate(samples):
        if is_body and run_start is None:
            run_start = index
        elif not is_body and run_start is not None:
            if index - run_start > best_length:
                best_length, best_start, best_end = index - run_start, run_start, index - 1
            run_start = None
    if run_start is not None and len(samples) - run_start > best_length:
        best_length, best_start, best_end = len(samples) - run_start, run_start, len(samples) - 1

    if best_start is None:
        return None
    return samples[best_start][0], samples[best_end][0]


def body_interval(font, glyph, rise, step=16):
    """The x range where the letter rises above its connector.

    Superseded by body_interval_by_shape; kept because the flatness report
    still refers to the height-based reading it produced.

    Returns (left, right), or None if the glyph is connector all the way across
    (which would mean there is no letter to pin).
    """
    pen = PolygonPen(font)
    glyph.draw(pen)
    if not pen.polygons:
        return None
    bounds = glyph.getBounds(font)
    if bounds is None:
        return None

    xs = []
    x = bounds.xMin + 1
    while x < bounds.xMax:
        extent = vertical_extent(pen.polygons, x)
        if extent is not None:
            low, high = extent
            # Rising above the connector band, or dipping below it — a descending
            # bowl is as much "the letter" as an ascending tooth is.
            if high >= rise or low <= -rise * 0.55:
                xs.append(x)
        x += step

    if not xs:
        return None
    return min(xs), max(xs)


def apply_remap_preserving_dots(glyph, remap, nuqta):
    """Apply the x remap, but move dots rigidly instead of squashing them.

    The remap compresses the approach either side of the letter. Any contour
    living inside that region gets compressed with it — which is correct for the
    connector stroke and very wrong for a nuqta. A dot remapped point by point
    comes out as a horizontally squashed ellipse, and once it is thin enough the
    overlap removal in the build simply loses it. That is how the dot vanished
    from ba.

    A dot is a small closed contour that is not part of the writing stroke, so
    it is detected by size and moved as a rigid body: its centre is remapped and
    the contour follows, keeping its shape and its position under the letter.
    """
    dot_limit = nuqta * 1.35

    for contour in glyph.contours:
        xs = [p.x for p in contour.points]
        ys = [p.y for p in contour.points]
        if not xs:
            continue
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        if width <= dot_limit and height <= dot_limit:
            # Rigid: remap the centre, translate every point by the same amount.
            centre = (min(xs) + max(xs)) / 2
            shift = remap(centre) - centre
            for point in contour.points:
                point.x += shift
        else:
            for point in contour.points:
                point.x = remap(point.x)

    for component in glyph.components:
        xx, xy, yx, yy, dx, dy = component.transformation
        component.transformation = (xx, xy, yx, yy, remap(dx), dy)
    for anchor in glyph.anchors:
        anchor.x = remap(anchor.x)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Softened.ufo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)

    nuqta = config["module"]["nuqta"]
    settings = config.get("connectors") or {}
    approach = settings.get("approach", 0.42) * nuqta
    rise = settings.get("body_rise", 1.35) * nuqta
    pen = config["module"]["pen"]
    thickness_factor = settings.get("thickness_factor", 1.55)
    skip = set(settings.get("keep_long") or [])

    font = ufoLib2.Font.open(args.src)

    join_height = _joins.measure_join_height(font, PolygonPen)
    if join_height is None:
        raise SystemExit(
            "no single Arabic join height found; this transform depends on it")
    print(f"join height: y={join_height[0]:.0f}..{join_height[1]:.0f}")

    shortened = 0
    skipped_small = 0
    skipped_extreme = 0
    total_removed = 0.0
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours or glyph.name in skip:
            continue

        bounds = glyph.getBounds(font)
        if bounds is None:
            continue

        body = body_interval_by_join_height(font, glyph, join_height)
        if body is None:
            continue

        # Guard against a failed detection destroying a letter: a body only a
        # few units wide is not a letter, it is a detection failure.
        #
        # The threshold was 0.75 nuqta when the body was found by a thickness
        # heuristic that regularly misfired. Now that it is found from the
        # font's own join height and the longest contiguous run, it is reliable
        # enough to trust smaller bodies — initial lam measures 0.66 nuqta and
        # is perfectly real.
        body_width = body[1] - body[0]
        if body_width < nuqta * 0.45:
            skipped_small += 1
            continue

        # Only a side that actually carries a connector may be compressed.
        #
        # An isolated seen has ink running far to the LEFT of its origin, but
        # that is its tail, not an approach — it is the letter's most
        # characteristic feature. Treating it as a plateau compressed the tail
        # away and dragged the glyph so far left that the advance went negative,
        # which fontmake rejects outright ("width should not be negative").
        # A tail is a thing to keep; only the flat run leading into a join is
        # surplus.
        pen_poly = PolygonPen(font)
        glyph.draw(pen_poly)
        left_join, right_join = _joins.join_sides(glyph, pen_poly.polygons, join_height)

        # Measured from the JOIN POINTS, not from the ink bounds.
        #
        # The join happens at the origin and at the advance edge. The ink either
        # side of those — the 35-unit overlap the seed draws so letters share
        # ink rather than abut — is not approach and must not be compressed or
        # even moved relative to its join point. Measuring from bounds.xMin
        # instead dragged that overlap inward, which slid the join point off the
        # origin and unlinked every connector.
        origin = 0.0
        advance_edge = float(glyph.width)
        left_approach = max(0.0, body[0] - origin) if left_join else 0.0
        right_approach = max(0.0, advance_edge - body[1]) if right_join else 0.0

        keep_left = min(left_approach, approach)
        keep_right = min(right_approach, approach)
        removed_left = max(0.0, left_approach - keep_left)
        removed_right = max(0.0, right_approach - keep_right)
        if removed_left + removed_right < 2:
            continue

        # Second guard: do not take almost the whole glyph.
        #
        # This was 50% while the body detector was unreliable, and it then
        # blocked precisely the glyphs that most needed shortening: in a medial
        # form stretched to fill a 1228-unit cell the plateau genuinely IS more
        # than half the glyph. Medial lam, beh and seen were all being skipped
        # by it and stayed at exactly 1228, which is what kept Allah long.
        #
        # The body detector is now anchored on the font's measured join height
        # and takes the longest contiguous run, so it can be trusted much
        # further. This remains only as a backstop against a total misfire.
        if (removed_left + removed_right) > (bounds.xMax - bounds.xMin) * 0.82:
            skipped_extreme += 1
            continue

        # Anchored at the LEFT edge, not centred: the left connector and the
        # overlap it carries past the origin must not move at all, or every
        # join reopens the hairline seam we just closed. The body slides left
        # by whatever the left approach gave up, the right edge slides left by
        # the total, and the advance follows it so the right connector stays
        # exactly on the edge.
        body_left, body_right = body
        left_scale = ((left_approach - removed_left) / left_approach) if left_approach > 1 else 1.0
        right_scale = ((right_approach - removed_right) / right_approach) if right_approach > 1 else 1.0

        def remap(x, body_left=body_left, body_right=body_right,
                  left_scale=left_scale, right_scale=right_scale,
                  removed_left=removed_left, removed_right=removed_right,
                  advance_edge=advance_edge):
            # Beyond the origin: the left overlap, carried rigidly. It keeps its
            # exact offset from the join point, which is what makes letters
            # share ink instead of merely touching.
            if x <= 0.0:
                return x
            # Approach into the left join: compressed from the origin outwards.
            if x < body_left:
                return x * left_scale
            # The letter itself: translated, never scaled.
            if x <= body_right:
                return x - removed_left
            # Approach out to the right join.
            if x <= advance_edge:
                return (body_right - removed_left) + (x - body_right) * right_scale
            # Beyond the advance edge: the right overlap, carried rigidly so it
            # keeps its offset from the new advance edge.
            return x - removed_left - removed_right

        before = bounds.xMax - bounds.xMin
        # Last line of defence: an advance must stay positive and meaningful.
        new_width = round(glyph.width - removed_left - removed_right)
        if new_width < nuqta:
            skipped_extreme += 1
            continue

        if not args.dry_run:
            apply_remap(glyph, remap)
            # The advance must shrink with the geometry, otherwise the letter
            # gets narrower but still occupies its old monospace slot — which
            # is the whole complaint this transform exists to answer.
            glyph.width = new_width
        shortened += 1
        total_removed += removed_left + removed_right
        if args.verbose and (removed_left + removed_right) > nuqta * 0.5:
            print(f"  {glyph.name:20} ink {before:6.0f} -> {before - removed_left - removed_right:6.0f}"
                  f"  adv -{removed_left + removed_right:5.0f}"
                  f"  (body {body[0]:.0f}..{body[1]:.0f})")

    if not args.dry_run:
        if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
            shutil.rmtree(args.out)
        font.save(args.out, overwrite=True)

    mean = (total_removed / shortened) if shortened else 0
    print(f"skipped {skipped_small} (body too small to trust), "
          f"{skipped_extreme} (would remove over half the glyph)")
    print(f"shortened {shortened} Arabic glyphs, "
          f"mean {mean:.0f} units ({mean / nuqta:.2f} nuqta) of plateau removed"
          + ("" if args.dry_run else f" -> {args.out}"))


if __name__ == "__main__":
    main()
