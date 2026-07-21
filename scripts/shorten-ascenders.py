#!/usr/bin/env python3
"""Bring the Arabic verticals down to nastaʿlīq proportion.

This is the single biggest lever on whether the Arabic reads as a written hand
or as a typeface with Arabic in it, and it is the one the monospace inheritance
argues hardest against.

The classical measure: the alef is **3 nuqṭa** in nastaʿlīq and **5-6 in naskh**.
Mishkín-Qalam's own Greatest Name measures **3.5**. The seed master's alef is
1252 units — **4.6 nuqṭa** — which is naskh country. Relative to a nastaʿlīq
hand, the verticals are too tall and everything horizontal is too small; the
proportion is close to inverted.

Pulling the alef down is not cosmetic. It resets what the whole script is
measured against, because in this system the tooth, the dāl and the bowl are all
expressed as fractions of the alef. Shorten it and the bowls and finals become
large relative to the verticals, which is exactly the nastaʿlīq silhouette:
low, wide, and swinging.

**How, without breaking monolinearity.** Scaling the glyph vertically would thin
every horizontal stroke, which is precisely the property this design cannot
spend. Instead y is remapped piecewise-linearly: identity through the body of
the letter, compressed only in the ascender region above it. A vertical stem
simply gets shorter — its horizontal width is untouched — and horizontal strokes
all live in the body region, so their thickness is untouched too. The transform
is the same one used on the Latin serif flanks and pointed at the other axis.

Usage:
    python3 scripts/shorten-ascenders.py --src sources/QalamBadi-Softened.ufo \
                                         --out sources/QalamBadi-Short.ufo
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


def is_arabic(glyph):
    cp = glyph.unicode
    if cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def make_y_remap(body_top, target_top, current_top):
    """Compress everything above body_top so current_top lands on target_top.

    Below body_top nothing moves, so bowls, teeth, connectors and every
    horizontal stroke keep their exact geometry and thickness.
    """
    span = current_top - body_top
    if span <= 1:
        return None
    scale = (target_top - body_top) / span
    if scale >= 0.995:
        return None

    def remap(y):
        if y <= body_top:
            return y
        return body_top + (y - body_top) * scale

    return remap


def apply_y(glyph, remap):
    for contour in glyph.contours:
        for point in contour.points:
            point.y = remap(point.y)
    for component in glyph.components:
        xx, xy, yx, yy, dx, dy = component.transformation
        component.transformation = (xx, xy, yx, yy, dx, remap(dy))
    for anchor in glyph.anchors:
        anchor.y = remap(anchor.y)


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
    settings = config.get("verticals") or {}
    target_nuqta = settings.get("alef", 3.5)
    body_nuqta = settings.get("body_top", 1.45)

    body_top = body_nuqta * nuqta

    font = ufoLib2.Font.open(args.src)

    # The alef sets the measure; everything else is brought down by the same
    # ratio so the script keeps its internal proportions.
    alef = font.get("uni0627")
    if alef is None:
        raise SystemExit("no alef (uni0627) — cannot establish the measure")
    alef_bounds = alef.getBounds(font)
    alef_top = alef_bounds.yMax
    # The measure is the alef's HEIGHT, not its topmost coordinate: this alef's
    # ink starts well above the baseline, so reading yMax as a height would
    # shorten it by that offset again and land far under the target.
    target_top = alef_bounds.yMin + target_nuqta * nuqta
    ratio = (target_top - body_top) / (alef_top - body_top)

    shortened = 0
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours:
            continue
        bounds = glyph.getBounds(font)
        if bounds is None or bounds.yMax <= body_top:
            continue

        glyph_target = body_top + (bounds.yMax - body_top) * ratio
        remap = make_y_remap(body_top, glyph_target, bounds.yMax)
        if remap is None:
            continue

        before = bounds.yMax
        apply_y(glyph, remap)
        shortened += 1
        if args.verbose and glyph.name in ("uni0627", "uni0644", "uni0643", "uniFEDF"):
            print(f"  {glyph.name:12} top {before:6.0f} -> {glyph_target:6.0f} "
                  f"({glyph_target / nuqta:.2f} nuqta)")

    if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out, overwrite=True)

    print(f"shortened {shortened} Arabic glyphs; alef {alef_top:.0f} -> "
          f"{target_top:.0f} units ({alef_top / nuqta:.2f} -> {target_nuqta} nuqta) "
          f"-> {args.out}")


if __name__ == "__main__":
    main()
