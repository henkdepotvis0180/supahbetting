"""Dependency-free, conservative hardware detection for local model training."""
from __future__ import annotations
import argparse
import json
import os
import platform
import subprocess
from pathlib import Path


def _windows_details():
    if os.name != "nt":
        return {}
    try:
        command = [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "$ErrorActionPreference='Stop'; "
            "$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors; "
            "$mem=Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory; "
            "$gpu=@(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name); "
            "@{cpu=$cpu;mem=$mem;gpu=$gpu} | ConvertTo-Json -Compress -Depth 4"
        ]
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=12, check=True)
        return json.loads(completed.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def select_workers(logical_cpus, memory_gb=None, cap=16):
    """Leave headroom for Windows and avoid overcommitting small-memory PCs."""
    logical_cpus = max(1, int(logical_cpus or 1))
    cap = max(1, int(cap))
    workers = max(1, logical_cpus - 2)
    if memory_gb is not None and memory_gb > 0:
        # Each Python process gets its own copy of historical match data.
        workers = min(workers, max(1, int(memory_gb // 1.5)))
    return min(cap, workers)


def detect(cap=16):
    details = _windows_details()
    cpu = details.get("cpu") or {}
    mem = details.get("mem") or {}
    logical = int(cpu.get("NumberOfLogicalProcessors") or os.cpu_count() or 1)
    physical = cpu.get("NumberOfCores")
    try:
        memory_gb = round(int(mem.get("TotalPhysicalMemory")) / (1024 ** 3), 2)
    except (ValueError, TypeError):
        memory_gb = None
    gpu = details.get("gpu") or []
    if isinstance(gpu, str):
        gpu = [gpu]
    return {
        "os": platform.platform(),
        "cpu_name": cpu.get("Name") or platform.processor() or "Onbekend",
        "physical_cores": physical,
        "logical_processors": logical,
        "ram_gb": memory_gb,
        "gpu_names": gpu,
        "gpu_acceleration_enabled": False,
        "worker_cap": cap,
        "recommended_workers": select_workers(logical, memory_gb, cap),
        "note": "CPU-only; GPU wordt gedetecteerd maar niet gebruikt.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", type=int, default=16)
    parser.add_argument("--output", default="training_reports/hardware_profile.json")
    parser.add_argument("--workers-only", action="store_true")
    args = parser.parse_args()
    profile = detect(args.cap)
    if args.workers_only:
        print(profile["recommended_workers"])
        return
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    print("Hardwareprofiel:", path)


if __name__ == "__main__":
    main()
