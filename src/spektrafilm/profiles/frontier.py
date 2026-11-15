"""Loading of Fujifilm Frontier scanner templates.

Templates are JSON files in ``spektrafilm/data/scanners``. Each physical
value is stored as ``{"value": ..., "label": ..., "source": ...}`` so that
estimates can be swapped for measured data without code changes.
"""
from __future__ import annotations

import json
from importlib import resources

ALLOWED_LABELS = ("official", "patent", "community", "estimate", "measured")
DEFAULT_TEMPLATE = "frontier_default"


def load_frontier_template(name: str | None = None) -> dict:
    """Return the parsed template ``name`` (default: ``frontier_default``)."""
    name = name or DEFAULT_TEMPLATE
    path = resources.files("spektrafilm.data").joinpath("scanners", f"{name}.json")
    if not path.is_file():
        raise FileNotFoundError(f"Frontier template {name!r} not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_labelled_values(node, prefix=""):
    """Yield ``(dotted_path, entry)`` for every labelled value in a template."""
    if isinstance(node, dict):
        if "value" in node and "label" in node:
            yield prefix, node
            return
        for key, child in node.items():
            yield from iter_labelled_values(child, f"{prefix}.{key}" if prefix else key)
