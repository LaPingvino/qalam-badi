"""Narrow the harakat toward classical width so they fit over a letter.

The seed drew the vowel marks cell-wide — a fatha 2.1 nuqta, a shadda 2.5, a
dammatan 2.9 — but a mark is zero-width, so all that ink hangs over the letter
and past its advance. On a thin letter (lam.init is 315 units, alef 357) the
mark overflows by more than a nuqta each side and collides with the next
letter's marks. A reed pen draws the harakat compact: a fatha is a short dash,
not a plank.

This scales each wide mark in x toward its own centre, to a target width in
nuqta, so it still centres over its letter (mark-anchors, which runs after,
re-reads the narrowed ink) but no longer spills into the neighbour. Only x is
touched and only the marks — the letters keep their monolinear stroke; a mark
is small enough that the slight steepening of its dash reads as a written
haraka, not a distortion. It runs once on the Regular; the derived masters copy
the narrowed marks.

Usage:
    python3 scripts/narrow-marks.py --src sources/QalamBadi-Regular.ufo
"""

import argparse

import ufoLib2
import yaml

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)

# Target widths in nuqta, per mark. Marks not listed but wider than the floor
# get the default. Classical harakat are compact — a fatha about 1.3 dots, a
# shadda under 2, the tanwin a touch wider because they are two marks.
# Modest: keep the mark's character, just take the worst of the cell width off.
TARGETS = {
    0x064E: 1.65, 0x0650: 1.65,             # fatha, kasra  (2.11 -> 1.65)
    0x064F: 1.45,                            # damma         (1.54 -> 1.45)
    0x0651: 2.05,                            # shadda        (2.54 -> 2.05)
    0x0652: 1.65,                            # sukun         (1.87 -> 1.65)
    0x064B: 1.75, 0x064D: 1.75,             # fathatan, kasratan
    0x064C: 2.35,                            # dammatan      (2.88 -> 2.35)
}
DEFAULT_TARGET = 1.85     # nuqta, for any other wide mark
FLOOR = 300               # leave marks already narrower than this alone


def in_arabic(cp):
    return cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    nuqta = config["module"]["nuqta"]

    font = ufoLib2.Font.open(args.src)

    narrowed = 0
    for glyph in font:
        if glyph.width != 0 or not glyph.contours or not in_arabic(glyph.unicode):
            continue
        bounds = glyph.getBounds(font)
        if bounds is None:
            continue
        width = bounds.xMax - bounds.xMin
        if width <= FLOOR:
            continue
        target = TARGETS.get(glyph.unicode, DEFAULT_TARGET) * nuqta
        if width <= target:
            continue
        scale = target / width
        centre = (bounds.xMin + bounds.xMax) / 2
        for contour in glyph.contours:
            for point in contour.points:
                point.x = centre + (point.x - centre) * scale
        narrowed += 1
        if args.verbose:
            print(f"  {glyph.name}: {width:.0f} -> {target:.0f} (x{scale:.2f})")

    font.save(args.src, overwrite=True)
    print(f"narrowed {narrowed} harakat -> {args.src}")


if __name__ == "__main__":
    main()
