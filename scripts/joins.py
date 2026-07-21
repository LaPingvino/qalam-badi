#!/usr/bin/env python3
"""The one definition of what an Arabic join is, shared by every transform.

Arabic gives us something Latin never does: **every join in the font happens at
exactly the same height.** A connector is not "ink somewhere near the baseline",
it is one specific stroke — one pen thick, at one fixed height, sitting on the
advance edge. Measured across 604 joining glyphs in the seed, of the ~800 ink
spans touching an advance edge:

    750 have their bottom at exactly y=225
    728 have their top    at exactly y=369
    728 are exactly 144 units thick (the pen is 141)

That is not a tendency, it is a spec, and it makes join detection exact instead
of heuristic.

Every earlier attempt here used a band — "ink crossing the edge anywhere between
y=-40 and y=420" — and every Arabic bug we have chased came from it:

  * seen.fina kept a 1228 advance, because its tail sweeps left and crosses the
    origin on the way down. The band called that a left connector and pinned the
    sidebearing, so the advance could never shrink to fit the letter.
  * ya and ghain would not sweep, for the same reason.
  * The widening could not grow the advance, because a pinned edge cannot move.

A tail passing through an edge and a connector terminating at one look identical
to a band. They do not look remotely alike to a height-and-thickness test: the
tail crosses at whatever height it happens to be falling through, and is
travelling steeply rather than lying flat.

The join height is measured from the font at run time rather than hardcoded, so
that merging upstream Courier Badi — or changing the writing line — cannot
silently invalidate it. If the font stops having a single consistent join
height, that is something we want to be told about, not something to paper over.
"""

import collections

JOIN_TOLERANCE = 12.0     # units of slack on the join height
EDGE_TOLERANCE = 45.0     # how close to the advance edge counts as "at" it


def spans_at(polygons, x):
    """Ink spans (bottom, top) crossed by a vertical line at x."""
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
    crossings.sort()
    return list(zip(crossings[0::2], crossings[1::2]))


def is_joining_name(name, unicode_value=None):
    if any(name.endswith(s) for s in (".init", ".medi", ".fina", ".isol")):
        return True
    return name.startswith("uniFE") or name.startswith("uniFB")


def measure_join_height(font, polygon_pen_factory):
    """Find the font's join height: (bottom, top) of the connector stroke.

    Returns None if the font has no single dominant join height, which means
    the assumption this module rests on no longer holds and the caller should
    say so rather than guess.
    """
    bottoms = collections.Counter()
    tops = collections.Counter()
    samples = 0

    for glyph in font:
        if not is_joining_name(glyph.name, glyph.unicode) or not glyph.contours:
            continue
        pen = polygon_pen_factory(font)
        glyph.draw(pen)
        if not pen.polygons:
            continue
        for x in (0.5, glyph.width - 0.5):
            for bottom, top in spans_at(pen.polygons, x):
                bottoms[round(bottom)] += 1
                tops[round(top)] += 1
                samples += 1

    if not bottoms or not tops:
        return None

    bottom, bottom_count = bottoms.most_common(1)[0]
    top, top_count = tops.most_common(1)[0]

    # The dominant value has to actually dominate. In the seed it is ~94% of
    # samples; anything below half means there is no single join height.
    if bottom_count < samples * 0.5 or top_count < samples * 0.5:
        return None
    if top <= bottom:
        return None

    return float(bottom), float(top)


def join_sides(glyph, polygons, join_height):
    """Which edges of this glyph carry a real connector.

    A connector is ink at the advance edge whose span matches the font's join
    height at both ends. Ink crossing the edge at any other height — a final's
    tail sweeping past on its way down — is not a connector and must not pin
    the sidebearing.
    """
    bottom, top = join_height
    left = right = False

    for x, is_left in ((0.5, True), (glyph.width - 0.5, False)):
        for span_bottom, span_top in spans_at(polygons, x):
            if (abs(span_bottom - bottom) <= JOIN_TOLERANCE
                    and abs(span_top - top) <= JOIN_TOLERANCE):
                if is_left:
                    left = True
                else:
                    right = True

    return left, right
