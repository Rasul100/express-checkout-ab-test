from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

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
from generate_data import build, save  # noqa: E402

st.set_page_config(page_title="A/B Express Checkout", layout="wide")
ALPHA_UI = 0.05


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
d.metric(
    "p-value CR",
    "< 0.001" if ov["p_value"] < 0.001 else f"{ov['p_value']:.3f}",
    "значимо" if ov["significant"] else "нет",
)

e1, e2, e3 = st.columns(3)
e1.metric(
    "Δ CR абс.",
    f"{ov['abs_lift'] * 100:+.2f} п.п.",
    f"95% CI {ov['ci_abs'][0] * 100:+.2f}…{ov['ci_abs'][1] * 100:+.2f} п.п.",
)
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

seg_all = segments_holm(df, ["device", "user_type"])
st.caption(
    "Срезы device и user_type заданы до анализа. Все 5 проверок — одна семья, p-value скорректированы "
    "методом Холма: иначе шанс хотя бы одного ложного «значимо» ≈ 23%, а не 5%."
)


def _seg_table(seg: pd.DataFrame) -> pd.DataFrame:
    return seg[["value", "n_control", "n_treatment", "p_control", "p_treatment", "rel_lift", "p_value", "p_holm"]].assign(
        p_control=lambda d: d["p_control"].map(lambda x: f"{x:.2%}"),
        p_treatment=lambda d: d["p_treatment"].map(lambda x: f"{x:.2%}"),
        ci=seg["ci_abs"].map(lambda c: f"{c[0] * 100:+.2f}…{c[1] * 100:+.2f} п.п."),
        rel_lift=lambda d: d["rel_lift"].map(_pct),
        p_value=lambda d: d["p_value"].map(lambda x: f"{x:.3f}"),
        p_holm=lambda d: d["p_holm"].map(lambda x: f"{x:.3f}"),
    )


left, right = st.columns(2)
with left:
    st.subheader("Гетерогенность: девайс")
    seg_d = seg_all[seg_all["segment"] == "device"]
    fig_d = px.bar(
        seg_d,
        x="value",
        y="rel_lift",
        color="significant",
        text=seg_d["rel_lift"].map(lambda x: f"{x:+.0%}"),
        labels={"rel_lift": "Относительный lift", "value": "Девайс", "significant": "p_holm<0.05"},
    )
    fig_d.update_traces(textposition="outside")
    fig_d.update_layout(yaxis_tickformat=".0%", height=340, margin=dict(t=20))
    st.plotly_chart(fig_d, use_container_width=True)
    st.dataframe(_seg_table(seg_d), hide_index=True, use_container_width=True)

with right:
    st.subheader("Новые vs вернувшиеся")
    seg_u = seg_all[seg_all["segment"] == "user_type"]
    fig_u = px.bar(
        seg_u,
        x="value",
        y="rel_lift",
        color="significant",
        text=seg_u["rel_lift"].map(lambda x: f"{x:+.0%}"),
        labels={"rel_lift": "Относительный lift", "value": "Тип пользователя", "significant": "p_holm<0.05"},
    )
    fig_u.update_traces(textposition="outside")
    fig_u.update_layout(yaxis_tickformat=".0%", height=340, margin=dict(t=20))
    st.plotly_chart(fig_u, use_container_width=True)
    st.dataframe(_seg_table(seg_u), hide_index=True, use_container_width=True)

st.subheader("Отличаются ли эффекты между сегментами")
st.markdown(
    "«В одном сегменте значимо, в другом нет» — ещё не доказательство разницы. "
    "Проверяю саму разницу абсолютных lift'ов (interaction) z-тестом."
)
mob = df.assign(platform=df["device"].where(df["device"] == "desktop", "mobile"))
inter = pd.DataFrame(
    [
        lift_difference(mob, "platform", "desktop", "mobile"),
        lift_difference(df, "user_type", "new", "returning"),
    ]
)
st.dataframe(
    pd.DataFrame(
        {
            "сравнение": inter["a"] + " vs " + inter["b"],
            "lift A": inter["lift_a"].map(lambda x: f"{x * 100:+.2f} п.п."),
            "lift B": inter["lift_b"].map(lambda x: f"{x * 100:+.2f} п.п."),
            "разница": inter["diff"].map(lambda x: f"{x * 100:+.2f} п.п."),
            "95% CI": inter["ci"].map(lambda c: f"{c[0] * 100:+.2f}…{c[1] * 100:+.2f} п.п."),
            "p-value": inter["p_value"].map(lambda x: f"{x:.3f}"),
        }
    ),
    hide_index=True,
    use_container_width=True,
)
st.write(
    "Desktop и mobile отличаются по-настоящему. А новые и вернувшиеся получают **одинаковый** абсолютный прирост — "
    "«новым помогает сильнее» данные не подтверждают."
)

st.subheader("Guardrail по девайсам: выручка на пользователя")
rpu_d = segment_rpu(df, "device")
st.dataframe(
    pd.DataFrame(
        {
            "девайс": rpu_d["value"],
            "RPU control": rpu_d["rpu_control"].map(lambda x: f"{x:.0f} ₽"),
            "RPU treatment": rpu_d["rpu_treatment"].map(lambda x: f"{x:.0f} ₽"),
            "Δ RPU": rpu_d["rpu_diff"].map(lambda x: f"{x:+.0f} ₽"),
            "95% CI": rpu_d["rpu_ci"].map(lambda c: f"{c[0]:+.0f}…{c[1]:+.0f} ₽"),
            "p-value": rpu_d["p_value"].map(lambda x: f"{x:.3f}"),
        }
    ),
    hide_index=True,
    use_container_width=True,
)

st.subheader("Динамика: накопленный эффект по дням")
cum = cumulative_lift(df)
fig_c = go.Figure()
fig_c.add_trace(
    go.Scatter(
        x=list(cum["day"]) + list(cum["day"][::-1]),
        y=list(cum["ci_hi"]) + list(cum["ci_lo"][::-1]),
        fill="toself",
        line=dict(width=0),
        opacity=0.25,
        name="95% CI",
        hoverinfo="skip",
    )
)
fig_c.add_trace(go.Scatter(x=cum["day"], y=cum["abs_lift"], mode="lines+markers", name="Δ CR абс."))
fig_c.add_hline(y=0, line_dash="dot")
fig_c.update_layout(yaxis_tickformat=".1%", height=320, margin=dict(t=20), yaxis_title="Δ CR (накопленно)")
st.plotly_chart(fig_c, use_container_width=True)
first_sig = cum.loc[cum["p_value"] < ALPHA_UI, "day"].min()
st.write(
    "Эффект не затухает к концу теста — признаков эффекта новизны нет. "
    f"Первые дни p-value > 0.05, значимость появляется только с {first_sig:%d.%m}: "
    "если бы тест «подсмотрели» и остановили в первую неделю, фичу ошибочно признали бы бесполезной. "
    "Решение принимается один раз — на 14-й день, как планировалось."
)

ios_hi = seg_all.loc[seg_all["value"] == "ios", "ci_abs"].iloc[0][1]
desk_rpu = rpu_d.loc[rpu_d["value"] == "desktop", "rpu_diff"].iloc[0]

st.subheader("Мощность и MDE")
st.write(
    f"На текущем N ≈ {n_per:,} на ветку MDE по CR около **{detected_mde * 100:.2f} п.п.** "
    f"(80% power, α=0.05). Чтобы поймать +8% относительно базы {ov['p_control']:.1%}, "
    f"нужно примерно **{need_n:,}** пользователей на вариант — тест под такой эффект недобран, "
    "но фактический эффект оказался крупнее MDE. На iOS «нет эффекта» ≠ доказанный ноль: "
    "по доверительному интервалу можно исключить только прирост больше "
    f"≈ {ios_hi * 100:+.1f} п.п."
)

st.subheader("Вывод")
st.markdown(
    f"""
**Что сделал.** Проверил, стоит ли включать кнопку «Купить сразу» всем пользователям — провёл A/B-тест
и разложил результат по устройствам и типам пользователей.

**Что понял.** Тест прошёл честно, группы разделились ровно. В среднем конверсия выросла на **{_pct(ov["rel_lift"])}**,
но этот рост почти целиком дал **desktop** — на iOS и Android значимого эффекта нет, и разница desktop vs mobile
сама по себе значима. Новые и вернувшиеся пользователи получают одинаковый прирост. Средний чек просел на
{abs(rev["aov_rel"]):.1%}, но выручка с одного пользователя выросла (**{rev["rpu_diff"]:+.0f} ₽**, на desktop
**{desk_rpu:+.0f} ₽**), потому что покупать стали чаще.

**Что делать.** Включать кнопку на desktop уже сейчас. На iOS и Android пока не раскатывать «как есть» — сначала
доработать сохранённый способ оплаты и адрес, и только потом тестировать там заново. Итог мерить не по среднему чеку,
а по выручке на пользователя (RPU), иначе можно принять неверное решение из-за просевшего AOV.
"""
)
