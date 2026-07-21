#!/usr/bin/env python3
"""Generate the Rub el Hizb and its nine-pointed Bahá'í variants into the seed.

U+06DE ARABIC START OF RUB EL HIZB is classically two overlapping squares —
an eight-pointed star. The nine-pointed star has its own codepoint, U+1F7D9
NINE POINTED WHITE STAR, whose reference form is exactly the three
overlapping triangles. This face is a Bahá'í face, so both are drawn, plus
two alternates on stylistic sets:

    uni06DE        two overlapping squares, stroked   (the standard sign)
    u1F7D9         three overlapping stroked triangles (the encoded star)
    u1F7D9.solid   one big solid nine-pointed star            (ss02)
    uni06DE.rub9   the triangles at sign size, with a nuqta
                   in the centre — rub-el-hizb style          (ss03)

All strokes are one pen (141 units): the sign is drawn by the same reed as
the letters. The centre dot of the rub9 variant is exactly one nuqta (271
across) — the module the whole face is measured in, sitting at the heart of
the nine-pointed star.

Geometry is generated, not drawn, so it is exactly regular; the glyphs are
written into the MONO SEED and flow through the whole transform chain like
everything else (they have no joins, no flat runs and no tails, so every
pass leaves them alone except corner softening, which keeps their points
sharp — a star's spike is past max_turn, like the apex of A).

Idempotent: re-running replaces the four glyphs and the marked feature block.

Usage:
    python3 scripts/make-stars.py            # writes sources/QalamBadi-Mono.ufo
"""

import argparse
import math
import re

import pathops
import ufoLib2

PEN = 141
NUQTA = 271

BEGIN = "# BEGIN generated star variants (scripts/make-stars.py)"
END = "# END generated star variants"

FEATURES = f"""
{BEGIN}
feature ss02 {{
    featureNames {{ name "Nine-pointed star, solid"; }};
    sub u1F7D9 by u1F7D9.solid;
}} ss02;

feature ss03 {{
    featureNames {{ name "Nine-pointed Rub el Hizb (with nuqta)"; }};
    sub uni06DE by uni06DE.rub9;
}} ss03;
{END}
"""


def ring(pen, points):
    pen.moveTo(points[0])
    for pt in points[1:]:
        pen.lineTo(pt)
    pen.closePath()


def polygon(centre, radius, sides, rotation_degrees):
    cx, cy = centre
    pts = []
    for i in range(sides):
        a = math.radians(rotation_degrees + 90) + 2 * math.pi * i / sides
        pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return pts


def star(centre, outer, inner, points, rotation_degrees=0):
    cx, cy = centre
    pts = []
    for i in range(points * 2):
        r = outer if i % 2 == 0 else inner
        a = math.radians(rotation_degrees + 90) + math.pi * i / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def circle(pen, centre, radius):
    """A circle from four cubic arcs."""
    k = 0.5523 * radius
    cx, cy = centre
    pen.moveTo((cx + radius, cy))
    pen.curveTo((cx + radius, cy + k), (cx + k, cy + radius), (cx, cy + radius))
    pen.curveTo((cx - k, cy + radius), (cx - radius, cy + k), (cx - radius, cy))
    pen.curveTo((cx - radius, cy - k), (cx - k, cy - radius), (cx, cy - radius))
    pen.curveTo((cx + k, cy - radius), (cx + radius, cy - k), (cx + radius, cy))
    pen.closePath()


def stroke_rings(rings_points, width=PEN * 0.5):
    """Union of the given centreline rings, stroked.

    Half a pen, not a full one: nine line crossings inside one em need air
    between them, and at the sign's radius a 141-unit stroke inks the whole
    middle annulus solid. Half a pen is the reed turned on its edge — the
    sign is drawn finer than the letters, as interlaced signs always are.
    """
    result = pathops.Path()
    for pts in rings_points:
        path = pathops.Path()
        ring(path.getPen(), pts)
        path.stroke(width, pathops.LineCap.BUTT_CAP, pathops.LineJoin.MITER_JOIN, 12)
        result = pathops.op(result, path, pathops.PathOp.UNION, fix_winding=True)
    return result


def write_glyph(font, name, path_or_pts, unicode_value=None, advance=None, filled_pts=None):
    if name in font:
        del font[name]
    glyph = font.newGlyph(name)
    if unicode_value is not None:
        glyph.unicodes = [unicode_value]
    if filled_pts is not None:
        path = pathops.Path()
        for pts in filled_pts:
            ring(path.getPen(), pts)
        path = pathops.simplify(path, fix_winding=True)
    else:
        path = path_or_pts
    path.draw(glyph.getPen())
    bounds = glyph.getBounds(font)
    glyph.width = advance if advance is not None else round(bounds.xMax + bounds.xMin)
    return glyph


# Glyph names from earlier iterations of this script that must not linger.
# The nine-pointed star was first drawn as uni06DE.star9/.tri9 before it was
# given its own codepoint U+1F7D9; leaving those behind ships dead, unencoded
# glyphs. Deleting them here keeps re-runs honest.
LEGACY_NAMES = ("uni06DE.star9", "uni06DE.tri9")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Mono.ufo")
    args = parser.parse_args()

    font = ufoLib2.Font.open(args.src)

    for legacy in LEGACY_NAMES:
        if legacy in font:
            del font[legacy]

    # The seed is monospace: everything gets the cell advance, centred.
    cell = 1228
    centre = (cell / 2, 500)

    # The standard sign: two overlapping squares, an eight-pointed star.
    squares = stroke_rings([
        polygon(centre, 440, 4, 0),
        polygon(centre, 440, 4, 45),
    ])
    write_glyph(font, "uni06DE", squares, unicode_value=0x06DE, advance=cell)

    # The encoded nine-pointed star: three overlapping stroked triangles.
    triangles = stroke_rings([
        polygon(centre, 560, 3, 0),
        polygon(centre, 560, 3, 40),
        polygon(centre, 560, 3, 80),
    ])
    write_glyph(font, "u1F7D9", triangles, unicode_value=0x1F7D9, advance=cell)

    # Its solid alternate: one big filled nine-pointed star.
    write_glyph(font, "u1F7D9.solid", None, advance=cell,
                filled_pts=[star(centre, 610, 295, 9)])

    # The same interlace at sign size, with one nuqta at its heart.
    rub = stroke_rings([
        polygon(centre, 440, 3, 0),
        polygon(centre, 440, 3, 40),
        polygon(centre, 440, 3, 80),
    ])
    dot = pathops.Path()
    circle(dot.getPen(), centre, NUQTA / 2)
    rub = pathops.op(rub, dot, pathops.PathOp.UNION, fix_winding=True)
    write_glyph(font, "uni06DE.rub9", rub, advance=cell)

    # Feature block, replaced idempotently.
    fea = font.features.text or ""
    if BEGIN in fea:
        fea = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?",
                     FEATURES.strip() + "\n", fea, flags=re.S)
    else:
        fea = fea.rstrip() + "\n" + FEATURES
    font.features.text = fea

    font.save(args.src, overwrite=True)
    print("wrote uni06DE, u1F7D9 and their alternates (ss02, ss03) -> " + args.src)


if __name__ == "__main__":
    main()
