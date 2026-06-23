"""Typed `ModelManifest` plus YAML loader.

The manifest is the descriptor that makes a run replayable. It captures
just enough to reproduce a run in practice: model id + revision/quant +
runtime + version + sampling + target host. Per spec §1 ("pragmatic" rigor).
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

ALLOWED_RUNTIMES = {"ollama", "vllm", "vllm_metal", "nim", "trt_llm", "mlx", "sglang"}
ALLOWED_CAPABILITIES = {"chat", "embeddings", "seed", "logprobs"}


class Sampling(BaseModel):
    temperature: float
    top_p: float
    max_tokens: int


class ModelManifest(BaseModel):
    id: str
    family: str
    size: str
    revision: str
    quantization: str | None = None
    runtime: str
    runtime_version: str
    target_host: Literal["mac", "spark", "cloud-burst-l4", "cloud-burst-a2", "cloud-burst-a3", "cloud-burst-p5"]
    endpoint: str
    capabilities: list[str] = Field(default_factory=list)
    context_window: int
    default_sampling: Sampling

    @field_validator("runtime")
    @classmethod
    def _runtime_known(cls, v: str) -> str:
        if v not in ALLOWED_RUNTIMES:
            raise ValueError(
                f"runtime {v!r} not in {sorted(ALLOWED_RUNTIMES)}"
            )
        return v

    @field_validator("capabilities")
    @classmethod
    def _capabilities_known(cls, v: list[str]) -> list[str]:
        unknown = set(v) - ALLOWED_CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capabilities: {sorted(unknown)}")
        return v


def load_manifest_yaml(path: Path) -> ModelManifest:
    raw = yaml.safe_load(path.read_text())
    return ModelManifest.model_validate(raw)
