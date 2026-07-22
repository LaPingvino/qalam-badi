"""Glyph anatomy for Qalam Badi's bowl-shaped letters (yeh, seen, noon, ...).

One place for the vocabulary we worked out by hand, as a named API instead of
four throwaway scripts. Given a glyph it locates the landmarks and measures the
inclines we care about. See GLOSSARY.md for what each term means.

    from workbench.anatomy import GlyphAnatomy
    a = GlyphAnatomy.of("uniFEF2")           # loads the Regular by default
    a.trough                                  # Point at the bottom of the bowl
    a.cup.straight_angle, a.ret.straight_angle
    a.balance_delta                           # ret - cup, the lop-sidedness

Everything is measured on the BODY outline (diacritic dots excluded) of the
largest contour, flattened to a polyline via the pipeline's PolygonPen.
"""
import math
import os
import sys
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ufoLib2
import yaml
from ufoLib2.objects import Glyph

from _deps import PolygonPen, spans_at, base_and_form, YEH_SKELETON, ROOT

# --- constants -------------------------------------------------------------
DEFAULT_SRC = os.path.join(ROOT, "sources", "QalamBadi-Regular.ufo")
_cfg = yaml.safe_load(open(os.path.join(ROOT, "sources", "spacing.yaml")))
NUQTA = _cfg["module"]["nuqta"]          # 271 — the reference dot size
WRITING_LINE = 225                        # y where a return merges into the joiner
JOIN_TOP = 369                            # top of the join band
DOT_LIMIT = NUQTA * 1.35                  # contours smaller than this are diacritics

Point = namedtuple("Point", "x y")


# --- small geometry --------------------------------------------------------
def fit_slope(pts):
    """Least-squares slope of (x, y) points, in degrees from horizontal."""
    n = len(pts)
    if n < 2:
        return None
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    return None if den == 0 else math.degrees(math.atan(num / den))


def chord_angle(a, b):
    """Steepness of segment a->b: degrees from horizontal, sign = up/down,
    magnitude uses |dx| so a near-vertical reads ~90 regardless of direction."""
    return math.degrees(math.atan2(b[1] - a[1], abs(b[0] - a[0]) or 1))


def _perp(a, b, p):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1
    return abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / L


# --- body extraction -------------------------------------------------------
def body_only(glyph):
    """Copy of the glyph with diacritic-sized contours dropped."""
    body = Glyph(name=glyph.name)
    body.width = glyph.width
    for c in glyph.contours:
        xs = [p.x for p in c.points]
        ys = [p.y for p in c.points]
        if xs and max(xs) - min(xs) <= DOT_LIMIT and max(ys) - min(ys) <= DOT_LIMIT:
            continue
        body.contours.append(c)
    return body


def body_polygon(glyph, font):
    """Ordered, flattened polyline of the largest body contour."""
    body = body_only(glyph)
    big = max(body.contours, key=lambda c: len(c.points))
    solo = Glyph(name="_")
    solo.contours.append(big)
    pen = PolygonPen(font)
    solo.draw(pen)
    return [Point(*p) for p in max(pen.polygons, key=len)]


def silhouette(glyph, font, step=6):
    """(xs, top, bot): the jump-free upper and lower silhouette edges vs x."""
    body = body_only(glyph)
    pen = PolygonPen(font)
    body.draw(pen)
    b = body.getBounds(font)
    xs, top, bot = [], [], []
    x = b.xMin + 2
    while x < b.xMax:
        sp = spans_at(pen.polygons, x)
        if sp:
            xs.append(x)
            top.append(max(s[1] for s in sp))
            bot.append(min(s[0] for s in sp))
        x += step
    return xs, top, bot


# --- landmarks -------------------------------------------------------------
def _turns(poly, axis, prominence):
    """Prominence-filtered local extrema along a closed polyline on one axis.
    Returns [(index, 'max'|'min'), ...]."""
    n = len(poly)
    v = [p[axis] for p in poly]
    raw = []
    for i in range(n):
        a, b, c = v[(i - 1) % n], v[i], v[(i + 1) % n]
        if b > a and b >= c:
            raw.append([i, "max"])
        elif b < a and b <= c:
            raw.append([i, "min"])
    changed = True
    while changed and len(raw) > 2:
        changed = False
        for j in range(len(raw)):
            k = (j + 1) % len(raw)
            if abs(v[raw[j][0]] - v[raw[k][0]]) < prominence:
                raw.pop(k if k > j else j)
                changed = True
                break
    return [(i, kind) for i, kind in raw]


def cardinal_flips(poly, prominence=120):
    """Direction reversals: N=top, S=bottom (horizontal tangent); E=rightmost,
    W=leftmost (vertical tangent). Returns [(Point, 'N'|'S'|'E'|'W'), ...]."""
    out = []
    for i, kind in _turns(poly, 1, prominence):
        out.append((poly[i], "N" if kind == "max" else "S"))
    for i, kind in _turns(poly, 0, prominence):
        out.append((poly[i], "E" if kind == "max" else "W"))
    return out


# --- sides of the bowl -----------------------------------------------------
class SideWalk:
    """One wall of the bowl, walked from the trough outward along the outline.

    path          the ordered points, trough first
    corner_i      index in path where it stops being straight (starts curving)
    corner        that Point
    straight_angle  slope of the straight part only (trough -> corner), degrees
    full_angle      slope of the whole side (trough -> tip / writing line)
    """

    def __init__(self, path, tol=35):
        self.path = path
        self.tip = path[-1]
        self.full_angle = chord_angle(path[0], path[-1])
        k = 1
        for j in range(2, len(path)):
            if max(_perp(path[0], path[j], path[m]) for m in range(1, j)) > tol:
                break
            k = j
        self.corner_i = k
        self.corner = path[k]
        self.straight_angle = chord_angle(path[0], path[k])


def _walk(poly, i_trough, step, stop_y=WRITING_LINE):
    """Walk the outline from the trough in one direction until it reaches the
    writing line or turns back down past a sub-writing-line tip."""
    tr = poly[i_trough]
    n = len(poly)
    i = i_trough
    path = [tr]
    maxy = tr.y
    for _ in range(n // 2):
        i = (i + step) % n
        p = poly[i]
        path.append(p)
        if p.y >= stop_y:
            break
        if p.y < maxy - 80:
            path.pop()
            break
        maxy = max(maxy, p.y)
    return path


# --- the assembled anatomy -------------------------------------------------
_FONT_CACHE = {}


def _font(src):
    if src not in _FONT_CACHE:
        _FONT_CACHE[src] = ufoLib2.Font.open(src)
    return _FONT_CACHE[src]


class GlyphAnatomy:
    def __init__(self, glyph, font):
        self.name = glyph.name
        self.glyph = glyph
        self.font = font
        self.base, self.form = base_and_form(glyph)
        self.bounds = body_only(glyph).getBounds(font)
        self.polygon = body_polygon(glyph, font)

        n = len(self.polygon)
        i_tr = min(range(n), key=lambda i: self.polygon[i].y)
        self.trough = self.polygon[i_tr]

        # cup = the side toward decreasing x, return = toward increasing x
        step_ret = 1 if self.polygon[(i_tr + 1) % n].x > self.polygon[(i_tr - 1) % n].x else -1
        self.ret = SideWalk(_walk(self.polygon, i_tr, step_ret))
        self.cup = SideWalk(_walk(self.polygon, i_tr, -step_ret))

        self.cardinals = cardinal_flips(self.polygon)

    # --- named metrics ---
    @property
    def balance_delta(self):
        """return incline - cup incline (straight parts). ~0 symmetric bowl."""
        return self.ret.straight_angle - self.cup.straight_angle

    @property
    def west(self):
        """The leftmost landmark (highest |x| on the W side of the bowl)."""
        ws = [p for p, lab in self.cardinals if lab == "W"]
        return min(ws, key=lambda p: p.x) if ws else None

    @property
    def peaks(self):
        return [p for p, lab in self.cardinals if lab == "N"]

    def metrics(self):
        return {
            "cup_straight": round(self.cup.straight_angle),
            "ret_straight": round(self.ret.straight_angle),
            "balance_delta": round(self.balance_delta),
            "cup_full": round(self.cup.full_angle),
            "ret_full": round(self.ret.full_angle),
            "width": round(self.bounds.xMax - self.bounds.xMin),
            "height": round(self.bounds.yMax - self.bounds.yMin),
            "trough_y": round(self.trough.y),
        }

    @classmethod
    def of(cls, name, src=DEFAULT_SRC):
        font = _font(src)
        return cls(font[name], font)


def yeh_forms(src=DEFAULT_SRC):
    """The fina/isol yeh-family glyph names, sorted (our A..P set)."""
    font = _font(src)
    names = [g.name for g in font
             if base_and_form(g)[0] in YEH_SKELETON
             and base_and_form(g)[1] in ("fina", "isol") and g.contours]
    return sorted(names)


if __name__ == "__main__":
    import sys
    names = sys.argv[1:] or yeh_forms()
    hdr = f"{'glyph':<16}" + "".join(f"{k:>14}" for k in
                                     ("cup_straight", "ret_straight", "balance_delta"))
    print(hdr)
    for nm in names:
        a = GlyphAnatomy.of(nm)
        m = a.metrics()
        print(f"{nm:<16}" + "".join(f"{m[k]:>13}°" for k in
                                    ("cup_straight", "ret_straight", "balance_delta")))
