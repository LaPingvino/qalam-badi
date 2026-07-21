# Qalam Badi — design & engineering notes

This document records a few non-obvious design decisions, mainly so reviewers
(including Google Fonts onboarding) don't have to reverse-engineer them.

Qalam Badi is derived from [Courier
Badi](https://github.com/LaPingvino/courier-badi), and most of what follows was
inherited from it. The sections that are specific to Qalam Badi — the
proportional model, and the spacing system — come first.

## Proportional model

Qalam Badi is proportional. Its ancestor is not, and the difference is the
reason this project exists.

Advances are fitted to each glyph's ink, with sidebearings drawn from
[`sources/spacing.yaml`](../sources/spacing.yaml). `post.isFixedPitch` is
cleared and the PANOSE proportion byte is 3 (modern/proportional) rather than
the inherited 9 (monospaced); `hhea.numberOfHMetrics` is now the full glyph
count rather than 1. Those three declarations are corrected in
`scripts/make-proportional.py` rather than left to a downstream fixup, because
layout engines and PDF generators act on them and a font that claims fixed
pitch while shipping thousands of distinct advances gets laid out wrong.

**The stroke is never touched.** Glyphs are translated and their advances
changed; nothing is scaled. Where an outline does change — the serif narrowing
below — the transform is anchored on the stem so vertical stroke width is
mathematically invariant. Monolinearity is the property the whole design rests
on, since Qalam Badi's calligraphic character has to come from proportion
rather than from stroke contrast.

### Measured in nuqta

Spacing is denominated in the **nuqta**, the calligrapher's dot — the unit of
the classical Persian proportion system. This is not ornamental: the inherited
master already draws the Arabic nuqta at 271×289 units and the Latin period at
270×310, so a single dot module was already shared across the scripts. Using it
is what allows Latin, Cyrillic, Greek and Arabic to share one rhythm.

Two more inherited proportions are worth recording, because they mean rather
more of the system was already in place than we expected: the monolinear pen
measures **141 units**, and the alef stands **4.6 nuqta**. Classical sources put
the nastaʿlīq alef at 3 dots and the naskh alef at 5–6, so the inherited alef
sits between the two — which is roughly where this design wants to be anyway.

### Two distortions, opposite fixes

A monospace cell damages glyphs in both directions, and
`scripts/classify-widths.py` separates them by comparing each glyph's ink at the
serif band against its ink at mid x-height:

* **Too narrow.** The alef is a single 141-unit stroke in a 1228-unit cell.
  The outline is fine; re-fitting the advance is the entire fix (alef: 1228 →
  357).
* **Too wide.** Courier's `i` is a 141-unit stem carrying **910 units of
  serif** — the serifs were stretched until they reached the cell walls. Its
  ink really is that wide, so re-spacing achieves nothing and `i` would stay as
  wide as `m`. `scripts/narrow-serifs.py` compresses the flanks either side of
  the stem, pinning the stem, so the slab survives and the stroke does not
  change.

In the seed, every letter from `J` to `w` sat between 770 and 1112 units of ink
— a range of 1.4× across the whole alphabet. That flatness *is* the typewriter.
`i:m` was 0.93 and is now 0.43, against roughly 0.35–0.40 for a conventional
serif text face.

### Arabic joins are pinned, not spaced

A joining edge is not a sidebearing. An `.init`/`.medi`/`.fina` form carries its
connector exactly on the advance edge, and giving that edge any sidebearing
visibly pulls the script apart. Those edges are pinned to zero.

Join sides are **detected from the outlines** — ink reaching the advance edge
within a band around the baseline — rather than from a hand-maintained table,
so the detection stays correct when Courier Badi edits its Arabic upstream and
those changes are merged in. 643 glyphs carry a pinned join.

## Inherited: the monospace seed

The monospace master is retained as `sources/QalamBadi-Mono.ufo` and tracked
against the `upstream` remote. Everything below describes it, and applies to
Qalam Badi except where the proportional model above overrides it.

Every glyph in the seed advances **1228 units** (UPM 2048). It is strictly
monospaced: `post.isFixedPitch` is set, the PANOSE proportion byte is 9
(monospaced), and `hhea.numberOfHMetrics` is 1 (all glyphs share one width — a
valid and compact choice for a monospaced font; see
fonttools/fonttools#3014).

### Combining marks are zero-width overlays

Spacing/base glyphs advance 1228; **combining marks (Unicode categories Mn/Me)
advance 0**. They are drawn as overlays positioned to sit over the *preceding*
base cell, which is the standard model for combining marks and lets sequences
like `i` + U+0301 stack correctly instead of consuming a second cell.

The common accented letters used for Bahá'í and European orthographies
(á í ú ñ …) are **precomposed** single glyphs at the normal 1228 width, so the
zero-width marks matter only for arbitrary base+mark combinations.

The Arabic tashkil **isolated presentation forms** in U+FE70–U+FE7F are *not*
combining marks — they are standalone spacing forms and keep the 1228 width and
are excluded from the GDEF mark class.

> Note: this zero-width model was introduced deliberately. If a fontbakery run
> or a reviewer flags mark widths, this is the intended design, not an artifact.

## Arabic shaping

Arabic OpenType features are **generated**, not hand-written, by
`scripts/arabic-features` (Go). See its package doc for details. In short:

- `init` / `medi` / `fina` single substitutions are emitted for every base
  letter whose positional-form glyph exists in the UFO — either the Unicode
  presentation form (from the Unicode Character Database) or the
  `<base>.init/.medi/.fina` naming convention used for extended letters that
  have no Unicode presentation form (e.g. Pashto U+0681, U+0685).
- The mandatory **lam-alef** ligatures are matched against the *positional*
  forms (`lam.init`/`lam.medi` + `alef.fina`), because HarfBuzz applies
  init/medi/fina **before** `rlig`; rules written against the base letters
  never match and the ligature silently fails to form.
- The `GDEF` mark class is built from Unicode categories (Mn/Me), excluding the
  U+FE70–FE7F isolated forms noted above.

Regenerate after adding/removing Arabic glyphs:

```
make arabic-features         # rewrite the managed block in features.fea
make arabic-features-check   # verify it is up to date (CI-friendly)
```

The generated block lives between markers in
`sources/QalamBadi-Regular.ufo/features.fea`; hand-written features outside
the markers (see below) are preserved.

## Stylistic sets

- **ss01 — Dotless kaf.** Isolated and final kaf carry a small internal stroke;
  the initial/medial forms are already strokeless. ss01 swaps only the isolated
  (`uni0643` → `kafDotless_ar`) and final (`uniFEDA` → `kafDotless_ar.fina`)
  forms to their dotless variants.
- **zero — Slashed zero.**

## Italic

The Italic is generated from the (corrected) Regular by `scripts/make-italic.py`,
which shears it by the italic angle (10°). This keeps a single source of truth:
every correction to the Regular flows into the Italic automatically, and the
lowercase `a` is simply the roman `a` slanted (the original bespoke italic `a`
was inconsistent, and history confirms there was never a single-story form).
Courier Prime's italic is itself essentially an oblique, so this matches the
original closely. Genuine cursive forms that differ from a plain slant live in
`sources/italic-overrides/` and are grafted on after shearing — currently just
the descending `f`; drop a hand-drawn `.glif` there (e.g. a single-story `a`) to
add more. Regenerate with `make italic`. A STAT table (`scripts/add-stat.py`,
post-build) declares the `ital` axis linking Roman↔Italic.

## Variable font

The **shipping** family is a clean **wght + ital** design
(`sources/QalamBadi.designspace`, four masters). gftools splits italic into
its own file (the GF convention), producing `QalamBadi[wght].ttf` and
`QalamBadi-Italic[wght].ttf`. This is the Google-Fonts submission and passes
the googlefonts Fontbakery profile with **0 errors / 0 failures** — no
parametric-axis or family-packaging issues. `make build` builds it.

### Contrast (XOPQ) axis — bonus build

The experimental contrast axis lives in a **separate** designspace
(`sources/QalamBadi-Contrast.designspace`, config `sources/contrast.yaml`,
built by `make contrast-vf` into `fonts-contrast/`). It adds the registered
parametric **XOPQ** ("vertical stroke thickness") axis. It is shipped only as a
release extra and previewed by `documentation/contrast-specimen.html`
(`scripts/make-contrast-specimen.py`), kept out of the main build so the GF
checks' known crashes on parametric axes never touch the clean submission.

The axis needs a **contrast sibling at every weight**, not just Bold — otherwise
the XOPQ endpoints at regular weight both alias the plain Regular and the axis
does nothing until Bold. `scripts/make-contrast-master.py` builds each sibling
as a **weight-neutral** modulation of its base master (thicken verticals `+dx`,
thin horizontals `-dy`), so XOPQ reads as contrast (orthogonal to wght) at any
weight. All masters share one point structure, so they interpolate; the winding
normalization above is what makes that possible across scripts. `make masters`
regenerates every master (base weights + contrast siblings).

## Contour winding

The Latin was digitized with the PostScript convention (outer CCW, holes CW),
but the merged Cyrillic/Greek/Arabic — and some individual glyphs like the
Vietnamese precomposed letters — came in wound the other way, sometimes only in
part (base backwards, accents correct). Inconsistent winding silently broke the
emboldening (which offsets along the contour normal), thinning those glyphs
instead of thickening them. `scripts/normalize-winding.py` resolves each glyph's
true filled region with skia-pathops (`simplify`) and rewrites it with canonical
winding (converting the result back to cubics), which also merges overlaps. Run
it on the Regular before regenerating the other masters.

`f` is **excluded** (`SKIP` in the script): it has an interpolation partner — the
descending italic `f` in `sources/italic-overrides/` — that shares its
two-contour structure. `simplify()` would merge those two contours into one and
break the match, so the roman `f` keeps its original (already-correct, native
Latin) winding untouched, and roman ↔ descending-italic `f` interpolate.

## Bold (emboldening)

The Bold is generated from the Regular by `scripts/make-bold.py`, which dilates
the outlines: every point is offset outward along the right-hand normal of its
travel direction, which grows the outer contours and shrinks the counters, so
strokes thicken while the advance width (and thus the strict monospace) is
unchanged. Because the width can't change, this weight axis behaves like a GRAD
(grade): bolding never reflows text. Bold Italic is the emboldened Italic. The
Regular and Bold are interpolation-compatible (point structure is preserved), so
they are the two masters of the `wght` axis. Regenerate with `make masters`.

## seen/sheen/sad teeth widening

`scripts/widen-seen-family.py` spreads the scrunched teeth of the seen/sheen/sad
family so they fill the cell, to the **same teeth width in every positional
form** and always inside the box. Isolated/final forms spread the teeth left and
let the free terminal tail smuggle out past the left edge; initial/medial forms
stretch only the teeth *cluster* and compress the baseline connector(s), which
stay pinned to the cell edge so joins line up and nothing overhangs into the
next letter. An x-direction inset thins the fattened vertical stems back to a
constant, monolinear stroke; the dots keep their shape and are only
repositioned. The family is derived from Unicode letter names, so every dotted
variant (two-dot, four-dot, …) is covered. Run once from pristine glyphs.

The stem inset must **not** touch the baseline join connectors: a point that
sits on a cell edge (x = 0 or x = 1228) is a connector to the neighbouring
letter and is pinned in place, because insetting it would pull the join stroke
inward and leave a visible gap between letters. (This was a real bug — medial and
final forms ended up ~26 units short of the edge and didn't quite touch.)

## Cyrillic diacritic centering

The Cyrillic merged from Novikov's fork stored accented letters as standalone
outlines, several with the top mark shifted off-center. `scripts/
center-cyrillic-marks.py` recenters the safe cases (symmetric marks —
breve/dieresis/macron/double-acute — over non-dotted bases). It is idempotent
and can be re-run if Cyrillic is re-imported.
