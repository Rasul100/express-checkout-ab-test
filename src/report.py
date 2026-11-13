"""Print every number quoted in README. Run: python src/report.py

README must be regenerated from this output after any change to the generator.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze import (  # noqa: E402
    cumulative_lift,
    lift_difference,
    load,
    mde,
    revenue_per_user,
    sample_size,
    segment_rpu,
    segments_holm,
    srm,
    two_prop,
)


def pp(x: float) -> str:
    return f"{x * 100:+.2f} п.п."


def main() -> None:
    df = load()
    s = srm(df)
    ov = two_prop(df)
    rev = revenue_per_user(df)
    n_per = min(ov["n_control"], ov["n_treatment"])

    print(f"N = {s['n']:,}, treatment share = {s['share_treatment']:.4f}, SRM p = {s['p_value']:.2f}")
    print(f"CR control   {ov['p_control']:.2%}")
    print(f"CR treatment {ov['p_treatment']:.2%}  ({ov['rel_lift']:+.1%} отн., p = {ov['p_value']:.4f})")
    print(f"Δ CR abs     {pp(ov['abs_lift'])}  95% CI [{pp(ov['ci_abs'][0])} … {pp(ov['ci_abs'][1])}]")
    print(f"MDE (80% power) {mde(n_per, ov['p_control']) * 100:.2f} п.п.; "
          f"N на ветку для +8% отн.: {sample_size(ov['p_control']):,}")
    print(f"RPU {rev['rpu_control']:.0f} → {rev['rpu_treatment']:.0f} ₽, Δ {rev['rpu_diff']:+.1f} ₽ "
          f"95% CI [{rev['rpu_ci'][0]:+.1f} … {rev['rpu_ci'][1]:+.1f}], p = {rev['p_value']:.3f}")
    print(f"AOV {rev['aov_control']:.0f} → {rev['aov_treatment']:.0f} ₽ ({rev['aov_rel']:+.1%})")

    print("\nСегменты (Holm по 5 срезам):")
    seg = segments_holm(df, ["device", "user_type"])
    for r in seg.itertuples():
        print(f"  {r.value:<10} n={r.n_control + r.n_treatment:>6,}  {r.p_control:.2%} → {r.p_treatment:.2%}  "
              f"{r.rel_lift:+.1%}  Δ CI [{pp(r.ci_abs[0])} … {pp(r.ci_abs[1])}]  "
              f"p = {r.p_value:.4f}  p_holm = {r.p_holm:.4f}  {'значимо' if r.significant else 'нет'}")

    print("\nRPU по девайсам:")
    for r in segment_rpu(df, "device").itertuples():
        print(f"  {r.value:<8} Δ {r.rpu_diff:+.1f} ₽  CI [{r.rpu_ci[0]:+.1f} … {r.rpu_ci[1]:+.1f}]  p = {r.p_value:.4f}")

    print("\nРазница эффектов (interaction):")
    mob = df.assign(platform=df["device"].where(df["device"] == "desktop", "mobile"))
    for frame, col, a, b in [(mob, "platform", "desktop", "mobile"), (df, "user_type", "new", "returning")]:
        r = lift_difference(frame, col, a, b)
        print(f"  {a} vs {b}: {pp(r['lift_a'])} vs {pp(r['lift_b'])}, разница {pp(r['diff'])} "
              f"CI [{pp(r['ci'][0])} … {pp(r['ci'][1])}], p = {r['p_value']:.4f}")

    print("\nКумулятивный эффект по дням:")
    for r in cumulative_lift(df).itertuples():
        print(f"  {r.day:%m-%d}  {r.rel_lift:+.1%}  p = {r.p_value:.3f}")


if __name__ == "__main__":
    main()
