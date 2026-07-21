# Qalam Badi

[![Fontbakery](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FLaPingvino%2Fqalam-badi%2Fgh-pages%2Fbadges%2Foverall.json)](https://LaPingvino.github.io/qalam-badi/fontbakery/fontbakery-report.html)
[![Latest Release](https://img.shields.io/github/v/release/LaPingvino/qalam-badi)](https://github.com/LaPingvino/qalam-badi/releases/latest)
[![License: OFL-1.1](https://img.shields.io/badge/License-OFL%201.1-lightgreen.svg)](https://scripts.sil.org/OFL)

Qalam Badi is a **proportional** Bahá'í text family, leaning toward the hand of
**Mishkín-Qalam** — the calligrapher and Apostle of Bahá'u'lláh whose
*Yá Bahá'u'l-Abhá* is the best-known piece of Bahá'í lettering there is.

It is a derivative of [Courier Badi](https://github.com/LaPingvino/courier-badi),
which remains its own project and continues on its own path. Where Courier Badi
is a monospace typewriter face built for screenplays, Qalam Badi takes the same
outlines somewhere else entirely.

**The stroke stays monolinear.** This is the point of the whole exercise, and it
is worth being explicit about. A calligraphic face would normally reach for
stroke contrast — thick verticals, thin horizontals, a visible pen angle. Qalam
Badi deliberately does not. Courier's uniform stroke is inherited untouched, and
every calligraphic quality has to be earned through **proportion and rhythm**
instead: relative widths, the reach of a final's tail, how tightly letters join,
how much air a word gets. The constraint is the design.

## Heritage

Qalam Badi sits at the end of a chain, and each link is worth naming:

| | |
|---|---|
| **Courier Prime** | by [Quote-Unquote Apps](https://quoteunquoteapps.com), Reserved Font Name *Courier Prime Source*. The Courier model, redrawn for screenplays. |
| **[Courier Badi](https://github.com/LaPingvino/courier-badi)** | adds the characters Bahá'í usage needs in the widest sense — the Bahá'í star, Arabic, Persian, Cyrillic, Greek, extended Latin, combining diacritics — plus Italic, Bold, a variable font, and a long campaign of Fontbakery correctness work. Still monospace, still maintained. |
| **Qalam Badi** | this project. Proportional, and reaching toward Mishkín-Qalam. |

Courier Badi is not a fossil in here. It is tracked as the `upstream` remote, its
monospace master is kept in the sources as `QalamBadi-Mono.ufo`, and the
proportional family is *generated from it by script*. That is a deliberate
architectural choice: it means Courier Badi's ongoing Arabic shaping and
Fontbakery fixes can be merged in and flow straight through to Qalam Badi,
rather than the two projects drifting apart after the fork.

```
git fetch upstream
git merge upstream/main        # Courier Badi fixes land in the mono seed
make masters                   # and propagate through the whole family
```

## About

I am a Bahá'í, customer support agent by trade and programmer in my free time and former jobs. I am a long time big fan of the Fountain screenplay markup language and have written a command line tool for this that uses Courier Prime to generate screenplay PDFs — that tool is what Courier Badi serves. Qalam Badi is for everything that is *not* a screenplay: running text, prayer books, anywhere the Bahá'í writings want to look like they were written by a hand rather than a machine.

## Building

Fonts are built automatically by GitHub Actions - take a look in the "Actions" tab for the latest build.

If you want to build fonts manually on your own computer:

* `make build` will produce font files.
* `make test` will run [FontBakery](https://github.com/googlefonts/fontbakery)'s quality assurance tests.
* `make proof` will generate HTML proof files.

The proof files and QA tests are also available automatically via GitHub Actions - look at https://LaPingvino.github.io/qalam-badi.

## Where things stand

[`NEXT.md`](NEXT.md) carries the working state: how to get building on a fresh
machine, the measured facts the design rests on, the open issues, and the plan
for the Arabic. Start there when picking the project back up.

## Design & engineering notes

Non-obvious design decisions (the monospace model, **zero-width combining
marks**, the generated Arabic shaping features, stylistic sets, Cyrillic mark
centering) are documented in [documentation/design-notes.md](documentation/design-notes.md).
Arabic OpenType features are generated from the UFO by `scripts/arabic-features`
(Go) — run `make arabic-features` after changing Arabic glyphs.

## How the proportional family is built

Nothing in `sources/QalamBadi-Regular.ufo` is hand-edited. The chain is:

```
QalamBadi-Mono.ufo          the Courier Badi master, tracked against upstream
   │
   ├─ narrow-serifs.py      pull in serifs that were stretched to fill the cell
   ├─ make-proportional.py  fit advances to ink, in nuqta; pin Arabic joins
   │
   └─ QalamBadi-Regular.ufo ─┬─ make-italic.py  → Italic
                             ├─ make-bold.py    → Bold, Bold Italic
                             └─ make-contrast-master.py → XOPQ siblings
```

* `make proportional` regenerates the Regular from the seed.
* `make masters` regenerates the whole family.
* `make widths` prints the classification the spacing targets come from.

Every spacing decision lives in one reviewable file,
[`sources/spacing.yaml`](sources/spacing.yaml), rather than being scattered
across 2318 `.glif` files — it is meant to be read as the design record.

### Measured in nuqta

The spacing system is denominated in the **nuqta**, the calligrapher's dot, the
unit the classical Persian proportion system uses. That is not decoration. The
inherited master already draws the Arabic nuqta at 271×289 units and the Latin
period at 270×310 — one dot module, already shared across the scripts. Building
on it is what lets Latin, Cyrillic, Greek and Arabic share a rhythm instead of
having four unrelated ones. The monolinear pen measures 141 units and the alef
stands 4.6 nuqta tall, which is squarely inside the classical range; a good deal
of the proportion system was sitting in Courier Badi already.

## Changelog

### Qalam Badi

**21 July 2026. Version 0.100**
- **Forked from Courier Badi v1.010** and made proportional. The monospace
  master is kept as the seed and the family is generated from it, so upstream
  Courier Badi work stays mergeable.
- **Two distortions, opposite fixes.** `scripts/classify-widths.py` separates
  glyphs the cell made *too narrow* (alef, period — re-fitting the advance is
  the whole fix; alef goes 1228 → 357) from those it made *too wide* (Courier's
  `i` is a 141-unit stem carrying 910 units of serif — re-spacing cannot help,
  so the outline is narrowed). `i:m` was 0.93 and is now 0.43.
- **Serifs narrowed without touching the stroke.** `scripts/narrow-serifs.py`
  compresses the flanks either side of the stem while pinning the stem itself,
  so vertical stroke width is mathematically unchanged and the face stays
  monolinear.
- **Arabic joins pinned to the advance** rather than given a sidebearing, and
  detected from the outlines rather than a hand-kept table, so they survive
  upstream edits. 643 glyphs carry a pinned join.

### Inherited from Courier Badi

The history below belongs to [Courier
Badi](https://github.com/LaPingvino/courier-badi) and is kept because Qalam Badi
inherits every one of these fixes through its monospace seed.

**20 July 2026. Version 1.010**
- **Submission-ready split.** The shipping family is now a clean **wght + ital**
  variable font (`QalamBadi[wght].ttf` + `QalamBadi-Italic[wght].ttf`) with
  four static instances — this passes the Google Fonts Fontbakery profile with
  **0 errors and 0 failures**. The experimental **contrast (XOPQ)** axis moved
  to a **bonus** build (`make contrast-vf`, its own family) shipped only in the
  release and previewed by an interactive [specimen](contrast-specimen.html), so
  it never blocks the clean submission.
- **Contrast axis actually modulates.** Previously the XOPQ endpoints at regular
  weight aliased the plain Regular, so the axis did nothing until Bold. It now
  has a weight-neutral contrast sibling at every weight (thick verticals, thin
  horizontals via `scripts/make-contrast-master.py`), so it reads across the
  whole range.
- **Arabic joins fixed.** The seen/sheen/sad widening left the baseline
  connectors ~26 units short of the cell edge (the stem inset was pulling the
  join strokes in), so letters didn't quite touch. Connectors are now pinned to
  the edge and every positional form joins flush.
- **Descending italic `f`.** The genuine cursive `f` is back in the Italic and
  interpolates cleanly (the roman `f` is kept at its two-contour structure rather
  than being merged by overlap-removal).

**20 July 2026. Version 1.000**
- **Variable font.** Two variable fonts (upright + italic) with a **wght** axis
  (400–700) and an **XOPQ** axis (88–130) that tunes vertical-stroke thickness —
  i.e. the contrast/modulation from the 0.950 experiment, mapped onto the
  registered parametric axis. Four static instances (Regular/Bold/Italic/Bold
  Italic) ship alongside. Version reaches 1.000 (clearing the last version
  check). All font-correctness checks pass; the remaining Fontbakery items are
  Google-Fonts-submission packaging (statics + VFs under one family) and the GF
  checks' known crashes on parametric axes.

**20 July 2026. Version 0.950**
- Experimental **Contrast** sample: a directional emboldening (thick verticals,
  thin horizontals via `make-bold --contrast`) that turns the offset imbalance
  into stroke modulation. Also normalized all contour winding via skia-pathops
  so the Bold thickens uniformly across every script and accent.

**20 July 2026. Version 0.900**
- Added **Bold** and **Bold Italic** (issue #8). The Bold is generated from the
  Regular by dilating the outlines (`scripts/make-bold.py`); because the font is
  strictly monospace the advance widths don't change, so bolding behaves like a
  grade and never reflows text. Also widened the sad/dad loop to match the seen
  (the loop counter was mis-detected as a dot). STAT now declares wght + ital.

**20 July 2026. Version 0.800**
- Reintroduced the **Italic** (issue #8). It is generated from the corrected
  Regular as a sheared oblique (`scripts/make-italic.py`), so it inherits every
  fix and harmonises the `a`; the genuine descending italic `f` is grafted from
  `sources/italic-overrides/`. Added a STAT table declaring the `ital` axis.

**20 July 2026. Version 0.750**
- Widened the cramped seen/sheen/sad teeth family (google/fonts#6491,
  @eliheuer). The teeth are spread ~1.5× to the **same width in every positional
  form** and kept inside the cell: isolated/final let the free tail smuggle out
  on the left; initial/medial stretch only the teeth cluster and compress the
  connectors (held at the cell edge, so joins line up and nothing overhangs). An
  x-direction inset keeps the stroke **monolinear**, and the dots keep their
  shape and are only repositioned. Covers seen/sheen/sad/dad and every dotted
  variant via `scripts/widen-seen-family.py`.

**20 July 2026. Version 0.700**
- Arabic shaping overhaul: lam-alef ligatures now form correctly, Pashto and
  other extended letters link up (addresses the google/fonts#6491 Pashto
  report), via a new generated feature pipeline (`scripts/arabic-features`, Go).
- Fontbakery: all correctness FAILs resolved (the version-string check will
  report until the 1.000 release below); several WARNs cleared.
- Combining marks made zero-width overlays; added a `meta` table; PANOSE,
  fsType, vertical metrics and copyright corrected.
- Cyrillic: recentered symmetric top diacritics (breve/dieresis/macron).
- Added coverage: capital koppa, Ukrainian ʼ, Vietnamese combining horn, and
  Church Slavic archaic Cyrillic. New `ss01` "Dotless kaf" stylistic set.
- See [documentation/design-notes.md](documentation/design-notes.md).

Roadmap: **0.800** reintroduces the Italic; **1.000** ships a wght/ital
variable font (and bumps the version to satisfy the last Fontbakery check).

**24 October 2025. Version 0.600**
- Complete Arabic features enhancement through 5 incremental levels
- Extended Arabic character support (Unicode 075x range)
- Comprehensive contextual forms (.fina, .init, .medi) for Arabic script
- Enhanced language support for Arabic (ARA), Farsi (FAR), and Urdu (URD)
- 625 lines of OpenType features with 320 optimized substitution rules
- Added incremental enhancement automation tool
- Production-ready Arabic typography with backward compatibility

**13 October 2024. Version 0.529**
- Prerelease Greek improvements

**22 July 2023. Version 0.520**
- Fixed the gaps in Italic. Corrected skew for Italic. Corrected position of Bahá'í star in Italic.

**14 July 2023. Version 0.510**
- Corrected the width of the merge so it is actually true monospace. Kinda breaks the catalan middle dot,
  not sure what to do about that, might add a ligature for that later.

**13 July 2023. Version 0.500**
- Merged in Arabic, Greek and extended Latin from No Name Fixed, thanks for the suggestion @Eli Hauser.
  The fit is surprisingly good, but I will probably fix up some characters like the u used for Vietnamese
  and some Greek characters that look too thin, if the monospace limitations permit this.

**13 July 2023. Version 0.400**
- Cyrillic merged in from Novikov's Courier Prime fork

**4 July 2023. Version 0.300**
- Dot below letters added

**4 July 2023. Version 0.200**
- Combining diacritics and capital sharp s added

**4 July 2023. Version 0.100**
- Bahá'í star added

## License

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at
https://scripts.sil.org/OFL

Note that this project is a derivative of Courier Prime, also released under this same license
but with the reserved name Courier Prime Source. Courier itself is a public domain name and
Badi is a name from Bahá'í history.

## Repository Layout

This font repository structure is inspired by [Unified Font Repository v0.3](https://github.com/unified-font-repository/Unified-Font-Repository), modified for the Google Fonts workflow.
