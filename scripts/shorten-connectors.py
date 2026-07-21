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

PolygonPen = _classify.PolygonPen
make_remap = _narrow.make_remap
apply_remap = _narrow.apply_remap

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)


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


def body_interval(font, glyph, rise, step=16):
    """The x range where the letter rises above its connector.

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
    skip = set(settings.get("keep_long") or [])

    font = ufoLib2.Font.open(args.src)

    shortened = 0
    total_removed = 0.0
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours or glyph.name in skip:
            continue

        bounds = glyph.getBounds(font)
        if bounds is None:
            continue

        body = body_interval(font, glyph, rise)
        if body is None:
            continue

        left_approach = body[0] - bounds.xMin
        right_approach = bounds.xMax - body[1]
        if left_approach < 1 and right_approach < 1:
            continue

        # Target ink: the body, plus a bounded approach on whichever sides
        # currently have one. A side with no approach keeps none.
        target = (body[1] - body[0])
        target += min(left_approach, approach)
        target += min(right_approach, approach)

        remap = make_remap(bounds.xMin, bounds.xMax, body[0], body[1], target)
        if remap is None:
            continue

        before = bounds.xMax - bounds.xMin
        if not args.dry_run:
            apply_remap(glyph, remap)
        shortened += 1
        total_removed += before - target
        if args.verbose and (before - target) > nuqta:
            print(f"  {glyph.name:20} {before:6.0f} -> {target:6.0f} "
                  f"(body {body[0]:.0f}..{body[1]:.0f})")

    if not args.dry_run:
        if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
            shutil.rmtree(args.out)
        font.save(args.out, overwrite=True)

    mean = (total_removed / shortened) if shortened else 0
    print(f"shortened {shortened} Arabic glyphs, "
          f"mean {mean:.0f} units ({mean / nuqta:.2f} nuqta) of plateau removed"
          + ("" if args.dry_run else f" -> {args.out}"))


if __name__ == "__main__":
    main()
