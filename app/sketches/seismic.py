"""Seismic Lookalike: click a feature on a seismic section, find the patches that look like it, and explain them.

Every 32 x 32 patch (traces x samples, stride 16) of a set of sections gets a texture signature: amplitude statistics,
structure-tensor orientation and coherence (how layered, how steep), vertical frequency bands and lateral continuity.
No depth and no labels go into the signature, so a match means 'looks like', not 'is at the same depth'. Signatures are
reduced with PCA and compared by cosine similarity.

Scored honestly: the index is built from the training block of the F3 Netherlands benchmark, queries come from the
separate test block, and a hit counts when the match has the same facies label as the query (precision at 10, against
the chance level). Stand-in for the event's seismic: write the cube as a numpy array of shape (inline, trace, sample),
point CUBE at it and rebuild the index. The language model never sees an image; it explains the matches from their
numbers and labels, which is where its weakness at geological images does not matter.

    uv run python -m sketches.seismic        builds data/seismic/f3/index.npz and scores it
"""

import base64
import json

import joblib
from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from numpy.lib.stride_tricks import sliding_window_view
from scipy.linalg import eigh
from scipy.ndimage import uniform_filter
from sklearn.ensemble import HistGradientBoostingClassifier
from pydantic import BaseModel, Field

from common import DATA_DIR, ModelBusy, chat, page

router = APIRouter(prefix="/seismic")
D = DATA_DIR / "seismic" / "f3" / "data"
INDEX = DATA_DIR / "seismic" / "f3" / "index.npz"
META = DATA_DIR / "seismic" / "f3" / "index.json"
CLF = DATA_DIR / "seismic" / "f3" / "facies_clf.joblib"
P, STRIDE = 32, 16
SECTION_STEP = 8  # every 8th section of the training block goes in the index
PCA_DIMS = 12
LDA_DIMS = 5  # at most classes - 1
FACIES = ["Unlabelled", "Upper North Sea (N3)", "Middle North Sea (N3)", "Lower North Sea (N3)",
          "Rijnland / Chalk", "Scruff", "Zechstein (salt)"]
# the benchmark's classes are 0 to 5 for the six groups above, in this order
NAMES = ["Upper North Sea", "Middle North Sea", "Lower North Sea", "Rijnland / Chalk", "Scruff", "Zechstein"]
CUBES = {
    "train": ("train/train_seismic.npy", "train/train_labels.npy"),
    "test1": ("test_once/test1_seismic.npy", "test_once/test1_labels.npy"),
}
_mm: dict = {}


def cube(name: str):
    if name not in CUBES:
        raise HTTPException(404, f"cube: one of {', '.join(CUBES)}")
    if name not in _mm:
        s, l = CUBES[name]
        if not (D / s).exists():
            raise HTTPException(503, "no seismic yet: uv run python fetch_data.py seismic")
        _mm[name] = (np.load(D / s, mmap_mode="r"), np.load(D / l, mmap_mode="r"))
    return _mm[name]


def positions(shape: tuple) -> tuple[np.ndarray, np.ndarray]:
    return np.arange(0, shape[0] - P + 1, STRIDE), np.arange(0, shape[1] - P + 1, STRIDE)


def features(sec: np.ndarray) -> np.ndarray:
    """Signatures of the patch grid of one section (traces x samples): shape (n_traces_pos, n_sample_pos, 22)."""
    sec = np.asarray(sec, dtype=np.float32)
    gx, gy = np.gradient(sec, axis=0), np.gradient(sec, axis=1)
    win = lambda a: sliding_window_view(a, (P, P))[::STRIDE, ::STRIDE]  # noqa: E731
    w = win(sec)  # (nt, ns, P, P): traces, samples
    eps = 1e-8
    mean_abs = np.abs(w).mean((2, 3))
    sd = w.std((2, 3))
    z = (w - w.mean((2, 3), keepdims=True)) / (sd[..., None, None] + eps)
    skew, kurt = (z**3).mean((2, 3)), (z**4).mean((2, 3))
    jxx, jyy, jxy = (win(gx * gx).mean((2, 3)), win(gy * gy).mean((2, 3)), win(gx * gy).mean((2, 3)))
    energy = jxx + jyy + eps
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy**2) / energy
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy)
    spec = np.abs(np.fft.rfft(w - w.mean((2, 3), keepdims=True), axis=3)) ** 2  # vertical spectrum per trace
    spec = spec.mean(2)  # average over traces: (nt, ns, P//2+1)
    total = spec[..., 1:].sum(-1) + eps
    bands = [spec[..., a:b].sum(-1) / total for a, b in ((1, 3), (3, 5), (5, 8), (8, 12), (12, 17))]
    lateral = (w[:, :, :-1] * w[:, :, 1:]).mean((2, 3)) / ((w * w).mean((2, 3)) + eps)
    gh = np.abs(win(gx)).mean((2, 3)) / (np.abs(win(gy)).mean((2, 3)) + eps)  # lateral against vertical change
    f = [np.log(mean_abs + eps), np.log(sd + eps), skew, kurt, np.log(energy), coh, coh * np.cos(2 * theta),
         coh * np.sin(2 * theta), *[np.log(b + 1e-4) for b in bands], np.log(total), lateral, np.log(gh + eps)]
    g = np.stack(f, -1).astype(np.float32)
    # context: the mean signature of the 3 x 3 neighbourhood of patches (about 64 x 64 samples), so a chaotic unit
    # reads as chaotic at the scale an interpreter sees it
    ctx = uniform_filter(g, size=(3, 3, 1), mode="nearest")
    return np.concatenate([g, ctx], -1)


def majority(lab: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Majority class and its share, for each patch of a label section."""
    w = sliding_window_view(np.asarray(lab), (P, P))[::STRIDE, ::STRIDE]
    counts = np.stack([(w == c).mean((2, 3)) for c in range(6)], -1)
    return counts.argmax(-1), counts.max(-1)


def build() -> dict:
    seis, labs = cube("train")
    feats, where, label, purity = [], [], [], []
    for i in range(0, seis.shape[0], SECTION_STEP):
        f = features(seis[i])
        m, p = majority(labs[i])
        ti, si = positions(seis[i].shape)
        for a in range(f.shape[0]):
            for b in range(f.shape[1]):
                feats.append(f[a, b]); where.append((i, ti[a], si[b])); label.append(m[a, b]); purity.append(p[a, b])
    x = np.array(feats)
    mu, sd = x.mean(0), x.std(0) + 1e-6
    z = (x - mu) / sd
    u, s, vt = np.linalg.svd(z - z.mean(0), full_matrices=False)
    comp = vt[:PCA_DIMS]
    emb = z @ comp.T
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
    # learned metric: gradient-boosted trees learn the facies from the signatures of the labelled training patches;
    # similarity is then measured between predicted facies probabilities, so it means "same geology"
    label, purity = np.array(label), np.array(purity)
    sel = purity >= 0.8
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, random_state=0).fit(z[sel], label[sel])
    joblib.dump(clf, CLF)
    lemb = np.sqrt(clf.predict_proba(z))
    lemb /= np.linalg.norm(lemb, axis=1, keepdims=True) + 1e-9
    lda = np.zeros(1)
    np.savez_compressed(INDEX, emb=emb.astype(np.float32), lemb=lemb.astype(np.float32), where=np.array(where), label=label,
                        purity=purity, mu=mu, sd=sd, comp=comp, lda=lda)
    _idx.clear()
    meta = {**evaluate("texture"), "learned": evaluate("learned")}
    META.write_text(json.dumps(meta, indent=1))
    return meta


_idx: dict = {}
_clf: dict = {}


def classifier():
    if "m" not in _clf or _clf.get("mtime") != CLF.stat().st_mtime:
        _clf.update(m=joblib.load(CLF), mtime=CLF.stat().st_mtime)
    return _clf["m"]


def index() -> dict:
    if not INDEX.exists():
        raise HTTPException(503, "no index yet: uv run python -m sketches.seismic")
    if "emb" not in _idx or _idx.get("mtime") != INDEX.stat().st_mtime:
        z = np.load(INDEX)
        _idx.update({k: z[k] for k in z.files}, mtime=INDEX.stat().st_mtime)
    return _idx


def embed(f: np.ndarray, mode: str = "texture") -> np.ndarray:
    ix = index()
    z = (f - ix["mu"]) / ix["sd"]
    e = np.sqrt(classifier().predict_proba(z.reshape(-1, z.shape[-1]))).reshape(*z.shape[:-1], -1) if mode == "learned" else z @ ix["comp"].T
    return e / (np.linalg.norm(e, axis=-1, keepdims=True) + 1e-9)


def evaluate(mode: str = "texture", step: int = 10, k: int = 10, min_purity: float = 0.8) -> dict:
    """Precision at k on the held-out test block: matches with the same facies as a query that is mostly one facies."""
    ix = index()
    seis, labs = cube("test1")
    q, ql = [], []
    for i in range(0, seis.shape[0], step):
        f = features(seis[i])
        m, p = majority(labs[i])
        sel = p >= min_purity
        q.append(embed(f, mode)[sel]); ql.append(m[sel])
    q, ql = np.concatenate(q), np.concatenate(ql)
    pool = ix["purity"] >= min_purity
    e, lab = ix["lemb" if mode == "learned" else "emb"][pool], ix["label"][pool]
    top = np.argsort(-(q @ e.T), axis=1)[:, :k]
    hit = lab[top] == ql[:, None]
    prior = np.bincount(lab, minlength=6) / len(lab)
    chance = float((np.bincount(ql, minlength=6) / len(ql) * prior).sum())
    per = {NAMES[c]: {"precision": round(float(hit[ql == c].mean()), 3), "queries": int((ql == c).sum())} for c in range(6) if (ql == c).any()}
    return {"mode": mode, "k": k, "queries": int(len(q)), "index_patches": int(len(ix["emb"])), "precision_at_k": round(float(hit.mean()), 3),
            "chance": round(chance, 3), "per_class": per, "min_purity": min_purity, "sections_indexed": int(len(set(ix["where"][:, 0].tolist())))}


# -- API --


def pack(a: np.ndarray, scale: float) -> str:
    return base64.b64encode(np.clip(np.round(np.asarray(a) / scale * 127), -127, 127).astype(np.int8).tobytes()).decode()


@router.get("")
def slash():
    return RedirectResponse("seismic/")


@router.get("/", response_class=HTMLResponse)
def home():
    return page("seismic.html")


@router.get("/api/info")
def info():
    meta = json.loads(META.read_text()) if META.exists() else None
    out = {"cubes": {}, "facies": NAMES, "patch": P, "metrics": meta}
    for n in CUBES:
        try:
            s, _ = cube(n)
            out["cubes"][n] = {"sections": int(s.shape[0]), "traces": int(s.shape[1]), "samples": int(s.shape[2])}
        except HTTPException:
            pass
    return out


@router.get("/api/section/{name}/{i}")
def section(name: str, i: int):
    s, l = cube(name)
    if not 0 <= i < s.shape[0]:
        raise HTTPException(404, "no such section")
    a = np.asarray(s[i], dtype=np.float32)
    scale = float(np.percentile(np.abs(a), 99)) or 1.0
    return {"name": name, "i": i, "shape": list(a.shape), "scale": scale, "data": pack(a, scale), "labels": base64.b64encode(np.asarray(l[i], dtype=np.uint8).tobytes()).decode()}


class Query(BaseModel):
    cube: Literal["train", "test1"] = "test1"
    section: int = Field(ge=0)
    trace: int = Field(ge=0)
    sample: int = Field(ge=0)
    mode: Literal["texture", "learned"] = "texture"
    k: int = Field(12, ge=1, le=50)


def query_signature(name: str, i: int, t: int, s: int) -> tuple[np.ndarray, int, int]:
    """The signature of the grid patch nearest the click, from the whole section so its context is there too."""
    seis, _ = cube(name)
    f = features(seis[i])
    a = int(np.clip(round((t - P // 2) / STRIDE), 0, f.shape[0] - 1))
    b = int(np.clip(round((s - P // 2) / STRIDE), 0, f.shape[1] - 1))
    return f[a, b], a * STRIDE, b * STRIDE


@router.post("/api/similar")
def similar(q: Query):
    ix = index()
    seis, labs = cube(q.cube)
    if q.section >= seis.shape[0] or q.trace >= seis.shape[1] or q.sample >= seis.shape[2]:
        raise HTTPException(404, "outside the cube")
    sig, t0, s0 = query_signature(q.cube, q.section, q.trace, q.sample)
    p = np.asarray(seis[q.section, t0 : t0 + P, s0 : s0 + P], dtype=np.float32)
    e = embed(sig, q.mode)
    sims = ix["lemb" if q.mode == "learned" else "emb"] @ e
    where = ix["where"]
    if q.cube == "train":  # do not return the query's own neighbourhood
        near = (np.abs(where[:, 0] - q.section) <= 8) & (np.abs(where[:, 1] - t0) < 3 * P)
        sims = np.where(near, -1, sims)
    # one match per neighbourhood, so the list is not ten copies of the same place
    out, taken = [], []
    train = cube("train")[0]
    for j in np.argsort(-sims):
        if sims[j] < -0.5 or len(out) >= q.k:
            break
        w = where[j]
        if any(abs(w[0] - a) <= 8 and abs(w[1] - b) < 2 * P and abs(w[2] - c) < 2 * P for a, b, c in taken):
            continue
        taken.append(tuple(w))
        tp = np.asarray(train[w[0], w[1] : w[1] + P, w[2] : w[2] + P], dtype=np.float32)
        out.append({"similarity": round(float(sims[j]), 3), "section": int(w[0]), "trace": int(w[1]), "sample": int(w[2]),
                    "facies": NAMES[int(ix["label"][j])], "purity": round(float(ix["purity"][j]), 2),
                    "thumb": pack(tp, float(np.percentile(np.abs(tp), 99)) or 1.0)})
    ql = labs[q.section, t0 : t0 + P, s0 : s0 + P]
    cls = np.bincount(np.asarray(ql).ravel(), minlength=6)
    feats = dict(zip(FEATURE_NAMES, [round(float(v), 3) for v in sig[: len(FEATURE_NAMES)]]))
    return {"query": {"section": q.section, "trace": t0, "sample": s0, "size": P, "facies": NAMES[int(cls.argmax())],
                      "purity": round(float(cls.max() / cls.sum()), 2), "thumb": pack(p, float(np.percentile(np.abs(p), 99)) or 1.0),
                      "features": feats, "mode": q.mode},
            "matches": out}


FEATURE_NAMES = ["log mean amplitude", "log amplitude spread", "skew", "kurtosis", "log gradient energy", "layering coherence",
                 "dip cos2θ", "dip sin2θ", "band 1-2", "band 3-4", "band 5-7", "band 8-11", "band 12-16", "log spectrum power",
                 "lateral continuity", "log lateral/vertical change"]


class Explain(BaseModel):
    query: dict
    matches: list[dict]


@router.post("/api/explain")
async def explain(b: Explain):
    from collections import Counter

    c = Counter(m["facies"] for m in b.matches)
    lines = "\n".join(f"{i + 1}. section {m['section']}, trace {m['trace']}, sample {m['sample']}: {m['facies']} (similarity {m['similarity']})" for i, m in enumerate(b.matches))
    try:
        text = await chat(
            [
                {"role": "system", "content": "You are a seismic interpreter. A similarity search found patches that look like the one "
                 "the user clicked, from texture alone (no depth, no labels). From the query's attributes and the labels of the "
                 "matches, say what the clicked feature probably is (reflector character: continuous or chaotic, steep or flat, "
                 "high or low frequency), whether the matches agree with each other, and what to check next (a well tie, a fault "
                 "or salt flank, a different attribute). 120 words at most, plain text. You are not looking at an image; say what "
                 "is uncertain."},
                {"role": "user", "content": f"Query patch: {b.query.get('facies')} (purity {b.query.get('purity')}). Attributes: {b.query.get('features')}\n"
                 f"Matches by facies: {dict(c)}\n{lines}"},
            ],
            max_tokens=500,
        )
    except ModelBusy as e:
        raise HTTPException(503, f"the model is busy: {e}")
    return {"text": text}


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
