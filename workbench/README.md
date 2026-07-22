# workbench

Tooling for subjective glyph-shape work on Qalam Badi: **measure** glyph
anatomy, **render** annotated glyphs for visual review. Lives here (tracked)
rather than `out/` (git-ignored) so it survives.

## Layout

| file | what |
|------|------|
| `anatomy.py` | the measurement library — landmarks + named metrics for the bowl letters. `GlyphAnatomy.of("uniFEF2")` |
| `render.py`  | annotated glyph → SVG/PNG: numbered points, cardinal landmarks, side walks, dots/lines/labels. `Sheet(...).save(...)` |
| `sheets.py`  | ready-made diagnostic sheets (balance / corner / cardinal / points) |
| `GLOSSARY.md`| the shared shape vocabulary (trough, cup, return, corner, delta, N/S/E/W) |
| `TOOLKIT.md` | tooling & strategy: what we use, what we should adopt, the gaps, and a brief for a new Linux font tool |
| `_deps.py`   | loads the hyphen-named `scripts/` helpers we build on |

## Use

```bash
. venv/bin/activate
python3 workbench/anatomy.py                       # metrics table for all yeh forms
python3 workbench/sheets.py corner   out/show/wb_corner
python3 workbench/sheets.py cardinal out/show/wb_cardinal
python3 workbench/sheets.py points uniFEF2 out/show/wb_pts   # one glyph, numbered
```

Renders go to `out/show/` (git-ignored) — they're for showing, not keeping.

## Tooling strategy

See **`TOOLKIT.md`** for the full picture from three 2026-07 surveys (Eli Heuer's
tooling, the headless CLI font ecosystem, UFO-native font IDEs). Short version:
we already own most of the Google stack including a measurement toolkit
(`statisticsPen`, `beziers`, `kurbopy`) we partly reinvented here; the one real
gap is **stroke skeleton / medial-axis**, unsolved by any off-the-shelf tool —
ours to build. `TOOLKIT.md` §6 is a brief for a possible new Linux font tool.
