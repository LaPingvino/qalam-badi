#!/usr/bin/env python3
"""Anchor the Arabic harakat to their letters, so marks sit above and stack.

The seed draws every haraka at a FIXED height as a zero-width overlay. On a
short tooth that is fine; on a tall lam or alef the mark lands on the stem, and
a shadda plus a vowel land on top of each other — the marks collide because
nothing tells them where their letter's top actually is.

This adds attachment anchors and lets ufo2ft compile them into `mark` and
`mkmk` GPOS:

  base letters      get a `top` anchor a small gap above their own ink, and a
                    `bottom` anchor below it, both centred over the letter body
                    (the ink above the connector, so the mark sits over the
                    tooth/loop, not the join).
  above-marks       get `_top` (their foot, which lands on the base's `top`)
                    and `top` (their crown, so the next mark stacks above via
                    mkmk).
  below-marks       get `_bottom` and `bottom`, mirrored.

So a shadda floats above whatever letter it is on — the lam's real 1287 top,
not a fixed 1128 — and a following vowel stacks above the shadda instead of
through it.

Usage:
    python3 scripts/mark-anchors.py --src sources/QalamBadi-Regular.ufo
"""

import argparse
import os
import re

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_flatness = SourceFileLoader(
    "classify_flatness",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "classify-flatness.py"),
).load_module()

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)

# Gap above the letter before the first mark, and between stacked marks.
BASE_GAP = 80
STACK_GAP = 45


def in_arabic(cp):
    return cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS)


def is_arabic_name(glyph):
    if in_arabic(glyph.unicode):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def body_centre(glyph, font, above=True):
    """x where a mark should centre — over the letter body, not the connector.

    The connector lives in the join band (y 225..369); the body rises above it
    (or, for below-marks, we just take the whole-ink centre). Averaging the ink
    outside the join band keeps a mark over the tooth/loop rather than sliding
    onto the connector stub."""
    xs = []
    for contour in glyph.contours:
        for p in contour.points:
            if p.type is None:
                continue
            if above and p.y > 420:
                xs.append(p.x)
            elif not above and p.y < 200:
                xs.append(p.x)
    if not xs:
        bounds = glyph.getBounds(font)
        return (bounds.xMin + bounds.xMax) / 2
    return (min(xs) + max(xs)) / 2


def set_anchor(glyph, name, x, y):
    glyph.anchors = [a for a in glyph.anchors if a.name != name]
    glyph.appendAnchor({"name": name, "x": round(x), "y": round(y)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        settings = (yaml.safe_load(handle).get("marks") or {})
    # Thin, offset-stem letters whose marks overhang the neighbour: nudge their
    # marks from the stem toward the letter's footprint (advance) centre. A
    # short manual class; symmetric letters need no nudge and are left out.
    thin_letters = set(settings.get("thin_letters") or [])
    thin_pull = settings.get("thin_pull", 0.0)

    font = ufoLib2.Font.open(args.src)

    bases = marks_above = marks_below = 0
    for glyph in font:
        if not glyph.contours or not is_arabic_name(glyph):
            continue
        bounds = glyph.getBounds(font)
        if bounds is None:
            continue
        cx = (bounds.xMin + bounds.xMax) / 2

        if glyph.width == 0:
            # A mark. Above or below by where its ink sits.
            above = (bounds.yMin + bounds.yMax) / 2 > 300
            if above:
                set_anchor(glyph, "_top", cx, bounds.yMin)          # foot -> base top
                set_anchor(glyph, "top", cx, bounds.yMax + STACK_GAP)  # crown -> next mark
                marks_above += 1
            else:
                set_anchor(glyph, "_bottom", cx, bounds.yMax)
                set_anchor(glyph, "bottom", cx, bounds.yMin - STACK_GAP)
                marks_below += 1
        else:
            # A base letter. Centre the mark over the body (the stem/loop); for
            # the thin-letter class, pull it toward the glyph's footprint
            # (advance) centre so it stops overhanging the neighbour.
            base, _ = _flatness.base_and_form(glyph)
            pull = thin_pull if base in thin_letters else 0.0
            advance_centre = glyph.width / 2
            top_x = body_centre(glyph, font, above=True)
            bot_x = body_centre(glyph, font, above=False)
            set_anchor(glyph, "top", top_x + pull * (advance_centre - top_x),
                       bounds.yMax + BASE_GAP)
            set_anchor(glyph, "bottom", bot_x + pull * (advance_centre - bot_x),
                       bounds.yMin - BASE_GAP)
            bases += 1

    # The arabic-features tool emits an explicit `table GDEF` that declares
    # ONLY the mark class. With it present, ufo2ft treats the letters as
    # unclassified and refuses to generate the base->mark `mark` feature (only
    # mark->mark mkmk). Dropping just that table — the @GDEF_Marks glyph class
    # the join lookups reference stays — lets ufo2ft rebuild GDEF from the mark
    # anchors and emit both mark and mkmk. Done on the generated Regular only,
    # so the seed's features are untouched and it re-applies every build.
    fea = font.features.text or ""
    stripped = re.sub(r"table GDEF \{.*?\} GDEF;\n?", "", fea, flags=re.S)
    if stripped != fea:
        font.features.text = stripped

    font.save(args.src, overwrite=True)
    print(f"anchored {bases} Arabic bases, {marks_above} above-marks, "
          f"{marks_below} below-marks; GDEF handed to ufo2ft -> {args.src}")


if __name__ == "__main__":
    main()
