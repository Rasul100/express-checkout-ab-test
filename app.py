from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from analyze import load, mde, revenue_per_user, sample_size, segments, srm, two_prop  # noqa: E402
from generate_data import build, save  # noqa: E402

st.set_page_config(page_title="A/B Express Checkout", layout="wide")


@st.cache_data(show_spinner="Собираю назначения эксперимента…")
def _df() -> pd.DataFrame:
    db = ROOT / "data" / "experiment.sqlite"
    if not db.exists():
        save(build())
    return load()


def _pct(x: float) -> str:
    return f"{x:+.1%}" if pd.notna(x) else "—"


df = _df()
ov = two_prop(df)
rev = revenue_per_user(df)
srm_res = srm(df)
n_per = min(ov["n_control"], ov["n_treatment"])
detected_mde = mde(n_per, ov["p_control"])
need_n = sample_size(ov["p_control"], rel_mde=0.08)

st.title("Express Checkout на карточке товара")
st.markdown(
    "Нужно решить, **раскатывать ли «Купить сразу» на всех**, если средний conversion вырос."
)

st.markdown(
    """
**Гипотеза.** Кнопка «Купить сразу» на PDP снизит трение чекаута и поднимет conversion,
не уронив выручку на пользователя.
"""
)

a, b, c, d = st.columns(4)
a.metric("SRM p-value", f"{srm_res['p_value']:.2f}", "ок" if srm_res["pass"] else "сломан сплит")
b.metric("CR control", f"{ov['p_control']:.2%}")
c.metric("CR treatment", f"{ov['p_treatment']:.2%}", _pct(ov["rel_lift"]))
d.metric("p-value CR", f"{ov['p_value']:.3f}", "значимо" if ov["significant"] else "нет")

e1, e2, e3 = st.columns(3)
e1.metric("Δ CR абс.", f"{ov['abs_lift']:+.2%}", f"95% CI {ov['ci_abs'][0]:+.2%}…{ov['ci_abs'][1]:+.2%}")
e2.metric("RPU", f"{rev['rpu_treatment']:.0f} ₽", f"{rev['rpu_diff']:+.0f} ₽ vs control")
e3.metric("AOV", f"{rev['aov_treatment']:.0f} ₽", f"{rev['aov_rel']:+.1%} к control")

fig = go.Figure()
for var, p, ci in [
    ("control", ov["p_control"], ov["ci_control"]),
    ("treatment", ov["p_treatment"], ov["ci_treatment"]),
]:
    fig.add_trace(
        go.Bar(
            x=[var],
            y=[p],
            error_y=dict(type="data", array=[ci[1] - p], arrayminus=[p - ci[0]]),
            name=var,
        )
    )
fig.update_layout(yaxis_tickformat=".1%", height=320, showlegend=False, margin=dict(t=20), yaxis_title="Conversion")
st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("Гетерогенность: девайс")
    seg_d = segments(df, "device")
    fig_d = px.bar(
        seg_d,
        x="value",
        y="rel_lift",
        color="significant",
        text=seg_d["rel_lift"].map(lambda x: f"{x:+.0%}"),
        labels={"rel_lift": "Относительный lift", "value": "Девайс", "significant": "p<0.05"},
    )
    fig_d.update_traces(textposition="outside")
    fig_d.update_layout(yaxis_tickformat=".0%", height=340, margin=dict(t=20))
    st.plotly_chart(fig_d, use_container_width=True)
    st.dataframe(
        seg_d[["value", "n_control", "n_treatment", "p_control", "p_treatment", "rel_lift", "p_value"]].assign(
            p_control=lambda d: d["p_control"].map(lambda x: f"{x:.2%}"),
            p_treatment=lambda d: d["p_treatment"].map(lambda x: f"{x:.2%}"),
            rel_lift=lambda d: d["rel_lift"].map(_pct),
            p_value=lambda d: d["p_value"].map(lambda x: f"{x:.3f}"),
        ),
        hide_index=True,
        use_container_width=True,
    )

with right:
    st.subheader("Новые vs вернувшиеся")
    seg_u = segments(df, "user_type")
    fig_u = px.bar(
        seg_u,
        x="value",
        y="rel_lift",
        color="significant",
        text=seg_u["rel_lift"].map(lambda x: f"{x:+.0%}"),
        labels={"rel_lift": "Относительный lift", "value": "Тип пользователя", "significant": "p<0.05"},
    )
    fig_u.update_traces(textposition="outside")
    fig_u.update_layout(yaxis_tickformat=".0%", height=340, margin=dict(t=20))
    st.plotly_chart(fig_u, use_container_width=True)
    st.dataframe(
        seg_u[["value", "n_control", "p_control", "p_treatment", "rel_lift", "p_value"]].assign(
            p_control=lambda d: d["p_control"].map(lambda x: f"{x:.2%}"),
            p_treatment=lambda d: d["p_treatment"].map(lambda x: f"{x:.2%}"),
            rel_lift=lambda d: d["rel_lift"].map(_pct),
            p_value=lambda d: d["p_value"].map(lambda x: f"{x:.3f}"),
        ),
        hide_index=True,
        use_container_width=True,
    )

st.subheader("Мощность и MDE")
st.write(
    f"На текущем N ≈ {n_per:,} на ветку MDE по CR около **{detected_mde:.2%} абс.** "
    f"(80% power, α=0.05). Чтобы поймать +8% относительно базы {ov['p_control']:.1%}, "
    f"нужно примерно **{need_n:,}** пользователей на вариант. Факт: overall и desktop мощности хватает; "
    "на iOS «нет эффекта» ≠ доказанный ноль, если lift меньше MDE."
)

st.subheader("Вывод")
st.markdown(
    f"""
**Что сделал.** Проверил, стоит ли включать кнопку «Купить сразу» всем пользователям — провёл A/B-тест
и разложил результат по устройствам и типам пользователей.

**Что понял.** Тест прошёл честно, группы разделились ровно. В среднем конверсия выросла на **{_pct(ov["rel_lift"])}**,
но этот рост почти целиком дал **desktop** — на iOS и Android значимого эффекта нет. Средний чек чуть просел,
но выручка с одного пользователя всё равно выросла (**{rev["rpu_diff"]:+.0f} ₽**), потому что покупать стали чаще.

**Что делать.** Включать кнопку на desktop уже сейчас. На iOS и Android пока не раскатывать «как есть» — сначала
доработать сохранённый способ оплаты и адрес, и только потом тестировать там заново. Итог мерить не по среднему чеку,
а по выручке на пользователя (RPU), иначе можно принять неверное решение из-за просевшего AOV.
"""
)
