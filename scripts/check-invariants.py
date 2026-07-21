#!/usr/bin/env python3
"""Assert the design invariants that every past regression violated.

Every visible bug this project has shipped broke a rule that was written down
in prose but enforced by nobody: a stroke got fattened, a dot got squashed or
lost, a mark drifted off its base, a tail was clipped by the line metrics, a
derived master fell out of interpolation. Each was caught days later by a human
looking at a specimen. This script turns the prose into a gate.

It reads the SOURCE masters, not the built fonts, so it runs in a second and
can sit in front of every commit. Each check corresponds to a specific incident:

  module        the nuqta and pen the whole system is denominated in are still
                what spacing.yaml claims — an upstream merge that shifts the
                seed silently reinterprets every measurement (guarded already
                in make-proportional; here it also gates on its own).
  masters       Regular / Italic / Bold / BoldItalic have identical point
                structure, so the variable font interpolates. This is the
                exact check fontmake runs at build time — running it here means
                a desynced Bold fails in one second instead of three minutes,
                the way the ring-trim commit did.
  descender     no glyph's ink falls below the declared descender except the
                handful that are known to and declared in spacing.yaml. This is
                the check that would have caught ya clipping years early.
  joins         the Arabic still has one dominant join height; if it stops
                having one, every connector transform is resting on sand.
  pen           the alef is still one pen wide — the monolinearity that is the
                whole Courier inheritance we are keeping.

Exit status is nonzero if any check fails, so `make check` and CI can gate.

Usage:
    python3 scripts/check-invariants.py
    python3 scripts/check-invariants.py --src-dir sources
"""

import argparse
import os
import sys

import ufoLib2
import yaml

from importlib.machinery import SourceFileLoader

_here = os.path.dirname(os.path.abspath(__file__))
_classify = SourceFileLoader(
    "classify_widths", os.path.join(_here, "classify-widths.py")).load_module()
_joins = SourceFileLoader("joins", os.path.join(_here, "joins.py")).load_module()

PolygonPen = _classify.PolygonPen

# The four masters that interpolate; the contrast set has its own designspace.
INTERPOLATION_MASTERS = ("Regular", "Italic", "Bold", "BoldItalic")

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


class Report:
    def __init__(self):
        self.failed = 0

    def ok(self, check, detail=""):
        print(f"  {GREEN}PASS{RESET} {check:12} {detail}")

    def fail(self, check, detail):
        print(f"  {RED}FAIL{RESET} {check:12} {detail}")
        self.failed += 1

    def note(self, detail):
        print(f"       {YELLOW}note{RESET} {detail}")


def contour_signature(glyph):
    """Per-contour point counts plus component count — what interpolation needs
    to match. Order matters, so this is a list, not a set."""
    return ([len(list(c.points)) for c in glyph.contours], len(glyph.components))


def check_module(font, config, report):
    nuqta = config["module"]["nuqta"]
    pen = config["module"]["pen"]
    for name in ("uni0628", "uni062A", "uni0646"):
        glyph = font.get(name)
        if glyph is None or not glyph.contours:
            continue
        dots = [max((p.x for p in c.points), default=0) - min((p.x for p in c.points), default=0)
                for c in glyph.contours]
        dots = [w for w in dots if w < nuqta * 1.5]
        if not dots:
            continue
        measured = max(dots)
        if abs(measured - nuqta) > 12:
            report.fail("module", f"{name} nuqta measures {measured:.0f}, "
                                  f"spacing.yaml says {nuqta}")
            return
        report.ok("module", f"nuqta {nuqta}, pen {pen} (measured {measured:.0f} on {name})")
        return
    report.note("module: no reference glyph found to measure the nuqta")


def check_masters(src_dir, report):
    fonts = {}
    for name in INTERPOLATION_MASTERS:
        path = os.path.join(src_dir, f"QalamBadi-{name}.ufo")
        if os.path.isdir(path):
            fonts[name] = ufoLib2.Font.open(path)
    if "Regular" not in fonts or len(fonts) < 2:
        report.note("masters: fewer than two interpolation masters present")
        return
    reference = fonts["Regular"]
    ref_sig = {g.name: contour_signature(g) for g in reference}
    total_bad = 0
    for name, font in fonts.items():
        if name == "Regular":
            continue
        bad = []
        for gname, sig in ref_sig.items():
            other = font.get(gname)
            if other is None:
                bad.append(f"{gname} (missing)")
            elif contour_signature(other) != sig:
                bad.append(gname)
        if bad:
            total_bad += len(bad)
            report.fail("masters", f"Regular vs {name}: {len(bad)} incompatible "
                                   f"(e.g. {', '.join(bad[:4])})")
        else:
            report.ok("masters", f"Regular vs {name}: compatible ({len(ref_sig)} glyphs)")
    if total_bad == 0:
        report.ok("masters", "all masters interpolate")


def check_descender(font, config, report):
    floor = font.info.openTypeOS2TypoDescender
    if floor is None:
        report.note("descender: font declares none")
        return
    allow = set((config.get("checks") or {}).get("descender_allow") or [])
    offenders = []
    for glyph in font:
        if glyph.width == 0 or not (glyph.contours or glyph.components):
            continue
        bounds = glyph.getBounds(font)
        if bounds is not None and bounds.yMin < floor and glyph.name not in allow:
            offenders.append((round(bounds.yMin), glyph.name))
    if offenders:
        offenders.sort()
        report.fail("descender", f"{len(offenders)} glyph(s) clip below {floor}: "
                                 + ", ".join(f"{n} ({y})" for y, n in offenders[:6]))
    else:
        report.ok("descender", f"nothing clips below {floor} "
                               f"({len(allow)} known exceptions allowed)")
    # Flag allowlist drift so the list cannot rot: an entry that no longer
    # clips should be removed.
    stale = []
    for name in allow:
        glyph = font.get(name)
        if glyph is None:
            stale.append(f"{name} (absent)")
            continue
        bounds = glyph.getBounds(font)
        if bounds is not None and bounds.yMin >= floor:
            stale.append(f"{name} (now clears)")
    if stale:
        report.note("descender_allow entries no longer needed: " + ", ".join(stale))


def check_joins(font, report):
    height = _joins.measure_join_height(font, PolygonPen)
    if height is None:
        report.fail("joins", "no single dominant Arabic join height")
    else:
        report.ok("joins", f"join height y={height[0]:.0f}..{height[1]:.0f}")


def check_pen(font, config, report):
    pen = config["module"]["pen"]
    alef = font.get("uni0627")
    if alef is None or not alef.contours:
        report.note("pen: no alef to measure")
        return
    # The alef is a single vertical stem; the width of its main contour is one
    # pen. Measured at mid-height to avoid the softened corners at top and foot.
    bounds = alef.getBounds(font)
    if bounds is None:
        return
    mid = (bounds.yMin + bounds.yMax) / 2
    poly = PolygonPen(font)
    alef.draw(poly)
    transposed = [[(y, x) for x, y in p] for p in poly.polygons]
    spans = _joins.spans_at(transposed, mid)
    if not spans:
        report.note("pen: alef has no ink at mid-height")
        return
    width = min(b - a for a, b in spans)
    if abs(width - pen) > 18:
        report.fail("pen", f"alef stem measures {width:.0f}, pen is {pen} "
                           f"— monolinearity broken")
    else:
        report.ok("pen", f"alef stem {width:.0f} ~= pen {pen}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src-dir", default="sources")
    parser.add_argument("--config", default="sources/spacing.yaml")
    args = parser.parse_args()

    with open(args.config) as handle:
        config = yaml.safe_load(handle)

    regular_path = os.path.join(args.src_dir, "QalamBadi-Regular.ufo")
    if not os.path.isdir(regular_path):
        print(f"no Regular master at {regular_path}; run `make proportional` first")
        return 1
    regular = ufoLib2.Font.open(regular_path)

    print("Design invariants:")
    report = Report()
    check_module(regular, config, report)
    check_masters(args.src_dir, report)
    check_descender(regular, config, report)
    check_joins(regular, report)
    check_pen(regular, config, report)

    if report.failed:
        print(f"\n{RED}{report.failed} invariant(s) violated.{RESET}")
        return 1
    print(f"\n{GREEN}All invariants hold.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
