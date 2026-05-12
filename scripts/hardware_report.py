#!/usr/bin/env python3
"""Short report of the current machine — paste into an experiment's *Setup*
section so runs are comparable across Mac / GPU box / cloud.

Run: uv run python scripts/hardware_report.py
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys


def sh(*cmd: str) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
        return out or None
    except Exception:
        return None


def total_memory() -> str:
    try:  # Linux
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return f"{int(line.split()[1]) / 1024**2:.1f} GiB"
    except OSError:
        pass
    mem = sh("sysctl", "-n", "hw.memsize")  # macOS
    return f"{int(mem) / 1024**3:.1f} GiB" if mem and mem.isdigit() else "?"


def main() -> None:
    print("# Hardware report\n")
    print(f"platform:   {platform.platform()}")
    print(f"machine:    {platform.machine()}")
    print(f"processor:  {platform.processor() or sh('sysctl', '-n', 'machdep.cpu.brand_string') or '?'}")
    print(f"python:     {sys.version.split()[0]}  ({sys.executable})")
    print(f"cpu cores:  {os.cpu_count()}")
    print(f"memory:     {total_memory()}")

    if nvidia := shutil.which("nvidia-smi"):
        print(f"nvidia-smi: {sh(nvidia, '--query-gpu=name,memory.total', '--format=csv,noheader') or 'present'}")
    if ollama := shutil.which("ollama"):
        print(f"ollama:     {sh(ollama, '--version') or 'present'}")

    try:
        import torch  # type: ignore
    except ImportError:
        print("torch:      not installed (install per experiment when needed)")
    else:
        cuda = torch.cuda.is_available()
        mps = bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available()
        gpu = f", {torch.cuda.get_device_name(0)}" if cuda else ""
        print(f"torch:      {torch.__version__}  (cuda={cuda}{gpu}, mps={mps})")


if __name__ == "__main__":
    main()
