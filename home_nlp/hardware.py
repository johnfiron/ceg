#!/usr/bin/env python3
"""Emit a portable capability profile for home NLP sizing."""
import json
import os
import platform
import shutil
import subprocess


def _memory_bytes():
    try:
        values = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0]) * 1024
        return values.get("MemTotal"), values.get("MemAvailable")
    except (OSError, ValueError):
        return None, None


def _nvidia():
    if not shutil.which("nvidia-smi"):
        return None
    try:
        output = subprocess.check_output([
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ], text=True, timeout=5).strip()
        if not output:
            return None
        name, memory_mb, driver = [part.strip() for part in output.splitlines()[0].split(",")]
        return {"name": name, "memory_mb": int(memory_mb), "driver": driver}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def capability_profile():
    total, available = _memory_bytes()
    gpu = _nvidia()
    profile = "cuda" if gpu else "cpu_balanced" if (total or 0) >= 16 * 1024**3 else "cpu_small"
    return {
        "schema": "ash-home-capability/v1",
        "profile": profile,
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "memory_total_bytes": total,
        "memory_available_bytes": available,
        "nvidia": gpu,
    }


if __name__ == "__main__":
    print(json.dumps(capability_profile(), indent=2, sort_keys=True))
