"""Artefacts are replaced whole or not at all (PLAN P12.4, LOG L078): write to a temporary name in the same folder, then rename over the
old file (os.replace is atomic on one file system), so a reader never sees half a file. A step that writes several files that belong
together (targets: the cell table and one array per target) writes them into a staging folder and swaps the folder in (staged())."""
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
    """Yield a staging folder; on success swap it in place of `final` (the old folder is renamed away, then removed). Files of the old
    folder for which keep(path) is true are copied in first (outputs of later steps that still match)."""
    final = Path(final); stage = final.with_name(final.name + ".staging"); old = final.with_name(final.name + ".old")
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
    os.replace(stage, final); shutil.rmtree(old, ignore_errors=True)
