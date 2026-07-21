#!/usr/bin/env python3
"""Build a self-contained specimen page with the webfonts inlined.

The specimen has to be one file with no external requests — it gets published
and viewed away from the repo — so the woff2 files are embedded as data URIs
rather than linked. It also embeds the monospace seed alongside the proportional
result, because the only honest way to show what this project does is to set the
same line in both and let the reader compare.

Usage:
    python3 scripts/make-specimen.py --out documentation/specimen.html
"""

import argparse
import base64
import os
import sys

FONTS = {
    "REGULAR": "fonts/webfonts/QalamBadi-Regular.woff2",
    "ITALIC": "fonts/webfonts/QalamBadi-Italic.woff2",
    "BOLD": "fonts/webfonts/QalamBadi-Bold.woff2",
}


def data_uri(path):
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:font/woff2;base64,{encoded}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default="documentation/specimen-template.html")
    parser.add_argument("--out", default="documentation/specimen.html")
    parser.add_argument("--mono", help="path to a built webfont of the monospace seed, for the comparison")
    args = parser.parse_args()

    with open(args.template) as handle:
        html = handle.read()

    fonts = dict(FONTS)
    if args.mono:
        fonts["MONO"] = args.mono

    for key, path in fonts.items():
        placeholder = f"@@{key}@@"
        if placeholder not in html:
            continue
        if not os.path.exists(path):
            print(f"missing {path}; run `make build` first", file=sys.stderr)
            return 1
        html = html.replace(placeholder, data_uri(path))

    with open(args.out, "w") as handle:
        handle.write(html)

    size = os.path.getsize(args.out)
    print(f"wrote {args.out} ({size / 1024:.0f} KB, fonts inlined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
