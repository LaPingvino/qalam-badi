"""Annotated glyph rendering for visual collaboration.

Draw a glyph (or a grid of them) with overlays — numbered points, cardinal
landmarks, side walks, arbitrary dots / lines / labels — to SVG then PNG.
Replaces the one-off render code in the yeh_* scratch scripts.

    from workbench.render import Sheet
    from workbench.anatomy import GlyphAnatomy, yeh_forms

    def draw(cell, name):
        a = GlyphAnatomy.of(name)
        cell.outline(a.glyph)
        cell.side_walks(a)
        cell.dot(a.trough, "#111", "trough")
        cell.caption(f"delta {a.balance_delta:+.0f}deg")

    Sheet(yeh_forms(), draw, title="Yeh anatomy").save("out/show/anatomy_grid")

Coordinates you pass to dot()/line()/polyline()/points are in GLYPH units and
are transformed automatically; text is drawn upright (never mirrored).
"""
import os
import subprocess

from fontTools.pens.svgPathPen import SVGPathPen

CARD_COL = {"N": "#d81b1b", "S": "#1b74d8", "E": "#159b3a", "W": "#ff7a00"}


class Cell:
    """One glyph panel. Builds SVG fragments; coordinates auto-transform."""

    def __init__(self, font, cx, cy, colw, glyph_box, header=""):
        self.font = font
        self.cx, self.cy, self.colw = cx, cy, colw
        self.glyph_box = glyph_box
        self.header = header
        self._body = []          # inside the flipped glyph transform
        self._screen = []        # screen-space (labels, captions)
        self._caption_n = 0
        self._tf = None          # (ox, scale, ybase, xMin, yMax)

    # -- transform -------------------------------------------------------
    def _fit(self, bnd):
        gh = bnd.yMax - bnd.yMin
        gw = bnd.xMax - bnd.xMin
        scale = self.glyph_box / max(gh, 1)
        ox = self.cx + (self.colw - gw * scale) / 2
        ybase = self.cy + 90 + self.glyph_box
        self._tf = (ox, scale, ybase, bnd.xMin, bnd.yMax)

    def tx(self, x, y):
        ox, scale, ybase, xMin, yMax = self._tf
        return ox + scale * (x - xMin), ybase + scale * (yMax - y)

    # -- layers ----------------------------------------------------------
    def outline(self, glyph, fill="#ececec", stroke="#c4c4c4"):
        from anatomy import body_only
        bnd = body_only(glyph).getBounds(self.font)
        self._fit(bnd)
        spen = SVGPathPen(None)
        glyph.draw(spen)
        ox, scale, ybase, xMin, yMax = self._tf
        self._body.append(
            f'<g transform="translate({ox:.1f},{ybase:.1f}) scale({scale:.4f},{-scale:.4f}) '
            f'translate({-xMin:.1f},{-yMax:.1f})">'
            f'<path d="{spen.getCommands()}" fill="{fill}" stroke="{stroke}" stroke-width="3"/></g>')

    def polyline(self, pts, color, width=24, opacity=0.9, dash=None):
        d = "M " + " L ".join("%.1f %.1f" % self.tx(p[0], p[1]) for p in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self._screen.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
                            f'stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"{da}/>')

    def line(self, a, b, color, width=10, dash="30 18", opacity=0.8):
        ax, ay = self.tx(a[0], a[1])
        bx, by = self.tx(b[0], b[1])
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self._screen.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
                            f'stroke="{color}" stroke-width="{width}"{da} opacity="{opacity}"/>')

    def dot(self, p, color, label="", r=22, filled=True):
        x, y = self.tx(p[0], p[1])
        if filled:
            self._screen.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}"/>')
        else:
            self._screen.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="white" '
                                f'stroke="{color}" stroke-width="9"/>')
        if label:
            self._screen.append(f'<text x="{x:.1f}" y="{y - r - 8:.1f}" font-size="34" fill="{color}" '
                                f'text-anchor="middle" font-family="sans-serif" font-weight="bold">{label}</text>')

    def points(self, glyph, numbered=True):
        """Numbered on/off-curve points (blue on-curve, orange control)."""
        n = 0
        for c in glyph.contours:
            for p in c.points:
                on = p.type is not None
                col = "#0a58ff" if on else "#e8890c"
                x, y = self.tx(p.x, p.y)
                r = 20 if on else 13
                self._screen.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="white" '
                                    f'stroke="{col}" stroke-width="4"/>')
                if numbered:
                    self._screen.append(f'<text x="{x:.1f}" y="{y + r*0.55:.1f}" font-size="{r*1.2:.0f}" '
                                        f'fill="{col}" text-anchor="middle" font-family="sans-serif" '
                                        f'font-weight="bold">{n}</text>')
                n += 1

    def cardinals(self, anatomy):
        for p, lab in anatomy.cardinals:
            self.dot(p, CARD_COL[lab], lab, r=22, filled=False)

    def side_walks(self, anatomy, cup="#159b3a", ret="#ff7a00", straight_only=False):
        for walk, col in ((anatomy.cup, cup), (anatomy.ret, ret)):
            if not straight_only:
                self.polyline(walk.path, col, width=8, opacity=0.35)
            self.polyline(walk.path[:walk.corner_i + 1], col, width=26, opacity=0.95)
            self.dot(walk.corner, col, "", r=28, filled=False)
        self.dot(anatomy.trough, "#111", "", r=22, filled=True)

    def caption(self, text, color="#333"):
        y = self.cy + 90 + self.glyph_box + 42 + self._caption_n * 40
        self._screen.append(f'<text x="{self.cx + 20}" y="{y}" font-size="34" fill="{color}" '
                            f'font-family="monospace">{text}</text>')
        self._caption_n += 1

    # -- assemble --------------------------------------------------------
    def svg(self):
        head = (f'<text x="{self.cx}" y="{self.cy + 80}" font-size="110" font-weight="bold" '
                f'fill="#111" font-family="sans-serif">{self.header[0]}</text>'
                if self.header else "")
        name = (f'<text x="{self.cx + 130}" y="{self.cy + 52}" font-size="34" fill="#555" '
                f'font-family="monospace">{self.header[1]}</text>'
                if self.header and len(self.header) > 1 else "")
        return "".join(self._body) + head + name + "".join(self._screen)


class Sheet:
    """A grid of glyph cells rendered to one PNG."""

    def __init__(self, items, draw, title="", legend="", ncol=4,
                 colw=740, rowh=760, glyph_box=300, letter_ids=True, src=None):
        self.items = list(items)
        self.draw = draw
        self.title = title
        self.legend = legend
        self.ncol = ncol
        self.colw = colw
        self.rowh = rowh
        self.glyph_box = glyph_box
        self.letter_ids = letter_ids
        from anatomy import _font, DEFAULT_SRC
        self.font = _font(src or DEFAULT_SRC)

    def save(self, path_stem, zoom=1.0):
        pad, top = 40, 180
        rows = (len(self.items) + self.ncol - 1) // self.ncol
        W = self.colw * self.ncol + 2 * pad
        H = top + self.rowh * rows + pad
        cells = []
        for k, item in enumerate(self.items):
            cx = pad + (k % self.ncol) * self.colw
            cy = top + (k // self.ncol) * self.rowh
            name = item if isinstance(item, str) else item[0]
            header = (chr(ord("A") + k), name) if self.letter_ids else ("", name)
            cell = Cell(self.font, cx, cy, self.colw, self.glyph_box, header)
            self.draw(cell, item)
            cells.append(cell.svg())
        head = (f'<text x="{pad}" y="70" font-size="46" font-weight="bold" '
                f'font-family="sans-serif">{self.title}</text>' if self.title else "")
        leg = (f'<text x="{pad}" y="130" font-size="38" font-family="sans-serif">{self.legend}</text>'
               if self.legend else "")
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="white"/>'
               f'{head}{leg}{"".join(cells)}</svg>')
        svgf, pngf = path_stem + ".svg", path_stem + ".png"
        os.makedirs(os.path.dirname(pngf) or ".", exist_ok=True)
        open(svgf, "w").write(svg)
        cmd = ["rsvg-convert", svgf, "-o", pngf]
        if zoom != 1.0:
            cmd[2:2] = ["-z", str(zoom)]
        subprocess.run(cmd, check=True)
        return pngf
