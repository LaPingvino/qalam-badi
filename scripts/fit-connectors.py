#!/usr/bin/env python3
"""Fit the Arabic connector runs: shorten the cell's plateaus, extend to targets.

This is shorten-connectors.py made symmetric, as planned in NEXT.md. The cell
stretched the baseline connectors sideways exactly as it stretched the Latin
serifs; compressing them back is half the fix. The other half is the inverse:
letters whose written form IS partly a flat run — a beh final's bowl, a seen's
kashida — need that run restored to its classical length, and restoring it is
the same operation with the sign flipped. One code path, both directions, one
set of guards, which is what keeps extension out of the fat-seen failure mode:
a connector is a horizontal stroke at the join height, so its thickness is a
vertical measurement and changing its length in x costs nothing.

The unit of the whole transform is the ISLAND. At any x, either the only ink
is the join-height stroke itself (the pen is travelling, nothing is being
written) or something departs from that signature (the pen is writing). The
contiguous written stretches are the islands — teeth, bowls, hooks, dots — and
every one of them is a shape, so every one of them moves rigidly. Only the
bare runs between and around them may change length.

The previous version held ONE island rigid (the longest) and scaled everything
outside it as approach. On a single-bodied letter that is the same thing; on a
multi-island letter it violated the shape rule: a seen final is tail + teeth,
the tail won, and the teeth were scaled from ~290 units wide down to 24. This
version exists because of that measurement.

Length targets are per letter and live in sources/spacing.yaml
(connectors.widths), in nuqta, from the classical figures recorded there. The
delta needed to hit a target goes into a single elongation run — the bare run
beside the letter's largest island, which is where a kashida classically
lives — never spread across the teeth gaps.

Usage:
    python3 scripts/fit-connectors.py --src sources/QalamBadi-Softened.ufo \
                                      --out sources/QalamBadi-Connected.ufo
"""

import argparse
import os
import shutil

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_classify = SourceFileLoader(
    "classify_widths", os.path.join(_here, "classify-widths.py")).load_module()
_flatness = SourceFileLoader(
    "classify_flatness", os.path.join(_here, "classify-flatness.py")).load_module()
_joins = SourceFileLoader("joins", os.path.join(_here, "joins.py")).load_module()

PolygonPen = _classify.PolygonPen

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)

# The skeleton families the width targets are written against. A target for
# "beh" covers teh, theh, peh and every other letter that is beh's skeleton
# with different dots, because the skeleton is what has the width.
FAMILIES = {
    "beh": _flatness.BEH_SKELETON,
    "yeh": _flatness.YEH_SKELETON,
    "noon": _flatness.NOON_SKELETON,
    "dal": _flatness.DAL_SKELETON,
    "seen": _flatness.SEEN_SKELETON,
    "lam": _flatness.LAM_SKELETON,
    "heh": _flatness.HEH_SKELETON,
}


def is_arabic(glyph):
    cp = glyph.unicode
    if cp is not None and any(lo <= cp <= hi for lo, hi in ARABIC_BLOCKS):
        return True
    return any(glyph.name.endswith(s) for s in (".init", ".medi", ".fina", ".isol"))


def body_islands(font, glyph, join_height, step=12, dots_nuqta=None):
    """Every contiguous x range where the glyph is letter, not bare connector.

    Each island is padded by one sample step on both sides, so sampling
    granularity can never leave a sliver of true letter ink inside a run that
    is about to be scaled.

    When `dots_nuqta` is given, dot-sized contours are left out of the island
    scan: a connector's length is a join-height property, but a dot departs
    from the join signature at whatever x it hangs at, so a letter's below-dots
    would otherwise pad the island out to their full span and hold the whole
    cell open. The dot itself is not lost — apply_remap_preserving_dots carries
    it rigidly with the skeleton — so ignoring it here just lets the connector
    fit the tooth, not the dots. That is what un-folds the ya medial (island
    624 wide from its dots, against beh's 336) back to its skeleton's width.
    """
    bottom, top = join_height
    tolerance = _joins.JOIN_TOLERANCE

    pen = PolygonPen(font)
    if dots_nuqta is not None:
        dot_limit = dots_nuqta * 1.35
        for contour in glyph.contours:
            xs = [p.x for p in contour.points]
            ys = [p.y for p in contour.points]
            if not xs:
                continue
            if max(xs) - min(xs) <= dot_limit and max(ys) - min(ys) <= dot_limit:
                continue  # a dot: does not set the connector length
            contour.draw(pen)
    else:
        glyph.draw(pen)
    if not pen.polygons:
        return None
    bounds = glyph.getBounds(font)
    if bounds is None:
        return None

    islands = []
    run_start = None
    x = bounds.xMin + 1
    while x < bounds.xMax:
        spans = _joins.spans_at(pen.polygons, x)
        is_body = False
        if spans:
            only_join_line = all(
                abs(span_bottom - bottom) <= tolerance and abs(span_top - top) <= tolerance
                for span_bottom, span_top in spans)
            is_body = not only_join_line
        if is_body and run_start is None:
            run_start = x
        elif not is_body and run_start is not None:
            islands.append((run_start - step, x + step))
            run_start = None
        x += step
    if run_start is not None:
        islands.append((run_start - step, x + step))

    # Padding can make neighbours touch; merge them.
    merged = []
    for start, end in islands:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Drop sliver islands. Everything in this face is drawn with a 141-unit
    # pen, so no real feature is narrower than most of a pen — but the fillet
    # rounding the connector's corner at the join overlap reliably pushes one
    # or two samples outside the join tolerance, minting a ~36-unit phantom
    # island at the edge. Under the old longest-run rule that phantom merely
    # lost the vote; under the multi-island rule it would turn the entire real
    # approach into a held inner run, so it must go.
    merged = [(start, end) for start, end in merged if end - start >= 100]
    return merged or None


def body_interval_by_join_height(font, glyph, join_height, step=12):
    """The longest island — the reading the two-sided report classifies with."""
    islands = body_islands(font, glyph, join_height, step)
    if not islands:
        return None
    return max(islands, key=lambda i: i[1] - i[0])


def movable_runs(glyph, islands, left_join, right_join):
    """The bare connector runs that may change length, left to right.

    Each is [start, end, kind]: 'outer' runs lead from a joining edge to the
    outermost island and are subject to the approach cap; 'inner' runs lie
    between islands and are held unless one is the elongation run. A bare
    stretch on a NON-joining side is not a run at all — it is letter (a
    final's tail exit) and stays rigid, which is the lesson the
    negative-advance seen taught.
    """
    runs = []
    advance = float(glyph.width)
    if left_join and islands[0][0] > 0:
        runs.append([0.0, islands[0][0], "outer"])
    for (a_start, a_end), (b_start, b_end) in zip(islands, islands[1:]):
        if b_start > a_end:
            runs.append([a_end, b_start, "inner"])
    if right_join and advance > islands[-1][1]:
        runs.append([islands[-1][1], advance, "outer"])
    return runs


def elongation_run(runs, islands):
    """Where kashida length is inserted or removed: the run beside the largest
    island, preferring the inner side. In a beh final that is the bowl run
    between hook and tooth; in a seen final the run between tail and teeth; in
    an initial form with one island it degrades to the joining approach."""
    largest = max(islands, key=lambda i: i[1] - i[0])
    adjacent = [run for run in runs
                if abs(run[0] - largest[1]) < 1 or abs(run[1] - largest[0]) < 1]
    pool = adjacent or runs
    inner = [run for run in pool if run[2] == "inner"]
    pool = inner or pool
    return max(pool, key=lambda run: run[1] - run[0])


def width_targets(settings):
    """(base codepoint, form) -> target ink width in nuqta."""
    table = {}
    for key, value in (settings.get("widths") or {}).items():
        family, _, form = key.partition(".")
        if family not in FAMILIES:
            raise SystemExit(f"connectors.widths: unknown family {family!r} in {key!r}")
        if form not in ("init", "medi", "fina", "isol"):
            raise SystemExit(f"connectors.widths: unknown form in {key!r}")
        for codepoint in FAMILIES[family]:
            table[(codepoint, form)] = float(value)
    return table


def apply_remap_preserving_dots(glyph, remap, nuqta, islands=None):
    """Apply the x remap, but move dots rigidly instead of squashing them.

    A dot remapped point by point comes out as a squashed ellipse, and once it
    is thin enough the overlap removal in the build simply loses it — that is
    how the dot vanished from ba. So any contour small enough to be a dot is
    translated whole.

    But by how much? Not by remap(centre): now that dots are held OUT of the
    island scan, a below-dot sits in a bare connector RUN, and evaluating the
    remap there returns the run's SCALED position — so when the run shortens,
    the dots of a two- or three-dot cluster each land on a different scaled x
    and bunch into a blob. A dot belongs to the skeleton, so it must ride the
    rigid shift of the island it hangs under, not the run it happens to sit in.
    Every dot in a cluster shares one island, so they share one shift and their
    mutual spacing is preserved. Falls back to remap(centre) when no islands
    are supplied (the single-island callers that never compress a run).
    """
    dot_limit = nuqta * 1.35

    def dot_shift(centre):
        if not islands:
            return remap(centre) - centre
        start, end = min(islands, key=lambda i: abs((i[0] + i[1]) / 2 - centre))
        mid = (start + end) / 2
        return remap(mid) - mid

    for contour in glyph.contours:
        xs = [p.x for p in contour.points]
        ys = [p.y for p in contour.points]
        if not xs:
            continue
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        if width <= dot_limit and height <= dot_limit:
            centre = (min(xs) + max(xs)) / 2
            shift = dot_shift(centre)
            for point in contour.points:
                point.x += shift
        else:
            for point in contour.points:
                point.x = remap(point.x)

    for component in glyph.components:
        xx, xy, yx, yy, dx, dy = component.transformation
        component.transformation = (xx, xy, yx, yy, remap(dx), dy)
    for anchor in glyph.anchors:
        anchor.x = remap(anchor.x)


def make_piecewise_remap(runs, new_lengths):
    """x remap that rescales each run to its new length and translates
    everything else — islands, overlaps beyond the edges — rigidly."""
    pieces = []
    shift = 0.0
    for (start, end, _), new_length in zip(runs, new_lengths):
        scale = new_length / (end - start) if end > start else 1.0
        pieces.append((start, end, shift, scale))
        shift += new_length - (end - start)
    total_shift = shift

    def remap(x):
        for start, end, shift_before, scale in pieces:
            if x <= start:
                return x + shift_before
            if x < end:
                return start + shift_before + (x - start) * scale
        return x + total_shift

    return remap


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="sources/QalamBadi-Softened.ufo")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config", default="sources/spacing.yaml")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)

    nuqta = config["module"]["nuqta"]
    settings = config.get("connectors") or {}
    approach = settings.get("approach", 0.42) * nuqta
    skip = set(settings.get("keep_long") or [])
    targets = width_targets(settings)

    font = ufoLib2.Font.open(args.src)

    join_height = _joins.measure_join_height(font, PolygonPen)
    if join_height is None:
        raise SystemExit(
            "no single Arabic join height found; this transform depends on it")
    print(f"join height: y={join_height[0]:.0f}..{join_height[1]:.0f}")

    shortened = 0
    extended = 0
    skipped_small = 0
    skipped_extreme = 0
    total_removed = 0.0
    total_added = 0.0
    for glyph in font:
        if not is_arabic(glyph) or not glyph.contours or glyph.name in skip:
            continue

        bounds = glyph.getBounds(font)
        if bounds is None:
            continue

        base, form = _flatness.base_and_form(glyph)

        # Hold dots out of the island scan only for MEDIAL forms. A medial
        # shortens both approaches symmetrically, so its tooth stays put and
        # its dots ride straight down with it — the ya medial un-folds cleanly.
        # An initial/final shortens one side, so its tooth travels; letting the
        # dots follow that travel drags a cluster off the glyph. Those forms
        # keep the old dots-are-islands behaviour until they get their own fix.
        exclude_dots = nuqta if form == "medi" else None
        islands = body_islands(font, glyph, join_height, dots_nuqta=exclude_dots)
        if not islands:
            continue

        # A letter has to actually be there to pin. The widest island carries
        # the identity; if even that is a few units wide, detection failed.
        widest = max(end - start for start, end in islands)
        if widest < nuqta * 0.45:
            skipped_small += 1
            continue

        pen_poly = PolygonPen(font)
        glyph.draw(pen_poly)
        left_join, right_join = _joins.join_sides(glyph, pen_poly.polygons, join_height)

        target = targets.get((base, form)) if base is not None else None
        # A glyph with no join and no target has nothing to fit. With a
        # target it may still have inner runs — an isolated seen's kashida is
        # as real as a joined one's.
        if not (left_join or right_join) and target is None:
            continue

        runs = movable_runs(glyph, islands, left_join, right_join)
        if not runs:
            continue

        # Default fit: outer approaches down to the cap, inner runs untouched.
        new_lengths = []
        for start, end, kind in runs:
            length = end - start
            new_lengths.append(min(length, approach) if kind == "outer" else length)

        # Target fit: whatever the capped geometry still misses of the
        # classical width goes into the elongation run, in either direction.
        if target is not None:
            capped_ink = (bounds.xMax - bounds.xMin) + sum(
                new - (end - start) for (start, end, _), new in zip(runs, new_lengths))
            delta = target * nuqta - capped_ink
            if delta >= 0:
                # Growth is a kashida, and a kashida lives in ONE place. It
                # may grow a long way, but never past the classical ceiling.
                run = elongation_run(runs, islands)
                index = runs.index(run)
                new_lengths[index] = max(30.0, min(new_lengths[index] + delta, 12 * nuqta))
            else:
                # Shrinkage spreads over every movable run instead: taking it
                # all from one side would leave a stem letter's body sitting
                # lopsided between its two joins.
                movable = sum(new_lengths)
                if movable > 1:
                    factor = max(0.0, (movable + delta) / movable)
                    new_lengths = [max(30.0, length * factor) for length in new_lengths]

        delta_total = sum(new - (end - start)
                          for (start, end, _), new in zip(runs, new_lengths))
        if abs(delta_total) < 2:
            continue

        # An advance must stay positive and meaningful.
        new_width = round(glyph.width + delta_total)
        if new_width < nuqta:
            skipped_extreme += 1
            continue
        # And a pure shortening must not take almost the whole glyph —
        # backstop against a total detection misfire.
        if -delta_total > (bounds.xMax - bounds.xMin) * 0.82:
            skipped_extreme += 1
            continue

        if not args.dry_run:
            remap = make_piecewise_remap(runs, new_lengths)
            apply_remap_preserving_dots(glyph, remap, nuqta, islands=islands)
            # The advance follows the geometry, otherwise the letter changes
            # width but still occupies its old slot.
            glyph.width = new_width

        if delta_total < 0:
            shortened += 1
            total_removed += -delta_total
        else:
            extended += 1
            total_added += delta_total
        if args.verbose and abs(delta_total) > nuqta * 0.5:
            sign = "+" if delta_total > 0 else "-"
            print(f"  {glyph.name:20} adv {new_width - delta_total:5.0f} -> {new_width:5.0f}"
                  f"  ({sign}{abs(delta_total):4.0f})  islands {len(islands)}"
                  + (f"  target {target:.1f}" if target is not None else ""))

    if not args.dry_run:
        if os.path.abspath(args.out) != os.path.abspath(args.src) and os.path.exists(args.out):
            shutil.rmtree(args.out)
        font.save(args.out, overwrite=True)

    print(f"skipped {skipped_small} (widest island too small to trust), "
          f"{skipped_extreme} (fit would be extreme)")
    mean_removed = (total_removed / shortened) if shortened else 0
    mean_added = (total_added / extended) if extended else 0
    print(f"shortened {shortened} Arabic glyphs (mean {mean_removed:.0f} units), "
          f"extended {extended} (mean {mean_added:.0f} units)"
          + ("" if args.dry_run else f" -> {args.out}"))


if __name__ == "__main__":
    main()
