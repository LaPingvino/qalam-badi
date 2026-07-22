"""Standard diagnostic sheets, built on anatomy + render. Tracked replacements
for the throwaway out/show/yeh_*.py scripts.

    python3 workbench/sheets.py balance   out/show/wb_balance
    python3 workbench/sheets.py corner    out/show/wb_corner
    python3 workbench/sheets.py cardinal  out/show/wb_cardinal
    python3 workbench/sheets.py points  uniFEF2  out/show/wb_points   # single glyph
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anatomy import GlyphAnatomy, yeh_forms
from render import Sheet, CARD_COL

LEGEND_CARD = "  ".join(f'<tspan fill="{CARD_COL[c]}">&#9679; {c}</tspan>'
                        for c in ("N", "S", "E", "W"))


def _balance(cell, name):
    a = GlyphAnatomy.of(name)
    cell.outline(a.glyph)
    cell.side_walks(a)
    cell.caption(f"cup L : {a.cup.straight_angle:.0f}deg", "#159b3a")
    cell.caption(f"return: {a.ret.straight_angle:.0f}deg", "#ff7a00")
    cell.caption(f"delta : {a.balance_delta:+.0f}deg", "#111")


def _corner(cell, name):
    a = GlyphAnatomy.of(name)
    cell.outline(a.glyph)
    cell.side_walks(a, straight_only=False)
    cell.caption(f"cup {a.cup.straight_angle:.0f}deg -> corner", "#159b3a")
    cell.caption(f"ret {a.ret.straight_angle:.0f}deg -> corner", "#ff7a00")


def _cardinal(cell, name):
    a = GlyphAnatomy.of(name)
    cell.outline(a.glyph)
    cell.cardinals(a)


SHEETS = {
    "balance": (_balance, "Bowl balance (cup vs return incline)",
                '<tspan fill="#159b3a">&#9679; cup</tspan>  '
                '<tspan fill="#ff7a00">&#9679; return</tspan>  delta = return - cup'),
    "corner": (_corner, "Straight lay-down angle to the corner",
               "ring = corner where the side starts curving"),
    "cardinal": (_cardinal, "Cardinal direction-flips (outer body)",
                 "N=top  S=bottom  E=rightmost  W=leftmost   " + LEGEND_CARD),
}


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "balance"
    if kind == "points":
        name = sys.argv[2]
        stem = sys.argv[3] if len(sys.argv) > 3 else f"out/show/wb_{name}"

        def draw(cell, nm):
            a = GlyphAnatomy.of(nm)
            cell.outline(a.glyph)
            cell.points(a.glyph)
        png = Sheet([name], draw, title=f"{name} — numbered points",
                    ncol=1, colw=1400, glyph_box=800, letter_ids=False).save(stem)
        print(png)
        return
    draw, title, legend = SHEETS[kind]
    stem = sys.argv[2] if len(sys.argv) > 2 else f"out/show/wb_{kind}"
    png = Sheet(yeh_forms(), draw, title=title, legend=legend).save(stem)
    print(png)


if __name__ == "__main__":
    main()
