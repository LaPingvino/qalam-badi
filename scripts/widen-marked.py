"""Widen the word-end alif so its mark clears the next group.

The alif is a thin vertical whose stem sits at its free end, so a mark centred
on it overhangs past the advance into the following group — and the alif is
symmetric, so the footprint nudge cannot move it. The durable fix is to give
the alif a little more room on its free side: keep the stem and the join where
they are, just widen the advance, so the next group starts a touch further on
and the mark no longer collides with it.

Only the alif family, and only the final/isolated forms (the ones that end a
group); medial forms do not exist for the alif. In nuqta, added to the advance.

Runs once on the Regular before mark-anchors; the derived masters copy the
widened advance.

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
        glyph.width += widen
        widened += 1
        if args.verbose:
            print(f"  {glyph.name}: +{widen} -> {glyph.width}")

    font.save(args.src, overwrite=True)
    print(f"widened {widened} word-end alif forms by {widen} -> {args.src}")


if __name__ == "__main__":
    main()
