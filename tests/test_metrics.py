import pandas as pd

from analysis.metrics import compute_kpis
from analysis.quality import QualityReport


def _report():
    properties = pd.DataFrame([
        {"property_id": "V001", "property_name": "Villa 1", "cluster": "Ubud",
         "owner_id": "O001", "base_currency": "IDR"},
    ])
    reservations = pd.DataFrame([
        {"reservation_id": "R1", "property_id": "V001", "check_in": "2026-09-01", "check_out": "2026-09-03",
         "status": "confirmed", "gross_booking_value": 1000.0, "currency": "IDR", "ota_fee": 100.0,
         "refund_amount": 0.0, "channel": "OTA", "updated_at": "2026-09-01"},
        {"reservation_id": "R2", "property_id": "V001", "check_in": "2026-09-10", "check_out": "2026-09-12",
         "status": "cancelled", "gross_booking_value": 500.0, "currency": "IDR", "ota_fee": 50.0,
         "refund_amount": 500.0, "channel": "OTA", "updated_at": "2026-09-01"},
    ])
    for col in ("check_in", "check_out", "updated_at"):
        reservations[col] = pd.to_datetime(reservations[col])

    expenses = pd.DataFrame([
        {"expense_id": "E1", "property_id": "V001", "expense_date": "2026-09-01",
         "category": "Cleaning", "amount": 80.0, "currency": "IDR", "payment_status": "paid"},
        {"expense_id": "E2", "property_id": "V001", "expense_date": "2026-09-02",
         "category": "Supplies", "amount": 20.0, "currency": "IDR", "payment_status": "pending"},
    ])
    expenses["expense_date"] = pd.to_datetime(expenses["expense_date"])

    payments = pd.DataFrame([
        {"payment_id": "P1", "reservation_id": "R1", "property_id": "V001",
         "payment_date": "2026-09-02", "amount": 900.0, "currency": "IDR", "status": "received"},
    ])
    payments["payment_date"] = pd.to_datetime(payments["payment_date"])

    commission_rules = pd.DataFrame([
        {"property_id": "V001", "effective_from": "2026-09-01", "effective_to": "2026-12-31",
         "management_fee_rate": 0.17, "fee_basis": "gross_booking_value", "note": ""},
    ])
    for col in ("effective_from", "effective_to"):
        commission_rules[col] = pd.to_datetime(commission_rules[col])

    return QualityReport(properties, reservations, expenses, payments, commission_rules)


def test_cancelled_reservation_contributes_nothing_to_gross_bookings():
    kpis = compute_kpis(_report())
    assert kpis["gross_bookings"] == 1000.0
    assert kpis["ota_fees"] == 100.0


def test_management_fee_uses_the_property_rate():
    kpis = compute_kpis(_report())
    assert kpis["management_fee"] == 1000.0 * 0.17


def test_opex_accrual_includes_pending_but_paid_does_not():
    kpis = compute_kpis(_report())
    assert kpis["operating_expenses_accrual"] == 100.0
    assert kpis["operating_expenses_paid"] == 80.0
    assert kpis["opex_accrual_minus_paid"] == 20.0


def test_owner_balance_and_accrual_vs_cash():
    kpis = compute_kpis(_report())
    gb, fees, mgmt, opex = 1000.0, 100.0, 170.0, 100.0
    assert kpis["owner_balance_estimate"] == gb - fees - mgmt - opex
    assert kpis["cash_in"] == 900.0
    assert kpis["accrual_revenue_minus_cash_in"] == (gb - fees - mgmt) - 900.0
