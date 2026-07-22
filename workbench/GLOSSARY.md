# Qalam Badi shape vocabulary

Shared language for glyph-shape work, so an instruction like "cap the left at W"
is unambiguous. All terms are implemented in `anatomy.py`; measured in font
units on the **body** outline (diacritic dots excluded) of the largest contour.

## Reference lines & sizes

| term | value | meaning |
|------|------:|---------|
| **nuqta** | 271 | the reference dot; the unit of the design grid |
| **pen** | 141 | nominal stroke thickness |
| **writing line** | y = 225 | where a return merges back into the joiner |
| **join top** | y = 369 | top of the join band (connectors live in 225–369) |
| **dot limit** | 1.35·nuqta | contours smaller than this are treated as diacritics |

## Bowl anatomy (yeh, seen, noon, …)

The joined bowl letters share one skeleton. Walking the body outline:

- **trough** — the lowest point of the bowl (cardinal **S**). The anchor for
  both side walks. `a.trough`
- **cup** — the side of the bowl toward **decreasing x** (the left wall),
  walked upward from the trough. `a.cup`
- **return** — the side toward **increasing x** (the right wall), walked from
  the trough up to the terminal / writing line. `a.ret`
- **corner** — the point where a side stops being straight and starts curving
  into the terminal. Found by perpendicular deviation from the trough→point
  chord exceeding a tolerance (35u). `a.cup.corner`, `a.ret.corner`
- **tip** — the far end of a side walk (writing line, or a sub-line terminal
  peak). `a.cup.tip`

## Slopes (all in degrees from horizontal; |dx| so vertical ≈ 90°)

- **straight lay-down angle** — slope of the *straight part only*, trough →
  corner. The honest "how much does this side lay down" number, uncontaminated
  by the terminal curve. `a.cup.straight_angle`, `a.ret.straight_angle`
- **full angle** — slope of the whole side, trough → tip. `a.*.full_angle`
- **balance / delta** — `return.straight − cup.straight`. The bowl's
  lop-sidedness. ~0 is a symmetric bowl; our wide "laid-out" finals sit around
  −10, the compact isolated forms around +13. `a.balance_delta`

## Cardinal flips

Direction reversals on the body outline, prominence-filtered (default 120u):

- **N** top / **S** bottom — horizontal tangent (y reverses)
- **E** rightmost / **W** leftmost — vertical tangent (x reverses)

Because the outline is a double-walled ribbon, flips usually come in pairs (two
W's down the back, an N+E cluster at the connector). `a.cardinals`,
`a.west` (the leftmost W), `a.peaks` (the N's).

## The one rule (from NEXT.md)

> Anything that is a **shape** must be **translated**. Only **strokes** may be
> **remapped**.

Scaling a stroke or loop doubles its thickness (the "fat seen" failure). When a
construction moves ink, move shapes rigidly and remap stroke paths — never scale
them.
