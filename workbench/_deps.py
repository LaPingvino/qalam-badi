"""Load the hyphen-named pipeline helpers the workbench builds on.

The build scripts under ``scripts/`` have hyphens in their filenames, so they
can't be imported normally. This module loads the few we reuse and re-exports
their useful names, so the rest of the workbench can just ``from ._deps import
PolygonPen, spans_at, base_and_form, ...``.
"""
import os
from importlib.machinery import SourceFileLoader

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_ROOT, "scripts")


def _load(name):
    return SourceFileLoader(name.replace("-", "_"),
                            os.path.join(_SCRIPTS, name + ".py")).load_module()


_joins = _load("joins")
_widths = _load("classify-widths")
_flat = _load("classify-flatness")

spans_at = _joins.spans_at
PolygonPen = _widths.PolygonPen
base_and_form = _flat.base_and_form
YEH_SKELETON = _flat.YEH_SKELETON
SEEN_SKELETON = _flat.SEEN_SKELETON

ROOT = _ROOT
