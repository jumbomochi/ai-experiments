"""Tests for deterministic prompt rendering."""
from __future__ import annotations

import textwrap
from pathlib import Path

from shared.goldsets.render import render_prompt


def test_render_simple_template(tmp_path: Path) -> None:
    tpl_dir = tmp_path / "general"
    tpl_dir.mkdir()
    (tpl_dir / "multi-choice.j2").write_text(textwrap.dedent("""\
        Q: {{ question }}
        A. {{ choices.A }}
        B. {{ choices.B }}
    """))
    out = render_prompt(
        template_root=tmp_path,
        template_path="general/multi-choice.j2",
        inputs={"question": "x?", "choices": {"A": "yes", "B": "no"}},
    )
    assert out == "Q: x?\nA. yes\nB. no\n"


def test_render_is_deterministic(tmp_path: Path) -> None:
    tpl_dir = tmp_path / "general"
    tpl_dir.mkdir()
    (tpl_dir / "t.j2").write_text("{{ a }} | {{ b }}")
    inputs = {"a": "x", "b": "y"}
    assert render_prompt(tmp_path, "general/t.j2", inputs) == \
           render_prompt(tmp_path, "general/t.j2", inputs)
