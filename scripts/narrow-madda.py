#!/usr/bin/env python3
"""Narrow the madda to suit the shortened alef.

The madda is drawn 944 units wide in the seed — cell width minus margins —
and no transform ever narrowed it, while the vertical work brought the alef
it sits on down from 5.45 to 3.6 nuqta. The mark kept its monospace width
over a letter that shrank, so آ reads top-heavy: the proportion drifted even
though the madda itself never moved.

The madda is a horizontal stroke — a flattened alef — so the connector
corollary applies: its thickness is a vertical measurement, and compressing
it in x changes no stroke weight anywhere. It is scaled about its own centre
so it stays centred over whatever carries it, and composites referencing the
combining mark inherit the narrowing from the source.

Usage:
    python3 scripts/narrow-madda.py --src sources/QalamBadi-Tucked.ufo \
                                    --out sources/QalamBadi-Madda.ufo
"""

import argparse
import os
import shutil

import ufoLib2
import yaml

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)

# A madda stroke: very wide, thin, and high above the letter. The seed draws
# every instance 944 units wide with its ink entirely above y=900.
MIN_WIDTH = 800
MIN_Y = 900


def is_arabic(glyph):
    cp = glyph.unicode
    if cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    nuqta = config["module"]["nuqta"]
    target = (config.get("marks") or {}).get("madda")
    if not target:
        raise SystemExit("no marks.madda width in spacing.yaml; nothing to do")
    target_units = target * nuqta

    font = ufoLib2.Font.open(args.src)

    narrowed = 0
    for glyph in font:
        if not glyph.contours:
            continue
        if not (is_arabic(glyph) or glyph.width == 0):
            continue
        for contour in glyph.contours:
            xs = [p.x for p in contour.points]
            ys = [p.y for p in contour.points]
            if not xs:
                continue
            width = max(xs) - min(xs)
            if width < MIN_WIDTH or min(ys) < MIN_Y:
                continue
            if width <= target_units:
                continue
            centre = (min(xs) + max(xs)) / 2
            scale = target_units / width
            for point in contour.points:
                point.x = centre + (point.x - centre) * scale
            narrowed += 1
            if args.verbose:
                print(f"  {glyph.name:16} madda {width:.0f} -> {target_units:.0f}")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)
    print(f"narrowed {narrowed} madda strokes to {target:.2f} nuqta -> {args.out}")


if __name__ == "__main__":
    main()
