"""Every earth-model artefact gets a manifest: inputs with SHA-256, parameters, code version, time (PLAN.md section 3)."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

from se.config import PROJECT


def sha256(path: Path, limit: int | None = None) -> str:
    """Hash of a file (whole file, or the first `limit` bytes for very large inputs, said so in the manifest)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        n = 0
        while b := f.read(1 << 22):
            h.update(b); n += len(b)
            if limit and n >= limit:
                break
    return h.hexdigest()


def code_version() -> str:
    try:
        rev = subprocess.run(["git", "-C", str(PROJECT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(PROJECT), "status", "--porcelain", "--", "."], capture_output=True, text=True, timeout=10).stdout.strip()
        return rev + ("+uncommitted" if dirty else "")
    except Exception:
        return "unknown"


def write(out: Path, inputs: list[Path], params: dict, extra: dict | None = None, hash_limit: int = 256 << 20) -> dict:
    """Write `<out>.manifest.json` next to the artefact `out`."""
    ins = []
    for p in inputs:
        p = Path(p)
        big = p.stat().st_size > hash_limit
        ins.append({"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p, hash_limit if big else None), "hashed": "first 256 MB" if big else "whole file"})
    m = {"artefact": Path(out).name, "built": time.strftime("%Y-%m-%d %H:%M:%S"), "code": code_version(), "inputs": ins, "params": params, **(extra or {})}
    Path(str(out) + ".manifest.json").write_text(json.dumps(m, indent=1, default=str))
    return m
