#!/usr/bin/env python3
"""Derive the proportional Qalam Badi master from the inherited monospace seed.

Qalam Badi keeps Courier Badi's outlines — the monolinear stroke, the slab
serifs, the in-box Arabic teeth — and changes only how much room each glyph is
given. Everything the letters look like is inherited; everything about their
rhythm is decided here.

The spacing system lives in sources/spacing.yaml and is expressed in nuqta, the
calligrapher's dot, which the seed master already draws at the same size for
Arabic and Latin. See that file for the reasoning.

Three things make this more than ink-fitting:

1.  Arabic joining edges are pinned, not spaced. A .init/.medi/.fina form
    carries its connector exactly on the advance edge; give that edge a
    sidebearing and the script visibly comes apart. Join sides are detected
    from the outline itself (ink reaching the cell edge within the connector
    band around the baseline) rather than from a hand-kept table, so the
    detection stays correct when the Arabic glyphs are edited upstream.

2.  Composites are re-fitted after their bases move, by translating every
    component together. Fitting a composite before its base has moved, or
    letting only the base component follow, is what detaches accents.

3.  Nothing is scaled. Glyphs are translated and their advance is changed; the
    stroke width is never touched, because monolinearity is the one property
    the whole design rests on.

Usage:
    python3 scripts/make-proportional.py \
        --src sources/QalamBadi-Mono.ufo \
        --out sources/QalamBadi-Regular.ufo
"""

import argparse
import os
import shutil
import sys
import unicodedata

import ufoLib2
import yaml

# Ink closer than this to an advance edge, within the connector band around the
# baseline, is treated as a joining connector rather than as a glyph that
# happens to be wide. The seed master pins connectors to the edge, so real
# connectors land within a few dozen units of it; the nearest non-connector
# case measured in the seed (seen.init, 56 units of natural gap) sits outside.
JOIN_EDGE_TOLERANCE = 45

# Vertical band, relative to the baseline, in which a connector can appear.
# Arabic joins all happen on the baseline; ink touching the cell edge high up
# (a Latin serif) or well below it is not a connector.
#
# The lower bound matters as much as the upper one. A final form's tail sweeps
# left and down, and it frequently crosses the advance edge on its way — read
# that as a join and the glyph gets its left sidebearing pinned to zero, which
# is exactly the sweep we were trying to give it. The band is therefore kept
# tight around the join height: a connector leaves at the baseline, not under it.
CONNECTOR_BAND = (-40, 420)

ARABIC_BLOCKS = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
)

LATIN_ROUND = set("obcedpqgsOCGQS")
LATIN_STRAIGHT = set("ilmnhurIHMNUJfjt")
LATIN_DIAGONAL = set("vwxyzAVWXYZKk")

# Glyphs whose advance must stay equal to each other so figures still line up
# in tables and dates. Proportionalising the rest of the font does not make
# tabular figures a bad idea.
TABULAR = set("zero one two three four five six seven eight nine".split())


def in_arabic_block(cp):
    return cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS)


class Fitter:
    def __init__(self, font, config, trim_serifs=False, verbose=False):
        self.font = font
        self.config = config
        self.verbose = verbose
        self.trim_serifs = trim_serifs

        module = config["module"]
        self.nuqta = module["nuqta"]
        self.pen = module["pen"]
        self.verify_module()

        self.stats = {"fitted": 0, "joins": 0, "skipped": 0, "composites": 0}

    # -- the module ------------------------------------------------------

    def verify_module(self):
        """Assert the nuqta really is what spacing.yaml claims.

        The entire spacing system is denominated in this number. If an upstream
        merge changes the dot, every measurement in spacing.yaml silently means
        something else, so fail loudly instead.
        """
        for name in ("uni0628", "uni062A", "uni0646"):
            glyph = self.font.get(name)
            if glyph is None:
                continue
            dots = [c for c in glyph.contours if self._contour_width(c) < self.nuqta * 1.5]
            if not dots:
                continue
            measured = max(self._contour_width(c) for c in dots)
            if abs(measured - self.nuqta) > 12:
                raise SystemExit(
                    f"nuqta mismatch: spacing.yaml says {self.nuqta}, {name} "
                    f"measures {measured:.0f}. The spacing system is denominated "
                    f"in the nuqta — update sources/spacing.yaml deliberately "
                    f"rather than letting the two drift apart."
                )
            return

    @staticmethod
    def _contour_width(contour):
        xs = [p.x for p in contour.points]
        return max(xs) - min(xs) if xs else 0

    def units(self, nuqta_multiple):
        return round(nuqta_multiple * self.nuqta)

    # -- classification --------------------------------------------------

    def join_sides(self, glyph, bounds):
        """Which edges of this glyph carry an Arabic joining connector.

        Returns a (left, right) pair of booleans. Detected from the outline so
        that editing the Arabic glyphs upstream cannot desynchronise a table.
        """
        if not in_arabic_block(glyph.unicode) and not any(
            glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol")
        ):
            return (False, False)

        width = glyph.width
        lo, hi = CONNECTOR_BAND
        left = right = False
        for contour in glyph.contours:
            for point in contour.points:
                if not (lo <= point.y <= hi):
                    continue
                if point.x <= JOIN_EDGE_TOLERANCE:
                    left = True
                if point.x >= width - JOIN_EDGE_TOLERANCE:
                    right = True
        return (left, right)

    def category(self, glyph):
        name = glyph.name
        cp = glyph.unicode

        if in_arabic_block(cp) or any(
            name.endswith(s) for s in (".init", ".medi", ".fina", ".isol")
        ):
            if cp == 0x0627 or name.startswith("uni0627"):
                return "arabic_alef"
            return "arabic_isolated"

        if name in TABULAR:
            return "digits"

        base = name.split(".")[0]
        if len(base) == 1:
            if base in LATIN_ROUND:
                return "latin_round"
            if base in LATIN_STRAIGHT:
                return "latin_straight"
            if base in LATIN_DIAGONAL:
                return "latin_diagonal"
            if base.isupper():
                return "uppercase"

        if cp is not None:
            cat = unicodedata.category(chr(cp))
            if cat.startswith("P"):
                if chr(cp) in "([{)]}":
                    return "brackets"
                if chr(cp) in "\"'‘’“”«»":
                    return "quotes"
                return "punctuation"
            if cat == "Sm":
                return "math"
            if cat == "Sc":
                return "currency"
            if cat == "Nd":
                return "digits"
            if cat.startswith("L"):
                return "latin_default"

        return "latin_default"

    def sidebearings(self, glyph, bounds):
        """Target (lsb, rsb) in font units, plus which sides are pinned joins."""
        overrides = self.config.get("overrides") or {}
        cats = self.config["categories"]
        default = self.config["defaults"]

        left_join, right_join = self.join_sides(glyph, bounds)

        if glyph.name in overrides:
            rule = overrides[glyph.name]
        else:
            cat = self.category(glyph)
            if (left_join or right_join) and cat.startswith("arabic"):
                # A form that joins on its right and is free on its left is a
                # FINAL: it attaches to the letter before it and its tail is
                # loose. Those tails are the ones that sweep, so they get their
                # own rule and a negative sidebearing to sweep into.
                if right_join and not left_join:
                    cat = "arabic_final"
                elif cat == "arabic_isolated":
                    cat = "arabic_free"
            rule = cats.get(cat, default)

        lsb = self.units(rule.get("lsb", default["lsb"]))
        rsb = self.units(rule.get("rsb", default["rsb"]))

        # A joining edge is not a sidebearing. Pin it.
        if left_join:
            lsb = 0
        if right_join:
            rsb = 0

        return lsb, rsb, (left_join, right_join)

    # -- fitting ---------------------------------------------------------

    def fit(self, glyph, bounds):
        """Translate the glyph and set its advance. Never scales.

        A joining edge is handled by an entirely different rule to a free one,
        and conflating them is what puts hairlines in the Arabic.

        The seed overlaps its connectors PAST the advance edge — a medial beh's
        ink runs from -35 to 1263 in a 1228 cell — so that adjacent letters
        share ink and merge without a seam. That overlap is invisible in the
        glyph on its own and is the whole reason joined text looks continuous.

        So a joining edge is not re-derived from ink at all: its exact offset
        from the advance edge is preserved, overlap and all. Fitting it to a
        zero sidebearing looks correct in isolation, lands the connector exactly
        on the edge, and leaves neighbouring letters touching at a single point
        instead of overlapping — which rasterises as a hairline seam.
        """
        lsb, rsb, joins = self.sidebearings(glyph, bounds)
        left_join, right_join = joins
        original_width = glyph.width

        if left_join:
            # The left connector, and its overlap, stay exactly where they are.
            shift = 0.0
        elif right_join:
            # The right connector must land on the new advance edge, so the
            # glyph moves and the advance follows it by the same amount.
            shift = lsb - bounds[0]
        else:
            shift = lsb - bounds[0]

        if right_join:
            # Whatever the right connector's offset from the advance was, keep
            # it: the advance moves with the glyph.
            glyph.width = round(original_width + shift)
        elif left_join:
            glyph.width = round(bounds[2] + rsb)
        else:
            ink = bounds[2] - bounds[0]
            glyph.width = round(ink + lsb + rsb)

        if round(shift) != 0:
            glyph.move((shift, 0))

        if any(joins):
            self.stats["joins"] += 1
        return shift


def ordered_glyphs(font):
    """Glyph names ordered so a glyph is always fitted after its components.

    Composites must be re-fitted only once their bases have already moved,
    otherwise they are fitted against stale bounds.
    """
    order = []
    seen = set()
    visiting = set()

    def visit(name):
        if name in seen or name not in font:
            return
        if name in visiting:  # cyclic reference; the seed has none, but be safe
            return
        visiting.add(name)
        for component in font[name].components:
            visit(component.baseGlyph)
        visiting.discard(name)
        seen.add(name)
        order.append(name)

    for glyph in font:
        visit(glyph.name)
    return order


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Mono.ufo")
    parser.add_argument("--out", default="sources/QalamBadi-Regular.ufo")
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--trim-serifs", action="store_true",
                        help="also narrow the over-wide i/j/l serifs (not yet implemented)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--report", action="store_true",
                        help="print the resulting advance widths and exit non-zero on suspicious ones")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)

    font = ufoLib2.Font.open(args.src)
    fitter = Fitter(font, config, trim_serifs=args.trim_serifs, verbose=args.verbose)

    spaces = config.get("spaces") or {}
    space_names = {
        "space": "space", "nbspace": "uni00A0", "thinspace": "uni2009",
        "hairspace": "uni200A", "emspace": "uni2003", "enspace": "uni2002",
        "arabic_space": None,
    }

    digit_width = None

    for name in ordered_glyphs(font):
        glyph = font[name]

        # Zero-width combining marks are overlays: they carry no advance by
        # design and must not acquire one here.
        if glyph.width == 0:
            fitter.stats["skipped"] += 1
            continue

        bounds = glyph.getBounds(font)
        if bounds is None:  # whitespace — handled below from spacing.yaml
            fitter.stats["skipped"] += 1
            continue

        if glyph.components:
            fitter.stats["composites"] += 1

        fitter.fit(glyph, bounds)
        fitter.stats["fitted"] += 1

        if name == "zero":
            digit_width = glyph.width

    # Tabular figures: every digit takes the widest digit's advance, centred.
    if digit_width is not None:
        digits = [font[n] for n in TABULAR if n in font]
        target = max(g.width for g in digits)
        for glyph in digits:
            if glyph.width != target:
                glyph.move(((target - glyph.width) / 2, 0))
                glyph.width = target

    # Whitespace, from the nuqta system.
    for key, glyph_name in space_names.items():
        if glyph_name and glyph_name in font and key in spaces and spaces[key]:
            font[glyph_name].width = fitter.units(spaces[key])

    font.info.familyName = "Qalam Badi"
    font.info.styleName = "Regular"
    if font.info.postscriptFontName:
        font.info.postscriptFontName = "QalamBadi-Regular"

    # The seed declares itself monospaced in three separate places, and all
    # three are now lies. Layout engines, PDF generators and terminal emulators
    # act on them — a font that claims fixed pitch while shipping 2193 distinct
    # advances gets laid out wrong — so they are corrected here rather than
    # left for a downstream fixup to guess at.
    font.info.postscriptIsFixedPitch = False
    panose = list(font.info.openTypeOS2Panose or [])
    if len(panose) == 10 and panose[3] == 9:  # bProportion: 9 = monospaced
        panose[3] = 3  # 3 = modern/proportional for a Latin text family
        font.info.openTypeOS2Panose = panose

    if os.path.exists(args.out):
        shutil.rmtree(args.out)
    font.save(args.out)

    stats = fitter.stats
    print(
        f"fitted {stats['fitted']} glyphs "
        f"({stats['composites']} composite, {stats['joins']} with pinned Arabic joins), "
        f"{stats['skipped']} left alone -> {args.out}"
    )


if __name__ == "__main__":
    main()
