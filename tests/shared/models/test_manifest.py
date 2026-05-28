"""Tests for the ModelManifest pydantic model + YAML loading."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from shared.models.manifest import load_manifest_yaml


def test_load_minimal_manifest(tmp_path: Path) -> None:
    yaml_path = tmp_path / "m.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        id: qwen2.5-0.5b-instruct-ollama
        family: qwen2.5
        size: 0.5b
        revision: "2024-09-19"
        quantization: null
        runtime: ollama
        runtime_version: "0.3.12"
        target_host: mac
        endpoint: "http://localhost:11434/v1"
        capabilities: [chat, embeddings]
        context_window: 32768
        default_sampling:
            temperature: 0.0
            top_p: 1.0
            max_tokens: 256
    """))
    m = load_manifest_yaml(yaml_path)
    assert m.id == "qwen2.5-0.5b-instruct-ollama"
    assert m.runtime == "ollama"
    assert m.context_window == 32768
    assert m.default_sampling.max_tokens == 256
    assert "chat" in m.capabilities


def test_unknown_runtime_rejected(tmp_path: Path) -> None:
    yaml_path = tmp_path / "m.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        id: x
        family: x
        size: x
        revision: "x"
        runtime: faketime
        runtime_version: x
        target_host: mac
        endpoint: x
        capabilities: []
        context_window: 1
        default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 1}
    """))
    with pytest.raises(ValueError, match="runtime"):
        load_manifest_yaml(yaml_path)


def test_unknown_capability_rejected(tmp_path: Path) -> None:
    yaml_path = tmp_path / "m.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        id: x
        family: x
        size: x
        revision: "x"
        runtime: ollama
        runtime_version: x
        target_host: mac
        endpoint: x
        capabilities: [chat, telepathy]
        context_window: 1
        default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 1}
    """))
    with pytest.raises(ValueError, match="capabilities"):
        load_manifest_yaml(yaml_path)
