#!/usr/bin/env python3
"""Classify which glyphs the monospace cell distorted, and in which direction.

Converting Courier to a proportional face is not one problem but two, and they
need opposite treatments:

  NARROW  The glyph's ink is genuinely much smaller than the cell — alef,
          period, comma, i-in-a-sans-world. Nothing is wrong with the outline;
          it was simply parked in a cell far too big for it. Re-fitting the
          advance (scripts/make-proportional.py) is the whole fix.

  PADDED  The glyph's ink fills the cell, but only because its SERIFS were
          stretched to reach the cell walls. Courier's `i` is one 141-unit stem
          carrying serifs 910 units across. Re-fitting the advance does nothing
          here: the ink really is that wide, so `i` stays nearly as wide as `m`
          and the face still reads as monospace. These need the outline itself
          narrowed, at the serif.

  OK      Ink and body agree: the glyph was always about this wide. Leave it.

The discriminator is the ratio between the glyph's ink extent at the SERIF band
(just above the baseline, where Courier's slabs live) and at the BODY band
(mid x-height, where only the actual strokes are). A glyph padded out to fill
the cell has a large ratio; an honestly wide glyph has a ratio near 1.

Scanlines are computed by flattening the outlines to polygons and intersecting,
which avoids depending on a rasteriser.

Usage:
    python3 scripts/classify-widths.py --src sources/QalamBadi-Mono.ufo
    python3 scripts/classify-widths.py --src sources/QalamBadi-Mono.ufo --tsv > widths.tsv
"""

import argparse
import sys

import ufoLib2
from fontTools.misc.bezierTools import splitCubicAtT
from fontTools.pens.basePen import BasePen

# Ratio of serif-band ink to body-band ink above which we call a glyph padded
# out to fill the cell rather than honestly wide. Courier's `i` measures ~6.5;
# `m` and `o` measure ~1.0-1.2; the gap between the two populations is wide, so
# the exact threshold is not delicate.
PADDED_RATIO = 1.9

# A glyph using less than this fraction of the cell is under-filled.
NARROW_FRACTION = 0.62


class PolygonPen(BasePen):
    """Flatten outlines into closed polygons for scanline intersection."""

    STEPS = 16

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.polygons = []
        self._current = []

    def _moveTo(self, pt):
        self._flushContour()
        self._current = [pt]

    def _lineTo(self, pt):
        self._current.append(pt)

    def _curveToOne(self, p1, p2, p3):
        p0 = self._current[-1]
        for i in range(1, self.STEPS + 1):
            t = i / self.STEPS
            mt = 1 - t
            x = (mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0]
                 + 3 * mt * t * t * p2[0] + t ** 3 * p3[0])
            y = (mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1]
                 + 3 * mt * t * t * p2[1] + t ** 3 * p3[1])
            self._current.append((x, y))

    def _qCurveToOne(self, p1, p2):
        p0 = self._current[-1]
        for i in range(1, self.STEPS + 1):
            t = i / self.STEPS
            mt = 1 - t
            x = mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0]
            y = mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]
            self._current.append((x, y))

    def _closePath(self):
        self._flushContour()

    def _endPath(self):
        self._flushContour()

    def _flushContour(self):
        if len(self._current) > 2:
            self.polygons.append(self._current)
        self._current = []


def scanline_extent(polygons, y):
    """Total horizontal extent of ink at height y, and the number of runs."""
    crossings = []
    for poly in polygons:
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if y0 == y1:
                continue
            if (y0 <= y < y1) or (y1 <= y < y0):
                t = (y - y0) / (y1 - y0)
                crossings.append(x0 + t * (x1 - x0))
    if len(crossings) < 2:
        return 0.0, 0
    crossings.sort()
    return crossings[-1] - crossings[0], len(crossings) // 2


def measure(font, glyph):
    pen = PolygonPen(font)
    glyph.draw(pen)
    if not pen.polygons:
        return None

    bounds = glyph.getBounds(font)
    if bounds is None:
        return None

    x_height = font.info.xHeight or 924
    # Serif band: low enough to catch the slab, high enough to clear any
    # baseline overshoot on round letters.
    serif_y = bounds.yMin + 60
    body_y = x_height * 0.55

    serif_extent, _ = scanline_extent(pen.polygons, serif_y)
    body_extent, runs = scanline_extent(pen.polygons, body_y)

    return {
        "ink": bounds.xMax - bounds.xMin,
        "serif": serif_extent,
        "body": body_extent,
        "runs": runs,
    }


def classify(measurement, cell):
    ink, serif, body = measurement["ink"], measurement["serif"], measurement["body"]
    if body <= 1:
        # No ink at the body scanline: punctuation, marks, subscripts. These are
        # judged on fill alone.
        return "NARROW" if ink < cell * NARROW_FRACTION else "OK"

    ratio = serif / body if body else 0
    if ratio >= PADDED_RATIO and ink > cell * 0.6:
        return "PADDED"
    if ink < cell * NARROW_FRACTION:
        return "NARROW"
    return "OK"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Mono.ufo")
    parser.add_argument("--tsv", action="store_true", help="machine-readable output")
    parser.add_argument("--only", help="restrict to a comma-separated glyph list")
    args = parser.parse_args()

    font = ufoLib2.Font.open(args.src)
    cell = 1228

    names = args.only.split(",") if args.only else [g.name for g in font]

    rows = []
    for name in names:
        glyph = font.get(name)
        if glyph is None or glyph.width == 0:
            continue
        measurement = measure(font, glyph)
        if measurement is None:
            continue
        verdict = classify(measurement, cell)
        rows.append((name, measurement, verdict))

    if args.tsv:
        print("glyph\tink\tserif\tbody\tratio\tverdict")
        for name, m, verdict in rows:
            ratio = m["serif"] / m["body"] if m["body"] else 0
            print(f"{name}\t{m['ink']:.0f}\t{m['serif']:.0f}\t{m['body']:.0f}\t{ratio:.2f}\t{verdict}")
        return

    buckets = {}
    for name, m, verdict in rows:
        buckets.setdefault(verdict, []).append((name, m))

    for verdict in ("PADDED", "NARROW", "OK"):
        entries = buckets.get(verdict, [])
        print(f"\n=== {verdict} ({len(entries)}) ===")
        if verdict == "OK":
            continue
        entries.sort(key=lambda e: -(e[1]["serif"] / max(e[1]["body"], 1)))
        for name, m in entries[:60]:
            ratio = m["serif"] / m["body"] if m["body"] else 0
            print(f"  {name:22} ink={m['ink']:6.0f} serif={m['serif']:6.0f} "
                  f"body={m['body']:6.0f} ratio={ratio:5.2f}")
        if len(entries) > 60:
            print(f"  ... and {len(entries) - 60} more")


if __name__ == "__main__":
    main()
