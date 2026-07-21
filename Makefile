SOURCES=$(shell python3 scripts/read-config.py --sources )
FAMILY=$(shell python3 scripts/read-config.py --family )
DRAWBOT_SCRIPTS=$(shell ls documentation/*.py)
DRAWBOT_OUTPUT=$(shell ls documentation/*.py | sed 's/\.py/.png/g')
MONO_SOURCES=$(shell find sources/QalamBadi-Mono.ufo -type f 2>/dev/null)

help:
	@echo "###"
	@echo "# Build targets for $(FAMILY)"
	@echo "###"
	@echo
	@echo "  make build:  Builds the fonts and places them in the fonts/ directory"
	@echo "  make test:   Tests the fonts with fontbakery"
	@echo "  make proof:  Creates HTML proof documents in the proof/ directory"
	@echo "  make images: Creates PNG specimen images in the documentation/ directory"
	@echo

build: build.stamp

venv: venv/touchfile

venv-test: venv-test/touchfile

# Assert the design invariants (module, master interpolation, descender
# clearance, join height, monolinearity) over the source masters in ~1s.
# Gates `make build`; run it standalone before committing.
check: venv
	. venv/bin/activate; python3 scripts/check-invariants.py

customize: venv
	. venv/bin/activate; python3 scripts/customize.py

# Regenerate the managed Arabic OpenType features (init/medi/fina, lam-alef
# ligatures, GDEF marks) directly from the UFO glyph set. Requires Go. The
# generated block is written between markers in features.fea; hand-written
# features outside the markers are preserved. Run this after adding or removing
# Arabic glyphs. Use `arabic-features-check` in CI to verify it is up to date.
arabic-features:
	cd scripts/arabic-features && go run . --ufo ../../sources/QalamBadi-Regular.ufo

arabic-features-check:
	cd scripts/arabic-features && go run . --ufo ../../sources/QalamBadi-Regular.ufo --check

build.stamp: venv sources/config.yaml $(SOURCES)
	# Gate the build on the design invariants. This is a one-second check that
	# fails fast with a readable message where fontmake would fail three
	# minutes in with a cryptic one — the desynced-Bold interpolation break is
	# exactly what it catches. See scripts/check-invariants.py.
	. venv/bin/activate; python3 scripts/check-invariants.py
	rm -rf fonts
	(for config in sources/config*.yaml; do . venv/bin/activate; gftools builder $$config; done)
	# Post-build: add a 'meta' table (dlng/slng ScriptLangTags) and a STAT table
	# (italic axis for the Regular+Italic family), then refresh the webfonts.
	. venv/bin/activate; python3 scripts/add-meta-table.py $$(find fonts -name '*.ttf' -o -name '*.otf' 2>/dev/null)
	. venv/bin/activate; python3 scripts/add-stat.py $$(find fonts -name '*.ttf' -o -name '*.otf' 2>/dev/null)
	. venv/bin/activate; for ttf in fonts/ttf/*.ttf; do [ -f "$$ttf" ] && rm -f fonts/webfonts/$$(basename $${ttf%.ttf}).woff2 && fonttools ttLib.woff2 compress -o fonts/webfonts/$$(basename $${ttf%.ttf}).woff2 $$ttf; done
	touch build.stamp

# Regenerate the Italic UFO as a sheared oblique of the Regular, with the
# cursive overrides from sources/italic-overrides grafted on. Run after changing
# the Regular so the Italic inherits all corrections.
italic:
	. venv/bin/activate; python3 scripts/make-italic.py

# Regenerate the proportional Regular from the inherited monospace seed.
#
# This is the step that makes Qalam Badi a different typeface from Courier Badi,
# and it is deliberately a script rather than a hand-edited master: the seed
# stays mergeable with upstream, so Courier Badi's Arabic and Fontbakery fixes
# keep flowing in, and every spacing decision stays legible in one reviewable
# file (sources/spacing.yaml) instead of being buried in 2318 .glif files.
#
#   1. narrow-serifs      pulls in serifs that were stretched to fill the cell
#   2. soften-corners     rounds the corners so strokes read as a pen, not a machine
#   3. make-proportional  fits advances to ink, in nuqta, pinning Arabic joins
#
# Softening runs before fitting so advances are measured against the final
# outlines. It changes no stroke width and no bounding box — a fillet is tangent
# to the corner it replaces — so the two steps are independent in practice.
#
# Run `make widths` for the classification the targets in spacing.yaml are
# derived from.
proportional:
	. venv/bin/activate; python3 scripts/narrow-serifs.py --src sources/QalamBadi-Mono.ufo --out sources/QalamBadi-Narrowed.ufo
	# NO seen/sheen/sad widening here. The seed ALREADY HAS IT.
	#
	# Courier Badi widened these teeth 1.5x in its v0.750 and committed the
	# widened outlines to the master, so running scripts/widen-seen-family.py
	# again double-applies it: 1.5 x 1.5 = 2.25x, and briefly 1.5 x 2.0 = 3x.
	# Measured on seen.medi at y=550 that took the ink from 173 units to 609.
	# That was the "way too fat" seen/sheen/sad, and it is also why Allah still
	# came out too wide after the tail transform was reverted — the fatness was
	# never the tails.
	#
	# If the teeth should be wider than the seed draws them, the scale to change
	# is the one in the SEED's own history, not a second pass here.
	. venv/bin/activate; python3 scripts/soften-corners.py --src sources/QalamBadi-Narrowed.ufo --out sources/QalamBadi-Softened.ufo
	# Tuck below-base dots inside the descender. The seed parks them low
	# enough to clear the deepest tail the CELL could hold — final yeh's dots
	# at y=-1024 against a -838 descender — so line-metric renderers clip
	# them. That was the "ya gets cut off" report.
	. venv/bin/activate; python3 scripts/tuck-dots.py --src sources/QalamBadi-Softened.ufo --out sources/QalamBadi-Tucked.ufo
	# The madda kept its cell width while the alef under it shrank; narrow it
	# to the proportion recorded in spacing.yaml (marks.madda).
	. venv/bin/activate; python3 scripts/narrow-madda.py --src sources/QalamBadi-Tucked.ufo --out sources/QalamBadi-Madda.ufo
	# Fit the connector runs: compress the cell's stretched approaches so a
	# joined letter's advance follows its actual body, and extend the letters
	# whose flat run is part of the written form (beh finals, seen kashidas)
	# to the classical widths recorded in spacing.yaml (connectors.widths).
	. venv/bin/activate; python3 scripts/fit-connectors.py --src sources/QalamBadi-Madda.ufo --out sources/QalamBadi-Connected.ufo
	# Bend the flat bowls and shallow tails: round with a slight dip, per
	# spacing.yaml (bends:). This is the safe successor to reshape-tails,
	# which is still DISABLED — that one scaled anisotropically and fattened
	# strokes; this one only translates vertically, so it cannot.
	. venv/bin/activate; python3 scripts/bend-strokes.py --src sources/QalamBadi-Connected.ufo --out sources/QalamBadi-Bent.ufo
	. venv/bin/activate; python3 scripts/shorten-ascenders.py --src sources/QalamBadi-Bent.ufo --out sources/QalamBadi-Short.ufo
	# Round the initial forms' hard L-elbow into a curve: initial ba, ya and
	# kin sweep the stem into the connector instead of turning a right angle.
	. venv/bin/activate; python3 scripts/curve-initials.py --src sources/QalamBadi-Short.ufo --out sources/QalamBadi-Curved.ufo
	# ayn and hamza sat 257 units below the apostrophe they stand beside in
	# 'Abdu'l-Baha and nastaliq. Position only — see the script for why not size.
	. venv/bin/activate; python3 scripts/normalize-modifiers.py --src sources/QalamBadi-Curved.ufo --out sources/QalamBadi-Mods.ufo
	. venv/bin/activate; python3 scripts/make-proportional.py --src sources/QalamBadi-Mods.ufo --out sources/QalamBadi-Regular.ufo

# Build the specimen: a single self-contained page with the webfonts inlined
# and the monospace seed alongside for comparison. Published with the proofs so
# there is always a current, readable sample next to the machine reports —
# diffenator2 tells you what changed, this tells you whether it looks right.
#
# Add further sample or test pages to documentation/ and list them in
# scripts/index.html so they show up on the site too.
# The monospace seed, compiled once and cached. It only changes when upstream
# Courier Badi is merged, so rebuilding it on every specimen run cost more time
# than the entire proportional transform chain (19s) for no benefit whatever.
.mono-seed.woff2: $(MONO_SOURCES)
	. venv/bin/activate; fontmake -u sources/QalamBadi-Mono.ufo -o ttf --output-path .mono-seed.ttf
	. venv/bin/activate; fonttools ttLib.woff2 compress -o $@ .mono-seed.ttf
	rm -f .mono-seed.ttf

specimen: venv build.stamp .mono-seed.woff2
	mkdir -p out
	. venv/bin/activate; python3 scripts/make-specimen.py --mono .mono-seed.woff2 --out out/specimen.html
	# The pitfalls proof rides along: the generic proof sheets exercise Latin
	# well and everything else thinly, so this page carries one test per known
	# failure mode of the Arabic, Cyrillic and Greek — including a regression
	# test line for every visual bug this project has actually shipped.
	. venv/bin/activate; python3 scripts/make-specimen.py --template documentation/pitfalls-template.html --out out/pitfalls.html

# Fast visual loop: regenerate the masters, compile ONLY the Regular, and
# rebuild the specimen. Skips the OTF, the variable fonts, the other three
# styles, the webfont set, fontbakery and diffenator2 — none of which you need
# in order to look at the thing.
#
# This exists because the only check that catches a visual regression is a human
# looking at the result, so the round trip from a changed number to a rendered
# page is the real bottleneck in this project, not the release build.
#
#   make preview   ~20s     enough to see whether a change worked
#   make build     ~2m40s   what CI ships
preview: venv proportional
	. venv/bin/activate; python3 scripts/make-italic.py
	mkdir -p fonts/webfonts out
	. venv/bin/activate; fontmake -u sources/QalamBadi-Regular.ufo -o ttf --output-path fonts/ttf/QalamBadi-Regular.ttf
	. venv/bin/activate; fonttools ttLib.woff2 compress -o fonts/webfonts/QalamBadi-Regular.woff2 fonts/ttf/QalamBadi-Regular.ttf
	. venv/bin/activate; fontmake -u sources/QalamBadi-Italic.ufo -o ttf --output-path fonts/ttf/QalamBadi-Italic.ttf
	. venv/bin/activate; fonttools ttLib.woff2 compress -o fonts/webfonts/QalamBadi-Italic.woff2 fonts/ttf/QalamBadi-Italic.ttf
	# Bold is NOT rebuilt here — that is the point of the target. If a stale one
	# is lying around from an earlier full build the specimen will show it, so
	# judge weight from `make build`, never from a preview.
	. venv/bin/activate; test -f fonts/webfonts/QalamBadi-Bold.woff2 || cp fonts/webfonts/QalamBadi-Regular.woff2 fonts/webfonts/QalamBadi-Bold.woff2
	$(MAKE) --no-print-directory specimen-only
	@echo ""
	@echo "  -> out/specimen.html   (Regular + Italic are fresh; BOLD IS NOT — use 'make build' to judge weight)"

# The specimen without the build.stamp dependency, for the fast loop.
specimen-only: .mono-seed.woff2
	mkdir -p out
	. venv/bin/activate; python3 scripts/make-specimen.py --mono .mono-seed.woff2 --out out/specimen.html
	. venv/bin/activate; python3 scripts/make-specimen.py --template documentation/pitfalls-template.html --out out/pitfalls.html

# Report which glyphs the monospace cell distorted, and how.
widths:
	. venv/bin/activate; python3 scripts/classify-widths.py --src sources/QalamBadi-Mono.ufo

# Regenerate all derived masters (Italic, Bold, Bold Italic) from the Regular.
# The Bold is an outward outline dilation (emboldening); Bold Italic is the
# emboldened Italic. Run after changing the Regular.
masters: proportional
	. venv/bin/activate; python3 scripts/make-italic.py
	. venv/bin/activate; python3 scripts/make-bold.py --src sources/QalamBadi-Regular.ufo --out sources/QalamBadi-Bold.ufo
	. venv/bin/activate; python3 scripts/make-bold.py --src sources/QalamBadi-Italic.ufo --out sources/QalamBadi-BoldItalic.ufo
	# Contrast siblings for the XOPQ axis: a weight-neutral modulation (thick
	# verticals, thin horizontals) of EACH weight, so XOPQ reads at every weight,
	# not just Bold. Same point structure -> interpolates with its base master.
	. venv/bin/activate; python3 scripts/make-contrast-master.py --src sources/QalamBadi-Regular.ufo    --out sources/QalamBadi-RegularContrast.ufo
	. venv/bin/activate; python3 scripts/make-contrast-master.py --src sources/QalamBadi-Italic.ufo     --out sources/QalamBadi-ItalicContrast.ufo
	. venv/bin/activate; python3 scripts/make-contrast-master.py --src sources/QalamBadi-Bold.ufo       --out sources/QalamBadi-BoldContrast.ufo
	. venv/bin/activate; python3 scripts/make-contrast-master.py --src sources/QalamBadi-BoldItalic.ufo --out sources/QalamBadi-BoldItalicContrast.ufo

# Bonus/experimental variable font: the contrast (XOPQ) axis, shipped as a
# release-only extra separate from the GF-clean submission. Outputs to
# fonts-contrast/ so it never mixes with the main fonts/ that CI tests.
contrast-vf: venv masters
	rm -rf fonts-contrast
	. venv/bin/activate; gftools builder sources/contrast.yaml
	. venv/bin/activate; python3 scripts/add-meta-table.py $$(find fonts-contrast -name '*.ttf' -o -name '*.otf' 2>/dev/null)
	. venv/bin/activate; python3 scripts/add-stat.py $$(find fonts-contrast -name '*.ttf' -o -name '*.otf' 2>/dev/null)

# Standalone "Contrast" sample preview (its own family name).
contrast:
	. venv/bin/activate; python3 scripts/make-bold.py --src sources/QalamBadi-Regular.ufo --out /tmp/QalamBadiContrast-Regular.ufo --weight 40 --contrast 4

venv/touchfile: requirements.txt
	test -d venv || python3 -m venv venv
	. venv/bin/activate; pip install -Ur requirements.txt
	touch venv/touchfile

venv-test/touchfile: requirements-test.txt
	test -d venv-test || python3 -m venv venv-test
	. venv-test/bin/activate; pip install -Ur requirements-test.txt
	touch venv-test/touchfile

test: venv-test build.stamp
	TOCHECK=$$(find fonts/variable -type f 2>/dev/null); if [ -z "$$TOCHECK" ]; then TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); fi ; . venv-test/bin/activate; mkdir -p out/ out/fontbakery; fontbakery check-googlefonts -j -l WARN --full-lists --succinct --badges out/badges --html out/fontbakery/fontbakery-report.html --ghmarkdown out/fontbakery/fontbakery-report.md $$TOCHECK  || echo '::warning file=sources/config.yaml,title=Fontbakery failures::The fontbakery QA check reported errors in your font. Please check the generated report.'

# --user-wordlist feeds the script-pitfall words (dot minimal pairs, harakat
# stacks, deep tails, confusables) into the machine proofs, so the generic
# sheets exercise the same failure modes the pitfalls page documents.
proof: venv build.stamp
	TOCHECK=$$(find fonts/variable -type f 2>/dev/null); if [ -z "$$TOCHECK" ]; then TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); fi ; . venv/bin/activate; mkdir -p out/ out/proof; diffenator2 proof $$TOCHECK -o out/proof --user-wordlist documentation/pitfall-words.txt

images: venv $(DRAWBOT_OUTPUT)

%.png: %.py build.stamp
	. venv/bin/activate; python3 $< --output $@

clean:
	rm -rf venv
	find . -name "*.pyc" -delete

update-project-template:
	npx update-template https://github.com/googlefonts/googlefonts-project-template/

update: venv venv-test
	venv/bin/pip install --upgrade pip-tools
	# See https://pip-tools.readthedocs.io/en/latest/#a-note-on-resolvers for
	# the `--resolver` flag below.
	venv/bin/pip-compile --upgrade --verbose --resolver=backtracking requirements.in
	venv/bin/pip-sync requirements.txt

	venv-test/bin/pip install --upgrade pip-tools
	venv-test/bin/pip-compile --upgrade --verbose --resolver=backtracking requirements-test.in
	venv-test/bin/pip-sync requirements-test.txt

	git commit -m "Update requirements" requirements.txt requirements-test.txt
	git push
