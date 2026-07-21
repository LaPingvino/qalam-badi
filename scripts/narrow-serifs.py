#!/usr/bin/env python3
"""Pull in the serifs that were stretched to fill the monospace cell.

Courier's `i` is one 141-unit stem carrying serifs 910 units across. That is not
a design decision, it is the cell: every glyph had to be the same width, so the
narrow letters grew slabs until they reached the walls. Re-spacing the font
cannot fix it — the ink genuinely is that wide — so `i` would stay within a
whisker of `m` and the face would still read as a typewriter.

So we narrow the outline itself, and we do it in the way that preserves the
thing the design rests on:

    The stem is pinned. Only the flanks either side of it are compressed.

x is remapped piecewise-linearly — identity inside the stem, linearly squeezed
outside it. Consequences, all of them deliberate:

  * Vertical stroke width is mathematically unchanged, so the face stays
    monolinear. This is the whole reason for anchoring on the stem rather than
    scaling the glyph.
  * Serif brackets compress smoothly along with their flank instead of kinking,
    which is what happens if you drag the outermost points and leave the
    control points behind.
  * Horizontal strokes (the serif slab itself, the crossbar of T, the arm of E)
    get shorter, never thinner: their weight is a vertical measurement and x
    does not touch it.

Targets are ink widths in nuqta, declared in sources/spacing.yaml. Glyphs not
named there keep the width they inherited — most of the alphabet was always
about the right width and only the single-stem letters were badly distorted.

Usage:
    python3 scripts/narrow-serifs.py --src sources/QalamBadi-Mono.ufo \
                                     --out sources/QalamBadi-Narrowed.ufo
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

PolygonPen = _classify.PolygonPen


def stem_interval(font, glyph):
    """The x-range of the letter's body, measured clear of the serif bands.

    Returned as (left, right). This is what stays fixed while the flanks move.
    """
    pen = PolygonPen(font)
    glyph.draw(pen)
    if not pen.polygons:
        return None

    x_height = font.info.xHeight or 924
    bounds = glyph.getBounds(font)
    if bounds is None:
        return None

    # Sample several heights through the body and take the tightest reading, so
    # a stray terminal or a dot does not get mistaken for the stem.
    best = None
    for fraction in (0.40, 0.50, 0.55, 0.62):
        y = x_height * fraction
        crossings = _crossings(pen.polygons, y)
        if len(crossings) < 2:
            continue
        span = (min(crossings), max(crossings))
        if best is None or (span[1] - span[0]) < (best[1] - best[0]):
            best = span
    return best


def _crossings(polygons, y):
    out = []
    for poly in polygons:
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if y0 == y1:
                continue
            if (y0 <= y < y1) or (y1 <= y < y0):
                t = (y - y0) / (y1 - y0)
                out.append(x0 + t * (x1 - x0))
    return out


def make_remap(x_min, x_max, stem_left, stem_right, target_ink):
    """Build the piecewise-linear x mapping. Returns None if nothing to do."""
    ink = x_max - x_min
    if target_ink >= ink:
        return None

    left_flank = stem_left - x_min
    right_flank = x_max - stem_right
    flank_total = left_flank + right_flank
    if flank_total <= 1:
        return None  # no flanks to give; the letter is all stem

    remove = ink - target_ink
    if remove > flank_total * 0.92:
        # Refuse to collapse the serifs entirely — that is a redraw, not a fit,
        # and it would destroy the slab that gives the face its character.
        remove = flank_total * 0.92

    left_scale = (left_flank - remove * (left_flank / flank_total)) / left_flank if left_flank > 1 else 1.0
    right_scale = (right_flank - remove * (right_flank / flank_total)) / right_flank if right_flank > 1 else 1.0

    def remap(x):
        if x < stem_left:
            return stem_left - (stem_left - x) * left_scale
        if x > stem_right:
            return stem_right + (x - stem_right) * right_scale
        return x

    return remap


def apply_remap(glyph, remap):
    for contour in glyph.contours:
        for point in contour.points:
            point.x = remap(point.x)
    # Components are translated, not remapped: a component is another glyph that
    # has been (or will be) narrowed on its own terms. Remapping it here would
    # narrow it twice. We move it so it stays centred over the narrowed base.
    for component in glyph.components:
        xx, xy, yx, yy, dx, dy = component.transformation
        component.transformation = (xx, xy, yx, yy, remap(dx), dy)
    for anchor in glyph.anchors:
        anchor.x = remap(anchor.x)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Mono.ufo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)

    nuqta = config["module"]["nuqta"]
    targets = config.get("ink_targets") or {}

    font = ufoLib2.Font.open(args.src)

    narrowed = 0
    skipped = []
    for name, target_nuqta in targets.items():
        glyph = font.get(name)
        if glyph is None:
            skipped.append((name, "absent"))
            continue

        bounds = glyph.getBounds(font)
        if bounds is None:
            skipped.append((name, "no ink"))
            continue

        stem = stem_interval(font, glyph)
        if stem is None:
            skipped.append((name, "no stem found"))
            continue

        target_ink = target_nuqta * nuqta
        remap = make_remap(bounds.xMin, bounds.xMax, stem[0], stem[1], target_ink)
        if remap is None:
            skipped.append((name, "already narrow enough"))
            continue

        before = bounds.xMax - bounds.xMin
        apply_remap(glyph, remap)
        after = glyph.getBounds(font)
        narrowed += 1
        if args.verbose:
            print(f"  {name:14} {before:6.0f} -> {after.xMax - after.xMin:6.0f} "
                  f"(target {target_ink:.0f}, stem {stem[0]:.0f}..{stem[1]:.0f})")

    if os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out)

    print(f"narrowed {narrowed} glyphs -> {args.out}")
    if skipped and args.verbose:
        for name, why in skipped:
            print(f"  skipped {name}: {why}")


if __name__ == "__main__":
    main()
