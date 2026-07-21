#!/usr/bin/env python3
"""Tuck below-base dots up inside the descender so renderers cannot clip them.

Reported as ya being cut off, and first misdiagnosed as the tail: in final yeh
the BODY only reaches y=-481 — it is the two dots below that hang at -1024,
190 units past the -838 typo/hhea descender, so any renderer that clips to
line metrics cuts them. About twenty glyphs inherit the same placement from
the seed: Farsi yeh variants, the sheen-below family, noon and beh variants
with dots or marks beneath.

The deep placement is a cell artifact. The monospace design parked the dots
low enough to clear the deepest possible tail anywhere in the cell, leaving
~250 units of air between letter and dot; a written hand tucks the dots in
just under the letter. So the fix and the style agree: raise each below-dot
group until it clears the descender, stopping short of the ink above it.

Dots are shapes, so the group is TRANSLATED as one rigid body — never scaled,
never re-spaced internally (a staggered pair keeps its stagger). The ceiling
is measured from the actual ink above the group's x range, not from bounding
boxes, so a tail sweeping elsewhere in the glyph does not block the shift.

Glyphs that reach their dots through components get the component offset
moved instead of the outline, and component SOURCES are left alone so nothing
shifts twice.

Usage:
    python3 scripts/tuck-dots.py --src sources/QalamBadi-Softened.ufo \
                                 --out sources/QalamBadi-Tucked.ufo
"""

import argparse
import os
import shutil

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_classify = SourceFileLoader(
    "classify_widths", os.path.join(_here, "classify-widths.py")).load_module()
_joins = SourceFileLoader("joins", os.path.join(_here, "joins.py")).load_module()

PolygonPen = _classify.PolygonPen

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)

# A contour is only a candidate if it is dot-sized AND entirely below this
# line. The deepest letter ink in the face is the yeh tail at -481; ordinary
# below-dots (beh's, at -289..0) sit above this and are exactly where a dot
# should be, so they must not move.
DEEP = -350

# Dot-sized: the nuqta is 271x289 and the largest dot cluster stays inside
# 1.35 nuqta per axis, same figure the connector fitter uses.
DOT_LIMIT_FACTOR = 1.35


def is_arabic(glyph):
    cp = glyph.unicode
    if cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def ceiling_above(polygons, x0, x1, top, step=12):
    """Bottom edge of the lowest ink above `top` within [x0, x1], or None."""
    ceiling = None
    x = x0
    while x <= x1:
        for span_bottom, span_top in _joins.spans_at(polygons, x):
            if span_bottom > top and (ceiling is None or span_bottom < ceiling):
                ceiling = span_bottom
        x += step
    return ceiling


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Softened.ufo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    nuqta = config["module"]["nuqta"]
    settings = config.get("dots") or {}
    min_gap = settings.get("min_gap", 0.09) * nuqta
    dot_limit = nuqta * DOT_LIMIT_FACTOR

    font = ufoLib2.Font.open(args.src)

    # The floor is the font's own declared descender: ink above it survives
    # every line-metrics clip. Read, not hardcoded, for the usual reason.
    floor = font.info.openTypeOS2TypoDescender or font.info.descender
    if floor is None:
        raise SystemExit("font declares no descender; nothing to tuck against")

    tucked = 0
    partial = []
    for glyph in font:
        if not is_arabic(glyph) or glyph.width == 0:
            continue

        # Collect the below-dot items: outline contours, and components whose
        # realized bounds are dot-sized and deep. Component sources themselves
        # are not Arabic-named, so they fall out of the loop above.
        items = []  # (kind, object, ymin, ymax, xmin, xmax)
        for contour in glyph.contours:
            xs = [p.x for p in contour.points]
            ys = [p.y for p in contour.points]
            if not xs:
                continue
            if (max(xs) - min(xs) <= dot_limit and max(ys) - min(ys) <= dot_limit
                    and max(ys) < DEEP):
                items.append(("contour", contour, min(ys), max(ys), min(xs), max(xs)))
        for component in glyph.components:
            base = font.get(component.baseGlyph)
            if base is None:
                continue
            bounds = base.getBounds(font)
            if bounds is None:
                continue
            xx, xy, yx, yy, dx, dy = component.transformation
            ymin, ymax = bounds.yMin * yy + dy, bounds.yMax * yy + dy
            xmin, xmax = bounds.xMin * xx + dx, bounds.xMax * xx + dx
            if ymin > ymax:
                ymin, ymax = ymax, ymin
            if xmin > xmax:
                xmin, xmax = xmax, xmin
            if (xmax - xmin <= dot_limit and ymax - ymin <= dot_limit
                    and ymax < DEEP):
                items.append(("component", component, ymin, ymax, xmin, xmax))

        if not items:
            continue
        group_bottom = min(item[2] for item in items)
        if group_bottom >= floor:
            continue
        group_top = max(item[3] for item in items)
        x0 = min(item[4] for item in items)
        x1 = max(item[5] for item in items)

        wanted = floor - group_bottom

        pen = PolygonPen(font)
        glyph.draw(pen)
        ceiling = ceiling_above(pen.polygons, x0, x1, group_top)
        allowed = (ceiling - min_gap - group_top) if ceiling is not None else wanted
        shift = min(wanted, max(0.0, allowed))
        if shift < 1:
            partial.append((glyph.name, 0.0, wanted))
            continue

        for kind, obj, *_ in items:
            if kind == "contour":
                for point in obj.points:
                    point.y += shift
            else:
                xx, xy, yx, yy, dx, dy = obj.transformation
                obj.transformation = (xx, xy, yx, yy, dx, dy + shift)
        tucked += 1
        if shift < wanted - 1:
            partial.append((glyph.name, shift, wanted))
        if args.verbose:
            print(f"  {glyph.name:16} dots {group_bottom:6.0f} -> {group_bottom + shift:6.0f}"
                  f"  (+{shift:.0f}{'' if shift >= wanted - 1 else f', wanted {wanted:.0f}'})")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)

    print(f"tucked below-dots in {tucked} glyphs above the {floor:.0f} descender"
          f" -> {args.out}")
    for name, got, wanted in partial:
        print(f"  WARNING {name}: letter ink allows only +{got:.0f} of the "
              f"+{wanted:.0f} needed; still clips by {wanted - got:.0f}")


if __name__ == "__main__":
    main()
