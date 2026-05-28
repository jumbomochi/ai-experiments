"""Deterministic Jinja2 prompt rendering.

The renderer is stateless and pure: same template + same inputs → same output.
StrictUndefined ensures missing fields raise rather than silently empty.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def render_prompt(
    template_root: Path,
    template_path: str,
    inputs: dict[str, Any],
) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_root)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    tpl = env.get_template(template_path)
    return tpl.render(**inputs)
