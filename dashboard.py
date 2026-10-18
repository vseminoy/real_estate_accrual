"""Portfolio dashboard — minimal prototype with property/period filters.

Run: streamlit run dashboard.py
"""

import pandas as pd
import streamlit as st

from analysis.loader import load_raw
from analysis.metrics import compute_kpis
from analysis.quality import run_quality_checks

st.set_page_config(page_title="Real Estate Accrual — Portfolio", layout="wide")


@st.cache_data
def get_report():
    return run_quality_checks(load_raw())


report = get_report()

st.title("Портфель вилл — финансовая сводка (прототип)")
st.caption(
    "Owner Balance — оценочная величина (Gross Bookings − OTA Fees − Management Fee − "
    "Operating Expenses, accrual). Методология и допущения — см. README.md."
)

with st.sidebar:
    st.header("Фильтры")
    property_options = ["Все объекты"] + sorted(report.properties["property_id"].tolist())
    property_choice = st.selectbox("Объект", property_options)
    property_id = None if property_choice == "Все объекты" else property_choice

    min_date = report.reservations["check_in"].min().date()
    max_date = report.reservations["check_in"].max().date()
    period = st.date_input("Период (по check_in)", value=(min_date, max_date),
                            min_value=min_date, max_value=max_date)
    start, end = (period if isinstance(period, tuple) and len(period) == 2 else (min_date, max_date))

kpis = compute_kpis(report, property_id=property_id, start=start, end=end)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Gross Bookings", f"{kpis['gross_bookings']:,.0f}")
col2.metric("OTA Fees", f"{kpis['ota_fees']:,.0f}")
col3.metric("Management Fee", f"{kpis['management_fee']:,.0f}")
col4.metric("Owner Balance (est.)", f"{kpis['owner_balance_estimate']:,.0f}")

col5, col6, col7, col8 = st.columns(4)
col5.metric("Operating Expenses (accrual)", f"{kpis['operating_expenses_accrual']:,.0f}",
            help=f"Из них оплачено: {kpis['operating_expenses_paid']:,.0f}")
col6.metric("Accrual revenue", f"{kpis['accrual_revenue']:,.0f}",
            help="Gross Bookings − OTA Fees − Management Fee. Operating Expenses сюда не входят — "
                 "это выручка, а не Owner Balance. Период — по check_in.")
col7.metric("Cash In (получено)", f"{kpis['cash_in']:,.0f}",
            help="Фильтр «Период» применяется и здесь, но по дате платежа (payment_date), "
                 "а не по check_in, как для остальных метрик — поэтому Cash In может включать "
                 "или не включать платёж за бронирование, которое в период попадает.")
col8.metric("Accrual revenue − Cash In", f"{kpis['accrual_revenue_minus_cash_in']:,.0f}",
            help="Положительное значение — выручка начислена, но деньги ещё не поступили.")

st.divider()
st.subheader("По объектам")
rows = []
for pid in sorted(report.properties["property_id"]):
    k = compute_kpis(report, property_id=pid, start=start, end=end)
    k["property_id"] = pid
    rows.append(k)
by_property = pd.DataFrame(rows).set_index("property_id")
st.dataframe(
    by_property[["gross_bookings", "ota_fees", "management_fee",
                  "operating_expenses_accrual", "cash_in", "owner_balance_estimate"]]
    .style.format("{:,.0f}"),
    use_container_width=True,
)
st.bar_chart(by_property["owner_balance_estimate"])

st.divider()
st.subheader("Качество данных")
st.caption(
    "«excluded» — строка не входит в расчёты выше; «requires_review» — строка учтена, "
    "но значение нужно подтвердить. Подробности и причины — в README.md."
)
summary = (
    report.exceptions.groupby(["entity", "rule", "severity"]).size().rename("count").reset_index()
    if not report.exceptions.empty else pd.DataFrame(columns=["entity", "rule", "severity", "count"])
)
st.dataframe(summary, use_container_width=True)
st.caption(
    "Эта таблица и полный список ниже не зависят от фильтров «Объект»/«Период» выше: "
    "это сквозной отчёт по всем исходным CSV, а не по текущему срезу дашборда."
)
with st.expander("Полный список записей, отправленных на проверку или исключённых"):
    entity_options = ["Все"] + sorted(report.exceptions["entity"].unique().tolist())
    entity_choice = st.radio("Сущность", entity_options, horizontal=True)
    shown = report.exceptions if entity_choice == "Все" else report.exceptions[report.exceptions["entity"] == entity_choice]
    st.dataframe(
        shown.sort_values(["entity", "severity", "rule"]).reset_index(drop=True),
        use_container_width=True,
        height=min(35 * (len(shown) + 1) + 3, 600),
    )
