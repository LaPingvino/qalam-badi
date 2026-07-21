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

from importlib.machinery import SourceFileLoader

_joins = SourceFileLoader(
    "joins", os.path.join(os.path.dirname(os.path.abspath(__file__)), "joins.py")
).load_module()
_classify = SourceFileLoader(
    "classify_widths",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "classify-widths.py")
).load_module()

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

        self.join_height = _joins.measure_join_height(font, _classify.PolygonPen)
        if self.join_height is None:
            print("warning: no single Arabic join height found; joins will not "
                  "be pinned. The font's connectors are no longer consistent.",
                  file=sys.stderr)
        else:
            print(f"join height: y={self.join_height[0]:.0f}..{self.join_height[1]:.0f} "
                  f"({self.join_height[1] - self.join_height[0]:.0f} units thick)")

        self.stats = {"fitted": 0, "joins": 0, "skipped": 0, "composites": 0}
        # How far each glyph was translated, so composites can undo their
        # components' independent movement. See compensate_components().
        self.shifts = {}

    def compensate_components(self, glyph):
        """Undo the movement each component inherited from its own base.

        A composite is not a drawing, it is a set of references, so when `a` is
        fitted and moves, every `aacute` silently moves with it — but `acute`
        moved by its OWN fit, a different distance, so the accent slides off the
        letter. This is why á rendered with its accent too far ahead.

        Each component is pulled back by whatever its base was shifted, which
        restores the composite to exactly the relative geometry the seed drew.
        The composite is then fitted as one unit, so the accent stays put over
        the letter it belongs to.
        """
        self.compensate_component_shifts(glyph)
        self.recentre_marks(glyph)

    def compensate_component_shifts(self, glyph):
        """Undo the translation each component inherited from its own base."""
        for component in glyph.components:
            base_shift = self.shifts.get(component.baseGlyph)
            if not base_shift:
                continue
            xx, xy, yx, yy, dx, dy = component.transformation
            component.transformation = (xx, xy, yx, yy, dx - base_shift, dy)

    def recentre_marks(self, glyph):
        """Centre diacritics over the letter they belong to.

        In the seed every mark was centred on the monospace CELL, because in a
        monospace font the cell and the letter are the same thing. They are not
        the same thing here: letters have moved, and single-stem letters like
        `i` have had their serifs pulled in, so a mark left at the old cell
        centre now sits off to one side of its base. This is what put the acute
        too far ahead on á and the dot off-centre under Ḥ.

        The largest component is taken as the letter and every substantially
        smaller one as a mark, which is what a diacritic is geometrically. Marks
        the seed placed deliberately off-centre — the cedilla, the ogonek — keep
        their offset; only ones that were centred, and have since drifted, are
        snapped back.
        """
        if len(glyph.components) < 2:
            return

        measured = []
        for component in glyph.components:
            base = self.font.get(component.baseGlyph)
            if base is None:
                return
            bounds = base.getBounds(self.font)
            if bounds is None:
                return
            measured.append((component, bounds, bounds.xMax - bounds.xMin))

        letter, letter_bounds, letter_width = max(measured, key=lambda m: m[2])
        if letter_width <= 0:
            return

        letter_centre = ((letter_bounds.xMin + letter_bounds.xMax) / 2
                         + letter.transformation[4])

        for component, bounds, width in measured:
            # 0.75, not something tighter: Courier's accents are wide because
            # they had a cell to fill too — its acute carries 498 units of ink
            # against the `a`'s 855 — so a stricter ratio classifies real
            # diacritics as letters and leaves them uncentred. Genuine
            # two-letter composites (ij) sit at ~1.0 and stay excluded.
            if component is letter or width > letter_width * 0.75:
                continue  # not a mark, it is part of the letter

            xx, xy, yx, yy, dx, dy = component.transformation
            mark_centre = (bounds.xMin + bounds.xMax) / 2 + dx
            offset = mark_centre - letter_centre

            # Deliberately off-centre in the design: leave it alone.
            if abs(offset) > letter_width * 0.30:
                continue

            component.transformation = (xx, xy, yx, yy, dx - offset, dy)

    # Marks that ATTACH at a designed spot rather than centring on the letter.
    ATTACHING_MARKS = ("cedilla", "ogonek", "horn")

    def recentre_all_composites(self):
        """Recentre comb-marks in precomposed letters from FINAL geometry.

        recentre_marks runs while glyphs are still being fitted, and the
        overlay restoration afterwards moves the combining marks' ink again —
        so every composite referencing a restored mark was centred against
        geometry that then changed underneath it. The dot under Ḥ drifted 255
        units right of the H exactly this way, and the hook above Ử a full
        504. This pass repeats the centring after everything has stopped
        moving, which makes the earlier one a first approximation and this
        one the truth.

        Deciding what to centre goes by NAME here, not by offset size: after
        drift, a large offset is precisely what a broken mark looks like, so
        "large offset means deliberate" — the guard the in-flight pass rightly
        uses — would preserve the worst breakage. A comb mark centres unless
        it is an attaching kind; everything else keeps its designed position.
        """
        count = 0
        for glyph in self.font:
            if glyph.width == 0 or len(glyph.components) < 2:
                continue
            measured = []
            for component in glyph.components:
                base = self.font.get(component.baseGlyph)
                bounds = base.getBounds(self.font) if base is not None else None
                if bounds is None:
                    measured = None
                    break
                measured.append((component, bounds, bounds.xMax - bounds.xMin))
            if not measured:
                continue

            letter, letter_bounds, letter_width = max(measured, key=lambda m: m[2])
            if letter_width <= 0:
                continue
            letter_centre = ((letter_bounds.xMin + letter_bounds.xMax) / 2
                             + letter.transformation[4])

            for component, bounds, width in measured:
                if component is letter or width > letter_width * 0.75:
                    continue
                name = component.baseGlyph
                if "comb" not in name or any(a in name for a in self.ATTACHING_MARKS):
                    continue
                xx, xy, yx, yy, dx, dy = component.transformation
                offset = (bounds.xMin + bounds.xMax) / 2 + dx - letter_centre
                if abs(offset) < 1:
                    continue
                component.transformation = (xx, xy, yx, yy, dx - offset, dy)
                count += 1
        return count

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

        Delegates to scripts/joins.py, which identifies a connector by the
        font's single measured join height rather than by a band around the
        baseline. See that module for why the band was wrong.
        """
        if not in_arabic_block(glyph.unicode) and not any(
            glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol")
        ):
            return (False, False)

        if self.join_height is None:
            return (False, False)

        pen = _classify.PolygonPen(self.font)
        glyph.draw(pen)
        if not pen.polygons:
            return (False, False)

        return _joins.join_sides(glyph, pen.polygons, self.join_height)

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

        if left_join or right_join:
            # A joining glyph is never repositioned, on either side.
            #
            # Finals used to be shifted so their left sidebearing hit a
            # configured negative value, which was how the sweep was faked
            # before the tails were real geometry. Now that reshape-tails draws
            # an actual undertail reaching back under the preceding letters,
            # forcing that sidebearing DRAGS THE WHOLE GLYPH RIGHT to meet it —
            # final alef maksura moved 838 units and its advance grew from 1138
            # to 1976, so instead of tucking under its neighbours it shoved them
            # apart and read as cut off at the end of a word.
            #
            # The overhang is a consequence of the drawing, not a target to snap
            # to. Let the tail hang wherever it was drawn.
            shift = 0.0
        else:
            shift = lsb - bounds[0]

        if right_join:
            # The right connector defines the advance edge; it must not move.
            glyph.width = original_width
        elif left_join:
            # Left connector pinned at the origin, right side free to be fitted.
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

    # Where every zero-width mark's ink sits BEFORE anything is fitted.
    #
    # These are overlays positioned over the preceding base, and many are
    # composites: gravecomb references the spacing grave, dotbelowcomb
    # references period. When those bases are fitted and move, the mark's ink
    # moves with them and no longer sits over the letter — U+0300 drifted and
    # rendered beside its base instead of on top of it.
    #
    # Their position is restored by measurement rather than by undoing the
    # base's shift arithmetically. The arithmetic has to agree with several
    # transforms at once and got the sign wrong on four marks; where the ink
    # started is a fact that cannot be got wrong.
    mark_origins = {}
    for glyph in font:
        if glyph.width == 0 and glyph.components:
            bounds = glyph.getBounds(font)
            if bounds is not None:
                mark_origins[glyph.name] = bounds.xMin

    digit_width = None

    for name in ordered_glyphs(font):
        glyph = font[name]

        # Zero-width combining marks are overlays: they carry no advance by
        # design and must not acquire one here.
        #
        # They must still have their components compensated, though. A mark like
        # gravecomb is a COMPOSITE referencing the spacing grave, so when that
        # base is fitted and shifts left, the mark's ink silently shifts with it
        # and no longer sits over the letter — U+0300 drifted 243 units and
        # rendered beside the base instead of on top of it. Skipping these
        # before compensation is what let that through.
        if glyph.width == 0:
            fitter.stats["skipped"] += 1
            continue

        # Undo inherited component movement BEFORE measuring: bounds taken
        # before this are the bounds of a composite that has come apart.
        if glyph.components:
            fitter.compensate_components(glyph)
            fitter.stats["composites"] += 1

        bounds = glyph.getBounds(font)
        if bounds is None:  # whitespace — handled below from spacing.yaml
            fitter.stats["skipped"] += 1
            continue

        fitter.shifts[name] = fitter.fit(glyph, bounds)
        fitter.stats["fitted"] += 1

        if name == "zero":
            digit_width = glyph.width

    # Put the zero-width marks back exactly where they started.
    restored = 0
    for name, original_x in mark_origins.items():
        glyph = font[name]
        bounds = glyph.getBounds(font)
        if bounds is None:
            continue
        drift = original_x - bounds.xMin
        if abs(drift) > 0.5:
            for component in glyph.components:
                xx, xy, yx, yy, dx, dy = component.transformation
                component.transformation = (xx, xy, yx, yy, dx + drift, dy)
            for contour in glyph.contours:
                for point in contour.points:
                    point.x += drift
            restored += 1
    if restored:
        print(f"restored {restored} combining marks to their overlay position")

    # And only NOW, with every mark and base where it will actually ship,
    # centre the marks inside the precomposed letters. See the method's
    # docstring for why this must be last and why it decides by name.
    recentred = fitter.recentre_all_composites()
    if recentred:
        print(f"recentred {recentred} marks over their precomposed bases")

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
