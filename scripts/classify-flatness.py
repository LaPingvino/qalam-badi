#!/usr/bin/env python3
"""Find the long flat runs the monospace cell forced into the Arabic.

Long flat lines are a red flag in this script for the same reason big open
spaces were a red flag in the Latin: both are the cell showing through. A
connector had to reach the wall of its box whether the letter wanted to be that
wide or not, so it was stretched into a plateau — and a plateau is precisely
what a nastaʿlīq hand does not draw.

The classical rule is explicit about it. Nastaʿlīq is **one-sixth to one-third
straight** (*saṭḥ*), the rest curved (*dowr*); one source puts the ratio at at
least 5:1 in favour of curve, against naskh's 1:2. Only the alef/lam stems and a
deliberate kashida should be truly straight. Everything else is arc.

This is also why الله needs its dedicated ligature glyph to look right: the
letters that compose it join along stretched flat connectors, so the joined form
reads as a fence rather than as a written word, and the ligature has to be drawn
by hand to paper over it. Shorten the connectors and the composed form should
come out close to right on its own.

A "flat run" here means a genuinely straight segment — two consecutive on-curve
points with no control points between them — that is near-horizontal and sits in
the band where joins happen. Flattened curve approximations are deliberately not
counted; we want the lines the outline actually declares to be lines.

The --sides report is the flatness report's successor, and the measure-first
step of connector EXTENSION. It splits every joining glyph into what the
transform itself sees — left approach | body | right approach, using the very
body detector and join test that shorten-connectors.py compresses with — and
flags each body TIGHT / OK / LOOSE against the classical figures (a tooth is
about one dot wide, a dal two, a beh short form four to five, a seen with its
kashida seven to eleven). Because it is the transform's own reading, a letter
this report calls TIGHT is one the symmetric fitter can actually free, and the
body/approach split answers the question the plan hinges on: whether a
squished letter is tight in the CONNECTOR (extend the approach) or in the BODY
(a different fix entirely).

Usage:
    python3 scripts/classify-flatness.py --src sources/QalamBadi-Mono.ufo
    python3 scripts/classify-flatness.py --src sources/QalamBadi-Mono.ufo --tsv
    python3 scripts/classify-flatness.py --src sources/QalamBadi-Connected.ufo --sides
"""

import argparse
import math
import os

import ufoLib2

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_classify = SourceFileLoader(
    "classify_widths", os.path.join(_here, "classify-widths.py")).load_module()
_joins = SourceFileLoader("joins", os.path.join(_here, "joins.py")).load_module()

# A segment is "flat" if it rises less than this many units per unit of run.
# 0.18 is about 10 degrees — steeper than that and it reads as a sweep, not a
# plateau.
FLAT_SLOPE = 0.18

# Only runs in this band above/below the baseline are of interest: these are the
# connector plateaus. A flat run high in the letter is a different creature (the
# bar of a kaf, the roof of a tah) and is not what the cell distorted.
BASELINE_BAND = (-260, 500)

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)


def is_arabic(glyph):
    cp = glyph.unicode
    if cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def flat_runs(glyph):
    """Straight, near-horizontal segments near the baseline.

    Returns a list of (length, y, x_start, x_end).
    """
    runs = []
    for contour in glyph.contours:
        points = list(contour.points)
        count = len(points)
        if count < 2:
            continue
        for index, point in enumerate(points):
            if point.type not in ("line", "curve", "qcurve", "move"):
                continue
            nxt = points[(index + 1) % count]
            # A line segment is declared by the NEXT point being an on-curve of
            # type "line"; anything else means control points intervene.
            if nxt.type != "line":
                continue
            dx = nxt.x - point.x
            dy = nxt.y - point.y
            if abs(dx) < 1:
                continue
            if abs(dy / dx) > FLAT_SLOPE:
                continue
            mid_y = (point.y + nxt.y) / 2
            if not (BASELINE_BAND[0] <= mid_y <= BASELINE_BAND[1]):
                continue
            runs.append((abs(dx), mid_y, min(point.x, nxt.x), max(point.x, nxt.x)))
    return runs


def straightness(glyph):
    """Fraction of outline length that is declared straight — the saṭḥ share."""
    straight = 0.0
    total = 0.0
    for contour in glyph.contours:
        points = list(contour.points)
        count = len(points)
        if count < 2:
            continue
        previous = None
        for index, point in enumerate(points):
            if point.type is None:
                continue
            if previous is not None:
                length = math.hypot(point.x - previous[0], point.y - previous[1])
                total += length
                if point.type == "line":
                    straight += length
            previous = (point.x, point.y)
    return (straight / total) if total else 0.0


# --- The two-sided report -------------------------------------------------
#
# Classical width figures, in nuqta, for the skeletons we have figures for.
# These are the numbers already argued in NEXT.md and spacing.yaml: a tooth is
# about one dot wide, a dal two, a beh short (final) form four to five, a seen
# carried on its kashida seven to eleven. Letters without a classical figure
# are still measured — the measurement is the deliverable, the flag is a
# convenience — they just carry no flag.
#
# Keyed by base-letter skeleton because the dotted variants share their
# skeleton's width exactly: teh is beh with dots, so it inherits beh's figure.
BEH_SKELETON = {
    0x0628, 0x062A, 0x062B, 0x0679, 0x067A, 0x067B, 0x067C, 0x067D,
    0x067E, 0x067F, 0x0680, 0x08A0, 0x08A1, 0x0750, 0x0751, 0x0752,
    0x0753, 0x0754, 0x0755, 0x0756, 0x0620,
}
YEH_SKELETON = {0x0626, 0x0649, 0x064A, 0x06CC, 0x06CD, 0x06CE, 0x06D0, 0x06D1}
NOON_SKELETON = {0x0646, 0x06BA, 0x06B9, 0x06BB, 0x06BC, 0x06BD, 0x0767, 0x0768, 0x0769}
DAL_SKELETON = {
    0x062F, 0x0630, 0x0688, 0x0689, 0x068A, 0x068B, 0x068C, 0x068D,
    0x068E, 0x068F, 0x0690, 0x06EE,
}
SEEN_SKELETON = {0x0633, 0x0634, 0x0635, 0x0636, 0x069A, 0x069B, 0x069C, 0x069D, 0x069E, 0x06FA, 0x06FB, 0x075C, 0x076D, 0x0770, 0x077D, 0x077E}
LAM_SKELETON = {0x0644, 0x06B5, 0x06B6, 0x06B7, 0x06B8}

TOOTH_FAMILY = BEH_SKELETON | YEH_SKELETON | NOON_SKELETON

FORM_SUFFIXES = {".init": "init", ".medi": "medi", ".fina": "fina", ".isol": "isol"}


def body_targets(base, form):
    """(lo, hi, label, measure) classical width in nuqta, or None.

    The tooth figure is a BODY width — the tooth itself, measured as the
    detector's longest island. The final and isolated figures are WHOLE
    LETTER widths — a beh short form is mostly its flat bowl, which the
    detector rightly reads as connector — so those compare against ink.
    """
    if base in TOOTH_FAMILY and form in ("init", "medi"):
        return (0.7, 1.4, "tooth ~1", "body")
    if base in DAL_SKELETON:
        return (1.6, 2.4, "dal ~2", "ink")
    if base in BEH_SKELETON and form in ("fina", "isol"):
        return (4.0, 5.0, "beh short 4-5", "ink")
    if base in SEEN_SKELETON and form in ("fina", "isol"):
        return (7.0, 11.0, "seen kashida 7-11", "ink")
    return None


def base_and_form(glyph):
    """Base-letter codepoint and joining form for a glyph, or (None, None).

    Presentation-form glyphs (uniFB50..uniFEFF) decompose to their base letter
    via Unicode itself; suffixed glyphs (uni0628.medi) parse from the name.
    """
    import unicodedata

    form = "isol"
    name = glyph.name
    for suffix, label in FORM_SUFFIXES.items():
        if suffix in name:
            form = label
            break

    cp = glyph.unicode
    if cp is not None and 0xFB50 <= cp <= 0xFEFF:
        decomposition = unicodedata.decomposition(chr(cp)).split()
        if decomposition and decomposition[0] in ("<initial>", "<medial>", "<final>", "<isolated>"):
            form = decomposition[0].strip("<>").replace("initial", "init").replace(
                "medial", "medi").replace("final", "fina").replace("isolated", "isol")
            if len(decomposition) == 2:  # single base letter, not a ligature
                return int(decomposition[1], 16), form
            return None, form
    if cp is not None:
        return cp, form
    if name.startswith("uni") and len(name) >= 7:
        try:
            return int(name[3:7], 16), form
        except ValueError:
            pass
    return None, form


def sides_report(args):
    """Left approach | body | right approach for every joining glyph.

    Uses shorten-connectors' own body detector, so what this report calls
    approach is exactly what the fitter will stretch or compress.
    """
    shorten = SourceFileLoader(
        "fit_connectors", os.path.join(_here, "fit-connectors.py")).load_module()
    PolygonPen = _classify.PolygonPen

    font = ufoLib2.Font.open(args.src)
    nuqta = 271

    join_height = _joins.measure_join_height(font, PolygonPen)
    if join_height is None:
        raise SystemExit("no single Arabic join height found; the report depends on it")

    rows = []
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours:
            continue
        pen = PolygonPen(font)
        glyph.draw(pen)
        if not pen.polygons:
            continue
        left_join, right_join = _joins.join_sides(glyph, pen.polygons, join_height)
        if not (left_join or right_join):
            continue

        body = shorten.body_interval_by_join_height(font, glyph, join_height)
        if body is None:
            continue
        body_width = (body[1] - body[0]) / nuqta
        left_approach = max(0.0, body[0]) / nuqta if left_join else 0.0
        right_approach = max(0.0, glyph.width - body[1]) / nuqta if right_join else 0.0

        bounds = glyph.getBounds(font)
        ink_width = (bounds.xMax - bounds.xMin) / nuqta

        base, form = base_and_form(glyph)
        target = body_targets(base, form) if base is not None else None
        if target is None:
            flag = "-"
            label = ""
        else:
            measured = body_width if target[3] == "body" else ink_width
            if measured < target[0]:
                flag = "TIGHT"
            elif measured > target[1]:
                flag = "LOOSE"
            else:
                flag = "OK"
            label = target[2]

        joins = ("L" if left_join else "-") + ("R" if right_join else "-")
        rows.append((flag, glyph.name, form, joins, body_width,
                     left_approach, right_approach, ink_width, label))

    order = {"TIGHT": 0, "LOOSE": 1, "OK": 2, "-": 3}
    rows.sort(key=lambda r: (order[r[0]], -r[4]))

    if args.tsv:
        print("glyph\tform\tjoins\tbody\tleft\tright\tink\tflag\ttarget")
        for flag, name, form, joins, body, left, right, advance, label in rows:
            print(f"{name}\t{form}\t{joins}\t{body:.2f}\t{left:.2f}\t{right:.2f}"
                  f"\t{advance:.2f}\t{flag}\t{label}")
        return

    print(f"Two-sided report over {len(rows)} joining glyphs ({args.src})")
    print(f"join height y={join_height[0]:.0f}..{join_height[1]:.0f}; all figures in nuqta ({nuqta} units)\n")
    print(f"{'glyph':26}{'form':>6}{'joins':>6}{'body':>7}{'left':>7}{'right':>7}{'ink':>7}  flag   target")
    shown = 0
    for flag, name, form, joins, body, left, right, advance, label in rows:
        if flag == "-" and not args.all:
            continue
        print(f"{name:26}{form:>6}{joins:>6}{body:7.2f}{left:7.2f}{right:7.2f}{advance:7.2f}  {flag:6} {label}")
        shown += 1
        if shown >= args.limit:
            break

    counts = {}
    for row in rows:
        counts[row[0]] = counts.get(row[0], 0) + 1
    print("\n" + "  ".join(f"{k}: {v}" for k, v in sorted(counts.items(), key=lambda i: order[i[0]])))
    print("(TIGHT = body narrower than the classical figure -> candidate for extension;")
    print(" LOOSE = body wider -> the squish is not in the connector; '-' = no classical figure)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Mono.ufo")
    parser.add_argument("--tsv", action="store_true")
    parser.add_argument("--sides", action="store_true",
                        help="two-sided report: left approach | body | right approach")
    parser.add_argument("--all", action="store_true",
                        help="with --sides, include glyphs that have no classical figure")
    parser.add_argument("--min-length", type=float, default=300,
                        help="report runs at least this long (units)")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    if args.sides:
        sides_report(args)
        return

    font = ufoLib2.Font.open(args.src)
    nuqta = 271

    rows = []
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours:
            continue
        runs = flat_runs(glyph)
        if not runs:
            continue
        longest = max(runs, key=lambda r: r[0])
        if longest[0] < args.min_length:
            continue
        rows.append((longest[0], glyph.name, longest, straightness(glyph), len(runs)))

    rows.sort(reverse=True)

    if args.tsv:
        print("glyph\tlongest_flat\tnuqta\tsath_share\tflat_runs")
        for length, name, run, sath, count in rows:
            print(f"{name}\t{length:.0f}\t{length / nuqta:.2f}\t{sath:.2f}\t{count}")
        return

    print(f"Arabic glyphs with a flat baseline run of {args.min_length:.0f}+ units")
    print(f"({len(rows)} of them; the nuqta is {nuqta} units)\n")
    print(f"{'glyph':22}{'flat run':>10}{'nuqta':>8}{'sath':>8}  runs")
    for length, name, run, sath, count in rows[:args.limit]:
        print(f"{name:22}{length:10.0f}{length / nuqta:8.2f}{sath:8.0%}  {count}")
    if len(rows) > args.limit:
        print(f"... and {len(rows) - args.limit} more")

    if rows:
        share = sum(r[3] for r in rows) / len(rows)
        print(f"\nmean saṭḥ share across these glyphs: {share:.0%}")
        print("classical nastaʿlīq: 17-33%. naskh: ~50%.")


if __name__ == "__main__":
    main()
