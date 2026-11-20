"""Gaussian process (kriging) with a linear trend, for surfaces and properties (PLAN P2.2, P3; LOG L056).

y(x) = trend(x) + f(x) + noise; f ~ GP(0, s2 * Matern32(d / ell)); noise_i ~ N(0, nug + obs_var_i) (each point's own measurement variance).
Hyperparameters (ell, s2, nug) by maximum marginal likelihood. Coordinates in km (EPSG:3035).
Posterior samples by Matheron's rule with random Fourier features, so realisations on large lattices stay cheap (torch on cuda if present).
"""
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from scipy.spatial.distance import cdist


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
            best = None
            for ell0 in (5.0, 20.0, 80.0):  # a few starts: the likelihood can have several local optima
                p0 = np.log([ell0, 0.7 * v, 0.3 * v + 1e-6])
                res = minimize(nll, p0, method="L-BFGS-B", bounds=[(lo, hi), (np.log(1e-6 * v), np.log(10 * v)), (np.log(1e-8 * v + 1e-9), np.log(10 * v))])
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
        # Matern nu=3/2 with argument sqrt(3) d / ell: spectral density is a bivariate Student t, 2 nu = 3 dof, scale 1 / ell
        nu = 1.5
        z = rng.standard_normal((features, 2))
        g = rng.chisquare(2 * nu, size=(features, 1))
        W = z * np.sqrt(2 * nu / g) / self.ell
        b = rng.uniform(0, 2 * np.pi, size=features)
        w = rng.standard_normal((features, n))
        amp = np.sqrt(2.0 * self.s2 / features)
        try:
            import torch

            dev = device if (device == "cuda" and torch.cuda.is_available()) else "cpu"
            T = lambda a: torch.as_tensor(a, dtype=torch.float64, device=dev)
            phi_s = amp * torch.cos(T(Xs) @ T(W).T + T(b))
            phi_o = amp * torch.cos(T(self.X) @ T(W).T + T(b))
            f_s, f_o = (phi_s @ T(w)).cpu().numpy(), (phi_o @ T(w)).cpu().numpy()
        except ImportError:
            phi_s = amp * np.cos(np.asarray(Xs) @ W.T + b)
            phi_o = amp * np.cos(self.X @ W.T + b)
            f_s, f_o = phi_s @ w, phi_o @ w
        eps = rng.standard_normal((len(self.y), n)) * np.sqrt(self.nug + self.ov)[:, None]
        r = (self.y - design(self.X, self.deg) @ self.beta)[:, None] - f_o - eps
        upd = matern32(cdist(np.asarray(Xs, float), self.X), self.ell, self.s2) @ cho_solve(self.c, r)
        return (design(Xs, self.deg) @ self.beta)[:, None] + f_s + upd
