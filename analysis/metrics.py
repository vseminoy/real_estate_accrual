"""Financial metrics computed on top of the cleaned frames from quality.py.

Accrual and cash are never mixed into one number: every function below is
either one or the other, and `compute_kpis` keeps them as separate fields.

- Accrual basis (Gross Bookings, OTA Fees, Management Fee, Operating Expenses
  accrued): recognised on `check_in` for a stay and `expense_date` for a cost,
  regardless of whether money has moved yet.
- Cash basis (Cash In, Operating Expenses paid): recognised on the date money
  actually moved (`payment_date`), status-filtered (`received` / `paid`).

A cancelled reservation with a full refund contributes zero to Gross Bookings
— the stay was never delivered, so there is no revenue to recognise. This is
an accounting rule, not a data-quality exclusion, so it is applied here and
not in quality.py.
"""

from datetime import date

import pandas as pd

from analysis.quality import QualityReport

ACTIVE_STATUSES = ("confirmed", "modified")


def _in_period(series: pd.Series, start: date | None, end: date | None) -> pd.Series:
    mask = pd.Series(True, index=series.index)
    if start is not None:
        mask &= series >= pd.Timestamp(start)
    if end is not None:
        mask &= series <= pd.Timestamp(end)
    return mask


def _active_reservations(report: QualityReport, property_id: str | None,
                          start: date | None, end: date | None) -> pd.DataFrame:
    df = report.reservations[report.reservations["status"].isin(ACTIVE_STATUSES)]
    if property_id:
        df = df[df["property_id"] == property_id]
    return df[_in_period(df["check_in"], start, end)]


def gross_bookings(report: QualityReport, property_id: str | None = None,
                    start: date | None = None, end: date | None = None) -> float:
    return float(_active_reservations(report, property_id, start, end)["gross_booking_value"].sum())


def ota_fees(report: QualityReport, property_id: str | None = None,
             start: date | None = None, end: date | None = None) -> float:
    df = _active_reservations(report, property_id, start, end)
    return float(df.loc[df["ota_fee"] >= 0, "ota_fee"].sum())


def _rate_for(commission_rules: pd.DataFrame, property_id: str, on_date: pd.Timestamp) -> float:
    rules = commission_rules[
        (commission_rules["property_id"] == property_id)
        & (commission_rules["effective_from"] <= on_date)
        & (commission_rules["effective_to"] >= on_date)
    ]
    if rules.empty:
        return 0.0
    return float(rules.iloc[0]["management_fee_rate"])


def management_fee(report: QualityReport, property_id: str | None = None,
                    start: date | None = None, end: date | None = None) -> float:
    df = _active_reservations(report, property_id, start, end)
    if df.empty:
        return 0.0
    rates = df.apply(lambda r: _rate_for(report.commission_rules, r["property_id"], r["check_in"]), axis=1)
    return float((df["gross_booking_value"] * rates).sum())


def operating_expenses(report: QualityReport, basis: str, property_id: str | None = None,
                        start: date | None = None, end: date | None = None) -> float:
    """basis: 'accrual' (every clean expense) or 'paid' (payment_status == 'paid')."""
    df = report.expenses
    if basis == "paid":
        df = df[df["payment_status"] == "paid"]
    elif basis != "accrual":
        raise ValueError("basis must be 'accrual' or 'paid'")
    if property_id:
        df = df[df["property_id"] == property_id]
    return float(df.loc[_in_period(df["expense_date"], start, end), "amount"].sum())


def cash_in(report: QualityReport, property_id: str | None = None,
            start: date | None = None, end: date | None = None) -> float:
    df = report.payments
    if property_id:
        df = df[df["property_id"] == property_id]
    return float(df.loc[_in_period(df["payment_date"], start, end), "amount"].sum())


def compute_kpis(report: QualityReport, property_id: str | None = None,
                  start: date | None = None, end: date | None = None) -> dict:
    gb = gross_bookings(report, property_id, start, end)
    fees = ota_fees(report, property_id, start, end)
    mgmt = management_fee(report, property_id, start, end)
    opex_accrual = operating_expenses(report, "accrual", property_id, start, end)
    opex_paid = operating_expenses(report, "paid", property_id, start, end)
    cash = cash_in(report, property_id, start, end)

    accrual_revenue = gb - fees - mgmt
    owner_balance = accrual_revenue - opex_accrual

    return {
        "gross_bookings": gb,
        "ota_fees": fees,
        "management_fee": mgmt,
        "operating_expenses_accrual": opex_accrual,
        "operating_expenses_paid": opex_paid,
        "cash_in": cash,
        "accrual_revenue": accrual_revenue,
        "owner_balance_estimate": owner_balance,
        "accrual_revenue_minus_cash_in": accrual_revenue - cash,
        "opex_accrual_minus_paid": opex_accrual - opex_paid,
    }
