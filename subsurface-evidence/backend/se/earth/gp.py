"""Gaussian process (kriging) with a linear trend, for surfaces and properties (PLAN P2.2, P3; LOG L056).

y(x) = trend(x) + f(x) + noise; f ~ GP(0, s2 * Matern32(d / ell)); noise_i ~ N(0, nug + obs_var_i) (each point's own measurement variance).
Hyperparameters (ell, s2, nug) by maximum marginal likelihood. Coordinates in km (EPSG:3035).
Posterior samples by Matheron's rule with random Fourier features, so realisations on large lattices stay cheap (torch on cuda if present).
"""
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from scipy.spatial.distance import cdist


TORCH_MIN_N = 300  # below this the numpy likelihood is as fast


def _torch_nll(D, r, ov, v):
    """Negative log marginal likelihood and its gradient in log(ell, s2, nug), float64 torch, on folds.device(); same model as GP.nll."""
    import torch

    from se.earth.folds import device

    dev = device() if device() != "cuda" or torch.cuda.is_available() else "cpu"
    dt = torch.float32 if dev == "cuda" else torch.float64  # consumer GPUs run float64 at a small fraction of float32 speed; the final fit stays float64
    sc = float(np.sqrt(v)); Dt, rt, ovt = (torch.as_tensor(np.asarray(a, float), dtype=dt, device=dev) for a in (D, np.asarray(r) / sc, np.asarray(ov) / v))
    I = torch.eye(len(r), dtype=dt, device=dev)

    def f(p):  # in units of the residual variance v (better conditioned in float32); log det shifts by a constant, the optimum does not move
        pt = torch.as_tensor(p - np.r_[0.0, np.log(v), np.log(v)], dtype=dt, device=dev).requires_grad_(True); ell, s2, nug = torch.exp(pt)
        q = np.sqrt(3.0) * Dt / ell; K = s2 * (1 + q) * torch.exp(-q) + torch.diag(nug + ovt) + (1e-6 if dt == torch.float32 else 1e-8) * I
        L, info = torch.linalg.cholesky_ex(K)
        if int(info) != 0:
            return 1e12, np.zeros(3)
        a = torch.cholesky_solve(rt[:, None], L)[:, 0]
        val = 0.5 * rt @ a + torch.log(torch.diagonal(L)).sum(); val.backward()
        return float(val.detach()), pt.grad.double().cpu().numpy()
    return f


def matern32(d, ell, s2):
    r = np.sqrt(3.0) * d / ell
    return s2 * (1.0 + r) * np.exp(-r)


def design(X, deg: int):
    X = np.asarray(X, float)
    return np.ones((len(X), 1)) if deg == 0 else np.c_[np.ones(len(X)), X]


class GP:
    def __init__(self, deg: int = 1, ell_bounds=(2.0, 400.0)):
        self.deg, self.ell_bounds = deg, ell_bounds

    def fit(self, X, y, obs_var=None, params=None):
        X, y = np.asarray(X, float), np.asarray(y, float)
        ov = np.zeros(len(y)) if obs_var is None else np.asarray(obs_var, float)
        self.X, self.y, self.ov = X, y, ov
        F = design(X, self.deg)
        self.beta = np.linalg.lstsq(F, y, rcond=None)[0]
        r = y - F @ self.beta
        D = cdist(X, X)
        v = max(float(np.var(r)), 1e-6)

        def nll(p):
            ell, s2, nug = np.exp(p)
            K = matern32(D, ell, s2) + np.diag(nug + ov) + 1e-8 * v * np.eye(len(y))
            try:
                c = cho_factor(K, lower=True)
            except np.linalg.LinAlgError:
                return 1e12
            a = cho_solve(c, r)
            return 0.5 * r @ a + np.log(np.diag(c[0])).sum()

        if params is None:
            lo, hi = np.log(self.ell_bounds)
            fun, jac = nll, False
            from se.earth.folds import device

            if len(y) >= TORCH_MIN_N and device() == "cuda":  # P10.1: exact gradients in torch on the GPU; measured 1.0-1.5x faster (L076), so opt-in
                fun, jac = _torch_nll(D, r, ov, v), True
            best = None
            for ell0 in (5.0, 20.0, 80.0):  # a few starts: the likelihood can have several local optima
                p0 = np.log([ell0, 0.7 * v, 0.3 * v + 1e-6])
                res = minimize(fun, p0, jac=jac, method="L-BFGS-B", bounds=[(lo, hi), (np.log(1e-6 * v), np.log(10 * v)), (np.log(1e-8 * v + 1e-9), np.log(10 * v))])
                if best is None or res.fun < best.fun:
                    best = res
            params = tuple(np.exp(best.x))
        self.ell, self.s2, self.nug = params
        K = matern32(D, self.ell, self.s2) + np.diag(self.nug + ov) + 1e-8 * v * np.eye(len(y))
        self.c = cho_factor(K, lower=True)
        self.alpha = cho_solve(self.c, r)
        return self

    def predict(self, Xs, latent: bool = True):
        """Mean and variance at Xs. latent=True: the surface itself; False: a new observation (adds the nugget)."""
        Xs = np.asarray(Xs, float)
        Ks = matern32(cdist(Xs, self.X), self.ell, self.s2)
        mu = design(Xs, self.deg) @ self.beta + Ks @ self.alpha
        v = cho_solve(self.c, Ks.T)
        var = np.maximum(self.s2 - np.einsum("ij,ji->i", Ks, v), 0.0) + (0.0 if latent else self.nug)
        return mu, var

    def params(self) -> dict:
        return {"ell_km": float(self.ell), "sill": float(self.s2), "nugget": float(self.nug), "trend": [float(b) for b in self.beta], "n": int(len(self.y))}

    def sample(self, Xs, n: int, seed: int = 0, features: int = 2000, device: str = "cpu"):
        """n posterior samples of the latent surface at Xs (Matheron's rule; prior by random Fourier features of the Matern 3/2 kernel)."""
        rng = np.random.default_rng(seed)
        f_all = prior_field(np.r_[np.asarray(Xs, float), self.X], self.ell, n, seed=seed, features=features, device=device) * np.sqrt(self.s2)
        f_s, f_o = f_all[: len(Xs)], f_all[len(Xs):]
        eps = rng.standard_normal((len(self.y), n)) * np.sqrt(self.nug + self.ov)[:, None]
        r = (self.y - design(self.X, self.deg) @ self.beta)[:, None] - f_o - eps
        upd = matern32(cdist(np.asarray(Xs, float), self.X), self.ell, self.s2) @ cho_solve(self.c, r)
        return (design(Xs, self.deg) @ self.beta)[:, None] + f_s + upd


def prior_field(X, ell, n: int, seed: int = 0, features: int = 2000, device: str = "cpu") -> np.ndarray:
    """n draws of a unit-variance Matern 3/2 random field (correlation length ell, km) at points X (km), shape (len(X), n).
    Random Fourier features: the Matern nu=3/2 spectral density with argument sqrt(3) d / ell is a bivariate Student t (3 dof, scale 1/ell).
    Used for posterior samples (GP.sample) and for spatially correlated Monte Carlo noise (targets, volumes; P10.3)."""
    rng = np.random.default_rng(seed); nu = 1.5
    W = rng.standard_normal((features, 2)) * np.sqrt(2 * nu / rng.chisquare(2 * nu, size=(features, 1))) / ell
    b = rng.uniform(0, 2 * np.pi, size=features); w = rng.standard_normal((features, n)); amp = np.sqrt(2.0 / features)
    try:
        import torch

        dev = device if (device == "cuda" and torch.cuda.is_available()) else "cpu"
        T = lambda a: torch.as_tensor(a, dtype=torch.float32, device=dev)
        out = torch.cos(T(X) @ T(W).T + T(b)) @ T(w) * amp
        return out.cpu().numpy().astype(np.float64)
    except ImportError:
        return amp * np.cos(np.asarray(X, float) @ W.T + b) @ w
