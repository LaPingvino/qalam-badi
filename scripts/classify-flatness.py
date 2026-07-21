#!/usr/bin/env python3
"""Find the long flat runs the monospace cell forced into the Arabic.

Long flat lines are a red flag in this script for the same reason big open
spaces were a red flag in the Latin: both are the cell showing through. A
connector had to reach the wall of its box whether the letter wanted to be that
wide or not, so it was stretched into a plateau — and a plateau is precisely
what a nastaʿlīq hand does not draw.

The classical rule is explicit about it. Nastaʿlīq is **one-sixth to one-third
straight** (*saṭḥ*), the rest curved (*dowr*); one source puts the ratio at at
least 5:1 in favour of curve, against naskh's 1:2. Only the alef/lam stems and a
deliberate kashida should be truly straight. Everything else is arc.

This is also why الله needs its dedicated ligature glyph to look right: the
letters that compose it join along stretched flat connectors, so the joined form
reads as a fence rather than as a written word, and the ligature has to be drawn
by hand to paper over it. Shorten the connectors and the composed form should
come out close to right on its own.

A "flat run" here means a genuinely straight segment — two consecutive on-curve
points with no control points between them — that is near-horizontal and sits in
the band where joins happen. Flattened curve approximations are deliberately not
counted; we want the lines the outline actually declares to be lines.

Usage:
    python3 scripts/classify-flatness.py --src sources/QalamBadi-Mono.ufo
    python3 scripts/classify-flatness.py --src sources/QalamBadi-Mono.ufo --tsv
"""

import argparse
import math

import ufoLib2

# A segment is "flat" if it rises less than this many units per unit of run.
# 0.18 is about 10 degrees — steeper than that and it reads as a sweep, not a
# plateau.
FLAT_SLOPE = 0.18

# Only runs in this band above/below the baseline are of interest: these are the
# connector plateaus. A flat run high in the letter is a different creature (the
# bar of a kaf, the roof of a tah) and is not what the cell distorted.
BASELINE_BAND = (-260, 500)

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)


def is_arabic(glyph):
    cp = glyph.unicode
    if cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def flat_runs(glyph):
    """Straight, near-horizontal segments near the baseline.

    Returns a list of (length, y, x_start, x_end).
    """
    runs = []
    for contour in glyph.contours:
        points = list(contour.points)
        count = len(points)
        if count < 2:
            continue
        for index, point in enumerate(points):
            if point.type not in ("line", "curve", "qcurve", "move"):
                continue
            nxt = points[(index + 1) % count]
            # A line segment is declared by the NEXT point being an on-curve of
            # type "line"; anything else means control points intervene.
            if nxt.type != "line":
                continue
            dx = nxt.x - point.x
            dy = nxt.y - point.y
            if abs(dx) < 1:
                continue
            if abs(dy / dx) > FLAT_SLOPE:
                continue
            mid_y = (point.y + nxt.y) / 2
            if not (BASELINE_BAND[0] <= mid_y <= BASELINE_BAND[1]):
                continue
            runs.append((abs(dx), mid_y, min(point.x, nxt.x), max(point.x, nxt.x)))
    return runs


def straightness(glyph):
    """Fraction of outline length that is declared straight — the saṭḥ share."""
    straight = 0.0
    total = 0.0
    for contour in glyph.contours:
        points = list(contour.points)
        count = len(points)
        if count < 2:
            continue
        previous = None
        for index, point in enumerate(points):
            if point.type is None:
                continue
            if previous is not None:
                length = math.hypot(point.x - previous[0], point.y - previous[1])
                total += length
                if point.type == "line":
                    straight += length
            previous = (point.x, point.y)
    return (straight / total) if total else 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Mono.ufo")
    parser.add_argument("--tsv", action="store_true")
    parser.add_argument("--min-length", type=float, default=300,
                        help="report runs at least this long (units)")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    font = ufoLib2.Font.open(args.src)
    nuqta = 271

    rows = []
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours:
            continue
        runs = flat_runs(glyph)
        if not runs:
            continue
        longest = max(runs, key=lambda r: r[0])
        if longest[0] < args.min_length:
            continue
        rows.append((longest[0], glyph.name, longest, straightness(glyph), len(runs)))

    rows.sort(reverse=True)

    if args.tsv:
        print("glyph\tlongest_flat\tnuqta\tsath_share\tflat_runs")
        for length, name, run, sath, count in rows:
            print(f"{name}\t{length:.0f}\t{length / nuqta:.2f}\t{sath:.2f}\t{count}")
        return

    print(f"Arabic glyphs with a flat baseline run of {args.min_length:.0f}+ units")
    print(f"({len(rows)} of them; the nuqta is {nuqta} units)\n")
    print(f"{'glyph':22}{'flat run':>10}{'nuqta':>8}{'sath':>8}  runs")
    for length, name, run, sath, count in rows[:args.limit]:
        print(f"{name:22}{length:10.0f}{length / nuqta:8.2f}{sath:8.0%}  {count}")
    if len(rows) > args.limit:
        print(f"... and {len(rows) - args.limit} more")

    if rows:
        share = sum(r[3] for r in rows) / len(rows)
        print(f"\nmean saṭḥ share across these glyphs: {share:.0%}")
        print("classical nastaʿlīq: 17-33%. naskh: ~50%.")


if __name__ == "__main__":
    main()
