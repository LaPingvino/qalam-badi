#!/usr/bin/env python3
"""Write group (class) kerning into the UFO, from the design record.

Sidebearings set an even rhythm; they cannot correct the optical white that
only appears between particular shapes — the triangular hole at AV, the gap
of T over a following o, W over a, r before a period. That is what kerning is
for, and the font shipped with none at all.

The pairs live in sources/spacing.yaml (kerning:), in nuqta, so they stay as
legible and design-recorded as the sidebearings. This writes them into the UFO
as public.kern1/public.kern2 groups plus a kerning table; the build compiles
that to GPOS on its own, and make-bold / make-italic carry it into the derived
masters because it is part of the font object they copy.

It runs LAST in the proportional chain, on the finished Regular, because that
chain regenerates the Regular from the seed every time — kerning written any
earlier, or by hand into the UFO, would be overwritten on the next build.

Groups are lists mixing codepoints (ints, resolved through the font's cmap so
Cyrillic and Greek join their Latin shape-mates) and literal glyph names.

Usage:
    python3 scripts/kern.py --src sources/QalamBadi-Regular.ufo
"""

import argparse

import ufoLib2
import yaml


def resolve(members, cmap, font):
    """Turn a group's [codepoint | glyph-name] list into present glyph names."""
    names = []
    for member in members:
        if isinstance(member, int):
            name = cmap.get(member)
            if name is not None:
                names.append(name)
        elif member in font:
            names.append(member)
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    nuqta = config["module"]["nuqta"]
    settings = config.get("kerning") or {}
    group_defs = settings.get("groups") or {}
    pairs = settings.get("pairs") or []

    font = ufoLib2.Font.open(args.src)
    cmap = {g.unicode: g.name for g in font if g.unicode is not None}

    # Resolve each named group to the glyphs actually present.
    members = {name: resolve(defn, cmap, font) for name, defn in group_defs.items()}

    # A group used on the left becomes public.kern1.<name>; on the right,
    # public.kern2.<name>. Emit both for every group so either side can use it;
    # empty ones are skipped.
    groups = {}
    for name, glyphs in members.items():
        if not glyphs:
            continue
        groups[f"public.kern1.{name}"] = list(glyphs)
        groups[f"public.kern2.{name}"] = list(glyphs)

    def side(token, prefix):
        """A pair token is a group name (-> class) or a literal glyph."""
        if token in members:
            return f"{prefix}.{token}" if members[token] else None
        return token if token in font else None

    kerning = {}
    dropped = 0
    for left, right, value in pairs:
        left_ref = side(left, "public.kern1")
        right_ref = side(right, "public.kern2")
        if left_ref is None or right_ref is None:
            dropped += 1
            continue
        kerning[(left_ref, right_ref)] = round(value * nuqta)

    # Merge, keeping any hand groups/kerning the UFO might already carry.
    font.groups.update(groups)
    font.kerning.update(kerning)
    font.save(args.src, overwrite=True)

    print(f"wrote {len(kerning)} kern pairs over {len(groups) // 2} classes"
          + (f" ({dropped} pairs skipped: glyphs absent)" if dropped else "")
          + f" -> {args.src}")
    if args.verbose:
        for (l, r), v in sorted(kerning.items()):
            print(f"  {l:24} {r:24} {v:+5}")


if __name__ == "__main__":
    main()
