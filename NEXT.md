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

Steps 1–3 are **done**; extension runs on the same machinery as removal, which
is what keeps it out of the fat-seen failure mode.

**1. ✓ Classify, don't guess.** `classify-flatness.py --sides` is the
two-sided report: left approach | body | right approach per joining glyph, in
nuqta, flagged TIGHT / OK / LOOSE against the classical figures (tooth ≈1 dot
as body width; dāl 2, beh short form 4–5, seen kashida 7–11 as whole-letter
ink). Answer to the connector-or-body question: the tightness was in the
finals, and it was the transform itself doing it — see step 2. Toothed
init/medi forms were already about right. Caveat: a dotted variant's body
reads wider than its skeleton's because a dot is an island too.

**2. ✓ The transform is symmetric.** `fit-connectors.py` replaced
shorten-connectors, and the rewrite fixed a shipped breakage the report
surfaced: the old code held only the longest body island rigid and scaled
everything else, which crushed seen finals' teeth from ~290 units to 24. Now
every island (tooth, bowl, hook, dot) translates rigidly; only bare
join-height runs change length; target deltas go into one elongation run
beside the largest island, never the teeth gaps. Islands under 100 units are
dropped as fillet phantoms (nothing real is narrower than most of a pen).

**3. ✓ Per-letter targets in `spacing.yaml`** (`connectors.widths`): beh
finals/isolated 4.5 nuqta, seen family 7.5. Verified on the rebuilt Regular:
both land exactly, report went 39 TIGHT / 21 OK → 2 TIGHT / 54 OK. The two
remaining TIGHT are noon ghunna inits whose tooth is *drawn* narrow — body
work. Seen init/medi have no classical figure recorded yet and now keep their
teeth gaps as drawn (~0.45 nuqta each); add `seen.init`/`seen.medi` targets if
they read airy in the specimen.

**4. The undertail — hook to curve.** Same principle: stretch x only across the
tail's horizontal run, rigidly translate the hook beyond it. Targets from his
Greatest Name: finals ~1.5–1.7 alef heights wide against ~0.9 deep, tail
returning rightward *under* the preceding letters.
`scripts/reshape-tails.py` holds the targets but is **disabled** — its
mechanism was the anisotropic scale above. Keep the numbers, replace the method.
This is also what should cure the yá cut-off below.

Still to check: how extension interacts with the lám shadda/harakat stacking
below, and a human look at the new specimen — beh/seen finals and isolated
forms changed width noticeably (beh isol 1228→1318, seen isol adv 2130).

---

## Known open issues

- **Lám with doubled harakat** stacks wrongly. May or may not be related to
  connector length.
- **`bá` has a sharp corner** where it wants a curve.
- **Yá cut-off: FIXED, and the diagnosis moved twice.** First blamed on bá,
  then on yeh's tail — measurement showed the body only reaches −481; it was
  the two DOTS below, parked at −1024 by the cell (placed to clear the
  deepest possible tail anywhere in the box) against a −838 descender.
  `scripts/tuck-dots.py` now raises every below-dot group, as a rigid shape,
  to clear the descender while stopping short of the ink above. Eight rare
  glyphs remain below the line (uni06D1/0777/076F/06BC finals, uniFBE5, two
  component sources): their tails sweep directly over the dots, leaving less
  vertical room than a dot is tall, so translation alone cannot save them —
  they need the step-4 tail reshape or a dot rearrangement.
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
