# Concepts (short)

- **Target:** share of described CLAY rows naming a green mineral. A reported rate, not true presence.
- **Unit:** wellbore x formation interval. Rows in it = trials.
- **Layer:** one data type -> one log-odds term (LLR). Silent (NaN) when no data.
- **Combiner:** base logit + sum of LLRs -> Platt calibration (fitted out-of-fold).
- **Status:** helps / no evidence / hurts, from blocked-CV gain with a well-bootstrap interval. Hurts = off by default.
- **Validation:** 40 km blocked folds, deviance gain vs constant rate, AUC inside coverage bins.
- **Knowledge:** sourced rules, each tested against data; verdict shown, never hidden.
- **Map:** formation rate + distance-weighted neighbours; grey = beyond 3 ell (no local evidence).
