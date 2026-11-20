"""Sophisticated surface candidates, judged by the same blocked CV as the simple ones (PLAN P2.2, LOG L057).

rk_gbm  regression kriging with a machine-learned trend: gradient-boosted trees on covariates (x, y, and the predicted depths of the
        seabed and every shallower group at that point), then a GP on the out-of-fold residuals. Captures non-linear relations between
        surfaces, e.g. a deep top that follows the overlying Cretaceous only in some areas.
dkl     deep-kernel GP: a small neural network maps (x, y, covariates) to features; an RBF kernel on those features allows non-stationary
        covariance (sharp changes across fault zones). Trained by exact marginal likelihood with Adam, on cuda when available.
Covariates at held-out points come from shallower surfaces refitted without that fold: no information from the held-out block leaks in.
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

from se.earth.gp import GP

Z90 = 1.645


class RKGBM:
    def fit(self, C, X, z, v):
        self.gbm = lambda: HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=300, min_samples_leaf=15, l2_regularization=1.0, random_state=0)
        oof = np.zeros(len(z))
        for tr, te in KFold(5, shuffle=True, random_state=0).split(C):  # out-of-fold trend, so the GP sees honest residuals
            oof[te] = self.gbm().fit(C[tr], z[tr]).predict(C[te])
        self.m = self.gbm().fit(C, z)
        self.gp = GP(0).fit(X, z - oof, v)
        return self

    def predict(self, C, X, latent=True):
        mu, var = self.gp.predict(X, latent=latent)
        return self.m.predict(C) + mu, np.sqrt(var)


class DKL:
    def __init__(self, hidden=32, feats=4, steps=300, lr=0.01, device=None):
        self.hidden, self.feats, self.steps, self.lr, self.device = hidden, feats, steps, lr, device

    def fit(self, C, X, z, v):
        import torch

        dev = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        torch.manual_seed(0)
        self.mu_c, self.sd_c = C.mean(0), C.std(0) + 1e-9
        self.mz, self.sz = z.mean(), z.std() + 1e-9
        T = lambda a: torch.as_tensor(a, dtype=torch.float64, device=dev)
        Cn, zn, vn = T((C - self.mu_c) / self.sd_c), T((z - self.mz) / self.sz), T(v / self.sz ** 2)
        d = Cn.shape[1]
        net = torch.nn.Sequential(torch.nn.Linear(d, self.hidden), torch.nn.Tanh(), torch.nn.Linear(self.hidden, self.feats)).double().to(dev)
        lo, la, ln = (torch.zeros(1, dtype=torch.float64, device=dev, requires_grad=True) for _ in range(3))
        opt = torch.optim.Adam(list(net.parameters()) + [lo, la, ln], lr=self.lr)
        I = torch.eye(len(zn), dtype=torch.float64, device=dev)

        def K(A, B):
            return torch.exp(la) * torch.exp(-0.5 * torch.cdist(A, B) ** 2 / torch.exp(2 * lo))

        for _ in range(self.steps):
            opt.zero_grad()
            F = net(Cn)
            Kn = K(F, F) + torch.diag(vn) + (torch.exp(ln) + 1e-6) * I
            L = torch.linalg.cholesky(Kn)
            a = torch.cholesky_solve(zn[:, None], L)
            nll = 0.5 * (zn[:, None] * a).sum() + torch.log(torch.diagonal(L)).sum()
            nll.backward(); opt.step()
        with torch.no_grad():
            F = net(Cn)
            Kn = K(F, F) + torch.diag(vn) + (torch.exp(ln) + 1e-6) * I
            self.L = torch.linalg.cholesky(Kn); self.a = torch.cholesky_solve(zn[:, None], self.L)
        self.net, self.K, self.F, self.T, self.ln, self.la, self.dev = net, K, F, T, ln, la, dev
        return self

    def predict(self, C, X, latent=True):
        import torch

        with torch.no_grad():
            Fs = self.net(self.T((C - self.mu_c) / self.sd_c))
            Ks = self.K(Fs, self.F)
            mu = (Ks @ self.a).squeeze(1)
            w = torch.cholesky_solve(Ks.T, self.L)
            var = torch.clamp(torch.exp(self.la) - (Ks * w.T).sum(1), min=0) + (0 if latent else torch.exp(self.ln))
            return (mu.cpu().numpy() * self.sz + self.mz), np.sqrt(var.cpu().numpy()) * self.sz


def fold_of(x, y, km=40.0, k=5):
    """One fold assignment shared by all horizons (by 40 km block), so shallower surfaces can be refitted per fold and reused."""
    b = np.floor(x / km).astype(np.int64) * 100003 + np.floor(y / km).astype(np.int64)
    return (np.abs(b * 2654435761) % 2 ** 32) % k


def evaluate(groups, obs, base_kind, make_fit, kinds=("rk_gbm", "dkl"), k=5):
    """For each group below the first: CV RMSE and nested 90 percent coverage of the base model and the hybrids, with fold-refitted covariates.

    groups: ordered names (seabed first); obs: {name: DataFrame x, y, z, var, wellbore}; base_kind: {name: chosen simple kind};
    make_fit(kind, X, z, v): returns an object with predict(X, latent) -> (mu, sd).
    """
    out, fold_fits = {}, {}
    for f in range(k):  # shallower surfaces refitted without fold f, once per fold
        fold_fits[f] = {}
        for g in groups:
            o = obs[g]; tr = fold_of(o.x.to_numpy(), o.y.to_numpy(), k=k) != f
            fold_fits[f][g] = make_fit(base_kind.get(g, "gp0"), o[["x", "y"]].to_numpy()[tr], o.z.to_numpy()[tr], o["var"].to_numpy()[tr])

    def cov(fits, gs, X):
        return np.column_stack([X] + [fits[g].predict(X, latent=True)[0] for g in gs])

    for i, g in enumerate(groups):
        if i < 2:
            continue
        shallow = groups[:i]
        o = obs[g]; X, z, v = o[["x", "y"]].to_numpy(), o.z.to_numpy(), o["var"].to_numpy(); fo = fold_of(o.x.to_numpy(), o.y.to_numpy(), k=k)
        res = {}
        for kind in ("base",) + tuple(kinds):
            e, zs = np.full(len(z), np.nan), np.full(len(z), np.nan)
            for f in range(k):
                te, tr = fo == f, fo != f
                if te.sum() == 0 or tr.sum() < 15:
                    continue
                fits = fold_fits[f]
                if kind == "base":
                    m, s = fits[g].predict(X[te], latent=False)
                else:
                    Ctr, Cte = cov(fits, shallow, X[tr]), cov(fits, shallow, X[te])
                    try:
                        mdl = (RKGBM() if kind == "rk_gbm" else DKL()).fit(Ctr, X[tr], z[tr], v[tr])
                        m, s = mdl.predict(Cte, X[te], latent=False)
                    except Exception as ex:  # e.g. torch missing for dkl: the candidate is skipped, said so
                        res[kind] = {"skipped": f"{type(ex).__name__}: {ex}"[:120]}; break
                e[te] = m - z[te]; zs[te] = (m - z[te]) / np.sqrt(s ** 2 + v[te])
            if kind in res:
                continue
            ok = np.isfinite(e)
            inside = []
            for f in range(k):
                sel = ok & (fo == f); oth = ok & (fo != f)
                if sel.sum() and oth.sum():
                    kf = max(1.0, float(np.percentile(np.abs(zs[oth]), 90)) / Z90); inside += list(np.abs(zs[sel]) <= Z90 * kf)
            res[kind] = {"rmse": round(float(np.sqrt(np.mean(e[ok] ** 2))), 1), "cover90_nested": round(float(np.mean(inside)), 3) if inside else None,
                         "inflation": round(max(1.0, float(np.percentile(np.abs(zs[ok]), 90)) / Z90), 3)}
        scored = {kk: r["rmse"] for kk, r in res.items() if "rmse" in r}
        res["winner"] = min(scored, key=scored.get)
        out[g] = res
    return out, cov
