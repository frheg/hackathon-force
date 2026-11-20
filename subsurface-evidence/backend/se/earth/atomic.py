"""Atomic single-file writes and staging for scratch builds. See snapshot.py for publication."""
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

import numpy as np


def _tmp(path: Path) -> Path:
    path = Path(path); return path.with_name(f".{path.name}.{os.getpid()}.tmp")


def savez(path, **arrays):
    path = Path(path); t = _tmp(path).with_suffix(".npz")  # numpy appends .npz to a name without it
    np.savez_compressed(t, **arrays); os.replace(t, path)


def write_text(path, text: str):
    path = Path(path); t = _tmp(path); t.write_text(text); os.replace(t, path)


def write_json(path, obj, **kw):
    write_text(path, json.dumps(obj, **({"indent": 1} | kw)))


def to_parquet(df, path):
    path = Path(path); t = _tmp(path); df.to_parquet(t); os.replace(t, path)


@contextmanager
def staged(final: Path, keep=lambda p: False):
    """Replace a mutable build folder; not an atomic publication to live readers."""
    final = Path(final); stage = final.with_name(final.name + ".staging"); old = final.with_name(final.name + ".old")
    if not final.exists() and old.exists():  # interrupted after the first rename
        os.replace(old, final)
    shutil.rmtree(stage, ignore_errors=True); stage.mkdir(parents=True)
    try:
        yield stage
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True); raise
    if final.exists():
        for p in final.iterdir():
            if not (stage / p.name).exists() and keep(p):
                shutil.copy2(p, stage / p.name)
        shutil.rmtree(old, ignore_errors=True); os.replace(final, old)
    try:
        os.replace(stage, final)
    except OSError:
        if old.exists():
            os.replace(old, final)
        raise
    shutil.rmtree(old, ignore_errors=True)
