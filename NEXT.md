# Qalam Badi — state of play, and what's next

Working notes for picking the project back up. Design rationale lives in
[`documentation/design-notes.md`](documentation/design-notes.md); every spacing
decision lives in [`sources/spacing.yaml`](sources/spacing.yaml), which is meant
to be read as the design record.

---

## Getting running on a fresh machine

```sh
git clone https://github.com/LaPingvino/qalam-badi.git
cd qalam-badi
git remote add upstream https://github.com/LaPingvino/courier-badi.git

python3 -m venv venv && . venv/bin/activate && pip install -Ur requirements.txt
# Go is needed only for `make arabic-features`.

make preview     # ~60s  -> out/specimen.html, enough to see whether it worked
make build       # ~3m   what CI ships
make widths      # the glyph classification the spacing targets come from
```

`make preview` deliberately does **not** rebuild Bold, and says so on every run.
Judge weight from `make build`.

Live: <https://LaPingvino.github.io/qalam-badi/> — specimen, proof sheets and
Fontbakery, rebuilt on every push. The specimen footer carries the **commit it
was built from**, so a stale page is obvious on sight; gh-pages caches for ten
minutes and that has already cost two rounds of debugging a fix that was in fact
deployed.

---

## The one rule

Learned four times the hard way, each time by shipping a visible regression:

> **Anything that is a *shape* must be translated. Only *strokes* may be remapped.**

The transforms move stroke endpoints around. Every time one has been allowed to
touch a shape, the shape came out wrong:

| what happened | symptom |
|---|---|
| tail region scaled anisotropically (y×0.85, x×2.6) | seen/sheen/sad **fat** — any non-horizontal stroke thickened up to 2.6× |
| composites let their components move independently | **accents detached** from á, í, ú |
| nuqta remapped point-by-point through the compression | **dot vanished** from bá — squashed to an ellipse, then lost to overlap removal |
| zero-width marks skipped before component compensation | **U+0300 rendered beside** its base instead of over it |

The corollary that makes the Arabic work safe: **a connector is a horizontal
stroke at the join height, so its thickness is a vertical measurement, and
stretching or compressing it in x costs nothing.** That is why shortening
connectors worked cleanly, and why extending them will too.

---

## Measured facts the design rests on

Read from the font at build time, never hardcoded, so an upstream merge cannot
silently invalidate them.

| | |
|---|---|
| **nuqta** | 271×289 (Arabic dot) — and the Latin period is 270×310. One shared module across scripts. |
| **pen** | 141 units. Invariant. If this changes, something is broken. |
| **join height** | y=225..369, 144 thick. Of ~800 ink spans at advance edges across 604 joining glyphs, 750 bottom at exactly 225 and 728 top at exactly 369. |
| **writing line** | y=225, not y=0. The alef's foot and every connector bottom sit there. |
| **alef** | 3.6 nuqta (was 5.45). Nastaʿlīq is 3, naskh 5–6, Mishkín-Qalam's own Greatest Name measures 3.5. |

Arabic advances now run **307–1228, stdev 228**. They were flat 1228.

---

## Next: free up the squished Arabic letters

The plan, in order. Extension is the **inverse of the removal already built**,
and runs on the same machinery — that is what keeps it out of the fat-seen
failure mode.

**1. Classify, don't guess.** Extend `scripts/classify-flatness.py` into a
two-sided report over every joining glyph: body width, left approach, right
approach, in nuqta, flagged TIGHT / OK / LOOSE against the classical figures
(tooth ≈1 dot, dāl 2, beh short form 4–5, seen kashida 7–11). This produces the
list of letters needing extension, and tells us whether "squished" is one
problem or several. Measure-first is what made the width and join-height work
land; every time it was skipped, something shipped broken.

**2. Make the transform symmetric.** `shorten-connectors.py` becomes
`fit-connectors.py`: same body detector, same join-height whitespace test, same
rigid-dot handling, but the target approach may be **larger** than current, not
only smaller. Extension inserts x into the horizontal run at the join height;
the overlap and the endpoint on the advance edge move rigidly. One code path,
both directions, one set of guards.

**3. Per-letter targets in `spacing.yaml`**, in nuqta, from the classical
figures already recorded there.

**4. The undertail — hook to curve.** Same principle: stretch x only across the
tail's horizontal run, rigidly translate the hook beyond it. Targets from his
Greatest Name: finals ~1.5–1.7 alef heights wide against ~0.9 deep, tail
returning rightward *under* the preceding letters.
`scripts/reshape-tails.py` holds the targets but is **disabled** — its
mechanism was the anisotropic scale above. Keep the numbers, replace the method.

Two things to check before committing to it: whether tight-looking letters are
tight in the *connector* or in the *body* (different fixes), and whether
extension interacts with the lám shadda/harakat stacking below.

---

## Known open issues

- **Lám with doubled harakat** stacks wrongly. May or may not be related to
  connector length.
- **`bá` has a sharp corner** where it wants a curve.
- **Yá gets cut off** (it is yá, not bá, that clips). Final yeh `uniFEF2`
  descends to y=−1024 while the hhea/typo descender is −838, so any renderer
  that clips to line metrics cuts the bottom of the tail. Bá bottoms at −289,
  well inside — the misattribution came from there. The tail is a deep narrow
  naskh hook, the same disease as the seen tail; the step-4 undertail reshape
  (wide and shallow, ~0.9 alef deep ≈ −650 from the writing line) should bring
  it back inside the descender on its own. If not, raise the metric, don't
  clip the letter.
- **ghain** still reads as double-joined, so it does not sweep.
- **`ʿ` U+02BF is oversized** next to the apostrophe (604×680 vs 366×555). Its
  position is fixed; the size is not. It is *not* thin — its stroke measures 140
  against the 141 pen; it is a long open arc that reads light. Scaling it drops
  the stroke to 115, so it needs a redraw or a real offset-curve dilation, not a
  scale. Radial dilation from the centroid does **not** work on a crescent.
- **Seen tail is ~2.6 alef heights wide × 0.48 deep**, against a target of
  1.5–1.7 × 0.9 — too shallow and too long, because the whole tail transform was
  reverted rather than just its mechanism.
- **Bold is a dilation of Regular**, so Arabic corrections propagate, but Bold
  has had far less visual checking than Regular.

## Speed work still on the table

- **Quadratic fillets.** Corner softening added 27,969 points (+20%, 18,646 of
  them off-curve). Pathops overlap removal scales superlinearly, so this cuts
  into the ~3min build. Note the corner *radius* itself is not worth tuning for
  size: 26 vs 48 measures identically, because the fillet is clamped to a
  fraction of the adjacent segment.
- **Concurrent CI jobs** for Fontbakery and diffenator2 — they are independent
  and currently sequential.
- **Incremental make** for the transform chain, so editing one number in
  `spacing.yaml` does not re-run all six passes (~20s total, so low priority).

---

## Merging upstream Courier Badi

The monospace master is kept as the seed and the whole family is generated from
it, so upstream fixes flow through:

```sh
git fetch upstream
git merge upstream/main      # lands in sources/QalamBadi-Mono.ufo
make masters                 # propagates through the family
```

**Do not re-run `widen-seen-family.py`.** Courier Badi widened the seen/sheen/sad
teeth 1.5× in its v0.750 and committed the widened *outlines*. Running it again
double-applies: 1.5 × 1.5 = 2.25×, and at scale 2.0 it was 3×. That was the fat
seen, and it survived two wrong diagnoses before being found.
