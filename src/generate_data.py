"""A/B: Express Checkout on PDP. Heterogeneous lift: desktop yes, mobile almost none."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEED = 24
N = 42_000
START = pd.Timestamp("2026-08-03")
END = pd.Timestamp("2026-08-16")


def build(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    user_id = np.arange(1, N + 1)
    variant = rng.choice(["control", "treatment"], N, p=[0.5, 0.5])
    device = rng.choice(["desktop", "ios", "android"], N, p=[0.41, 0.33, 0.26])
    user_type = rng.choice(["new", "returning"], N, p=[0.46, 0.54])
    channel = rng.choice(
        ["organic", "paid_search", "paid_social", "email"],
        N,
        p=[0.36, 0.28, 0.22, 0.14],
    )

    base = np.full(N, 0.078)
    base = np.where(device == "desktop", base + 0.022, base - 0.012)
    base = np.where(user_type == "returning", base + 0.018, base)
    base = np.where(channel == "email", base + 0.015, base)
    base = np.where(channel == "paid_social", base - 0.012, base)

    lift = np.zeros(N)
    is_t = variant == "treatment"
    lift = np.where(is_t & (device == "desktop"), 0.018, lift)
    lift = np.where(is_t & (device == "android"), 0.0, lift)
    lift = np.where(is_t & (device == "ios"), -0.004, lift)
    lift = np.where(is_t & (user_type == "new") & (device == "desktop"), lift + 0.005, lift)

    p_buy = np.clip(base + lift, 0.01, 0.35)
    purchased = rng.random(N) < p_buy

    aov_mu = np.where(device == "desktop", 2100, 1650)
    aov_mu = np.where(user_type == "returning", aov_mu + 180, aov_mu)
    # Treatment pulls in smaller baskets (impulse 1-click).
    aov_mu = np.where(is_t & purchased, aov_mu * 0.965, aov_mu)
    revenue = np.where(purchased, rng.lognormal(np.log(aov_mu), 0.35), 0.0)
    revenue = np.round(revenue, 2)

    assigned = START + pd.to_timedelta(rng.integers(0, 14, N), unit="D")
    assigned += pd.to_timedelta(rng.integers(0, 24, N), unit="h")

    return pd.DataFrame(
        {
            "user_id": user_id,
            "variant": variant,
            "device": device,
            "user_type": user_type,
            "channel": channel,
            "assigned_at": assigned,
            "purchased": purchased.astype(int),
            "revenue": revenue,
        }
    )


def save(df: pd.DataFrame) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    db = DATA / "experiment.sqlite"
    if db.exists():
        db.unlink()
    df.to_csv(DATA / "assignments.csv", index=False)
    conn = sqlite3.connect(db)
    df.to_sql("assignments", conn, index=False, if_exists="replace")
    conn.close()


def main() -> None:
    df = build()
    save(df)
    print(df.groupby("variant")[["purchased", "revenue"]].mean(), file=sys.stderr)
    print(DATA / "experiment.sqlite")


if __name__ == "__main__":
    main()
