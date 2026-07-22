#!/usr/bin/env python3
"""Even out the seen/sheen teeth: centre the middle tooth between the outer two.

The wide isolated and final seen carry their middle tooth bunched toward the
right tooth — gaps of 962 / 380 units where they should read even. A written
seen spaces its three teeth evenly. This finds the three tooth tops and slides
the middle tooth (the ink between the two valleys that flank it) sideways so it
sits halfway between its neighbours. Only the middle tooth translates, as a
rigid piece; the outer teeth, the connectors and the tail stay put, so joins
and advances are untouched.

Detection is measured: sample the upper envelope of the BODY (dot contours
excluded — sheen's three dots sit above the teeth and would otherwise read as
false peaks), take the three ink peaks above the join band, and only act when
the middle one is off-centre by more than a comfortable margin. Forms that are
already even (initial, medial, and the narrower sheen) come out unchanged; the
sad/dad have an eye, not three teeth, so they never match.

Runs on the finished Regular after make-proportional, in the same slot as the
other late tooth/tail passes, and is copied into the derived masters.

Usage:
    python3 scripts/center-seen-teeth.py --src sources/QalamBadi-Regular.ufo
"""

import argparse
import os

import ufoLib2
import yaml
from ufoLib2.objects import Glyph

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_flatness = SourceFileLoader(
    "classify_flatness", os.path.join(_here, "classify-flatness.py")).load_module()
_joins = SourceFileLoader("joins", os.path.join(_here, "joins.py")).load_module()
_classify = SourceFileLoader(
    "classify_widths", os.path.join(_here, "classify-widths.py")).load_module()

PolygonPen = _classify.PolygonPen

JOIN_TOP = 369
MIN_OFFSET = 40      # don't bother below this — already even


def _body_only(glyph, dot_limit):
    """A copy with dot-sized contours dropped, for clean envelope sampling."""
    body = Glyph(name=glyph.name)
    body.width = glyph.width
    for contour in glyph.contours:
        xs = [p.x for p in contour.points]
        ys = [p.y for p in contour.points]
        if xs and max(xs) - min(xs) <= dot_limit and max(ys) - min(ys) <= dot_limit:
            continue
        body.contours.append(contour)
    return body


def _envelope(glyph, font, dot_limit, step=10):
    body = _body_only(glyph, dot_limit)
    pen = PolygonPen(font)
    body.draw(pen)
    bounds = body.getBounds(font)
    if bounds is None:
        return None
    xs, tops = [], []
    x = bounds.xMin + 4
    while x < bounds.xMax:
        spans = _joins.spans_at(pen.polygons, x)
        tops.append(max((s[1] for s in spans), default=-1e9) if spans else -1e9)
        xs.append(x)
        x += step
    return xs, tops


def _peaks(xs, tops, thr):
    peaks = []
    for i in range(1, len(tops) - 1):
        if tops[i] > thr and tops[i] >= tops[i - 1] and tops[i] >= tops[i + 1]:
            if peaks and xs[i] - peaks[-1][0] < 220:      # merge a flat top
                if tops[i] > peaks[-1][1]:
                    peaks[-1] = (xs[i], tops[i])
            else:
                peaks.append((xs[i], tops[i]))
    return peaks


def _valley_x(xs, tops, x1, x2):
    cand = [(tops[i], xs[i]) for i in range(len(xs)) if x1 < xs[i] < x2]
    return min(cand)[1] if cand else (x1 + x2) / 2


def center_middle_tooth(glyph, font, nuqta):
    dot_limit = nuqta * 1.35
    env = _envelope(glyph, font, dot_limit)
    if env is None:
        return 0
    xs, tops = env
    peaks = _peaks(xs, tops, JOIN_TOP + 120)
    if len(peaks) != 3:
        return 0
    target = (peaks[0][0] + peaks[2][0]) / 2
    shift = target - peaks[1][0]
    if abs(shift) < MIN_OFFSET:
        return 0
    v12 = _valley_x(xs, tops, peaks[0][0], peaks[1][0])
    v23 = _valley_x(xs, tops, peaks[1][0], peaks[2][0])
    for contour in glyph.contours:
        for p in contour.points:
            if v12 < p.x < v23:
                p.x += shift
    return round(shift)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    nuqta = yaml.safe_load(open(args.config))["module"]["nuqta"]
    font = ufoLib2.Font.open(args.src)

    centered = 0
    for glyph in font:
        base, _ = _flatness.base_and_form(glyph)
        if base not in _flatness.SEEN_SKELETON or not glyph.contours:
            continue
        shift = center_middle_tooth(glyph, font, nuqta)
        if shift:
            centered += 1
            if args.verbose:
                print(f"  {glyph.name}: middle tooth {shift:+d}")

    font.save(args.src, overwrite=True)
    print(f"centred the middle tooth of {centered} seen/sheen glyphs -> {args.src}")


if __name__ == "__main__":
    main()
