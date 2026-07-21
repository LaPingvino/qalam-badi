"""Widen the word-end alif so its mark clears the next group.

The alif is a thin vertical whose stem sits at its free end, so a mark centred
on it overhangs past the advance into the following group — and the alif is
symmetric, so the footprint nudge cannot move it. The room has to go on the
FREE side (the x=0 end, where the mark hangs off and the following group
abuts), never on the join side.

The alif's connecting foot sits at the advance edge (high x): a final form
joins the preceding letter there, and the shaper abuts that neighbour exactly
at the alif's advance. So growing the advance alone opens a white gap at the
join — the neighbour steps back by the widen but the connector ink does not
follow it (measured at 114 units on بـا). The fix is a rigid translation:
shift the whole outline right by the same amount the advance grows, so the
connector foot stays glued to the advance edge while the free side — stem,
mark and all — gains the clearance. Translating the shape whole (never
remapping its points) is exactly what the one design rule demands.

Only the alif family, and only the final/isolated forms (the ones that end a
group); medial forms do not exist for the alif. In nuqta.

Runs once on the Regular before mark-anchors; the derived masters copy the
widened advance and shifted outline.

Usage:
    python3 scripts/widen-marked.py --src sources/QalamBadi-Regular.ufo
"""

import argparse
import os

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_flatness = SourceFileLoader(
    "classify_flatness",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "classify-flatness.py"),
).load_module()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        settings = (yaml.safe_load(handle).get("marks") or {})
    nuqta = yaml.safe_load(open(args.config))["module"]["nuqta"]
    letters = set(settings.get("widen_letters") or [])
    widen = round(settings.get("widen", 0.0) * nuqta)
    if not letters or widen <= 0:
        print("widen-marked: nothing to do (marks.widen / widen_letters unset)")
        return

    font = ufoLib2.Font.open(args.src)

    widened = 0
    for glyph in font:
        base, form = _flatness.base_and_form(glyph)
        if base not in letters or form not in ("fina", "isol"):
            continue
        if glyph.width <= 0:
            continue
        # Rigid translation right by `widen`, then grow the advance to match:
        # the connector foot at the advance edge stays glued to the neighbour,
        # and the free side gains the room. Move contours, components (they
        # carry their own offset) and anchors together so the shape stays whole.
        for contour in glyph.contours:
            for point in contour.points:
                point.x += widen
        for component in glyph.components:
            xx, xy, yx, yy, dx, dy = component.transformation
            component.transformation = (xx, xy, yx, yy, dx + widen, dy)
        for anchor in glyph.anchors:
            anchor.x += widen
        glyph.width += widen
        widened += 1
        if args.verbose:
            print(f"  {glyph.name}: shift +{widen}, width -> {glyph.width}")

    font.save(args.src, overwrite=True)
    print(f"widened {widened} word-end alif forms by {widen} -> {args.src}")


if __name__ == "__main__":
    main()
