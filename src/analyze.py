from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import proportion_confint, proportions_ztest
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "experiment.sqlite"
ALPHA = 0.05


def load() -> pd.DataFrame:
    if not DB.exists():
        from generate_data import build, save

        save(build())
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("select * from assignments", conn)
    conn.close()
    df["assigned_at"] = pd.to_datetime(df["assigned_at"])
    return df


def srm(df: pd.DataFrame, expected: float = 0.5) -> dict:
    n_t = int((df["variant"] == "treatment").sum())
    n = len(df)
    pval = float(stats.binomtest(n_t, n, expected).pvalue)
    return {
        "n": n,
        "n_treatment": n_t,
        "share_treatment": n_t / n,
        "p_value": pval,
        "pass": pval > 0.001,
    }


def two_prop(df: pd.DataFrame, col: str = "purchased") -> dict:
    g = df.groupby("variant")[col]
    n_c = int(g.size().get("control", 0))
    n_t = int(g.size().get("treatment", 0))
    x_c = int(g.sum().get("control", 0))
    x_t = int(g.sum().get("treatment", 0))
    p_c = x_c / n_c if n_c else 0
    p_t = x_t / n_t if n_t else 0
    stat, pval = proportions_ztest([x_t, x_c], [n_t, n_c], alternative="two-sided")
    ci_c = proportion_confint(x_c, n_c, alpha=ALPHA, method="wilson")
    ci_t = proportion_confint(x_t, n_t, alpha=ALPHA, method="wilson")
    abs_lift = p_t - p_c
    rel_lift = abs_lift / p_c if p_c else math.nan
    se = math.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    z = stats.norm.ppf(1 - ALPHA / 2)
    return {
        "n_control": n_c,
        "n_treatment": n_t,
        "p_control": p_c,
        "p_treatment": p_t,
        "abs_lift": abs_lift,
        "rel_lift": rel_lift,
        "ci_abs": (abs_lift - z * se, abs_lift + z * se),
        "ci_control": ci_c,
        "ci_treatment": ci_t,
        "z": float(stat),
        "p_value": float(pval),
        "significant": float(pval) < ALPHA,
    }


def revenue_per_user(df: pd.DataFrame) -> dict:
    c = df.loc[df["variant"] == "control", "revenue"]
    t = df.loc[df["variant"] == "treatment", "revenue"]
    stat, pval = stats.ttest_ind(t, c, equal_var=False)
    diff = float(t.mean() - c.mean())
    se = math.sqrt(c.var(ddof=1) / len(c) + t.var(ddof=1) / len(t))
    z = stats.norm.ppf(1 - ALPHA / 2)
    aov_c = c[c > 0].mean() if (c > 0).any() else 0
    aov_t = t[t > 0].mean() if (t > 0).any() else 0
    return {
        "rpu_control": float(c.mean()),
        "rpu_treatment": float(t.mean()),
        "rpu_diff": diff,
        "rpu_ci": (diff - z * se, diff + z * se),
        "p_value": float(pval),
        "aov_control": float(aov_c),
        "aov_treatment": float(aov_t),
        "aov_rel": float(aov_t / aov_c - 1) if aov_c else math.nan,
    }


def mde(n_per: int, p_base: float, power: float = 0.8) -> float:
    es = NormalIndPower().solve_power(
        effect_size=None,
        nobs1=n_per,
        alpha=ALPHA,
        power=power,
        ratio=1.0,
        alternative="two-sided",
    )
    # Cohen h back to approx absolute lift near p_base
    # h = 2asin(sqrt(p1)) - 2asin(sqrt(p0))
    h = float(es)
    p1 = math.sin(math.asin(math.sqrt(p_base)) + h / 2) ** 2
    return p1 - p_base


def sample_size(p_base: float, rel_mde: float = 0.08, power: float = 0.8) -> int:
    p1 = p_base * (1 + rel_mde)
    h = proportion_effectsize(p1, p_base)
    n = NormalIndPower().solve_power(effect_size=h, alpha=ALPHA, power=power, ratio=1.0)
    return int(math.ceil(n))


def segments(df: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for key, part in df.groupby(col):
        if part["variant"].nunique() < 2:
            continue
        res = two_prop(part)
        res["segment"] = col
        res["value"] = key
        rows.append(res)
    return pd.DataFrame(rows)
