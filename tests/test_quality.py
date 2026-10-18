import pandas as pd

from analysis.quality import run_quality_checks


def _raw():
    properties = pd.DataFrame([
        {"property_id": "V001", "property_name": "Villa 1", "cluster": "Ubud",
         "owner_id": "O001", "base_currency": "IDR"},
    ])
    reservations = pd.DataFrame([
        {"reservation_id": "R1", "property_id": "V001", "check_in": "2026-09-01", "check_out": "2026-09-03",
         "status": "confirmed", "gross_booking_value": 1000, "currency": "IDR", "ota_fee": 100,
         "refund_amount": 0, "channel": "OTA", "updated_at": "2026-09-01"},
        {"reservation_id": "R1", "property_id": "V001", "check_in": "2026-09-01", "check_out": "2026-09-03",
         "status": "confirmed", "gross_booking_value": 1000, "currency": "IDR", "ota_fee": 100,
         "refund_amount": 0, "channel": "OTA", "updated_at": "2026-09-01"},
        {"reservation_id": "R2", "property_id": "V999", "check_in": "2026-09-05", "check_out": "2026-09-06",
         "status": "confirmed", "gross_booking_value": 500, "currency": "IDR", "ota_fee": 50,
         "refund_amount": 0, "channel": "OTA", "updated_at": "2026-09-01"},
        {"reservation_id": "R3", "property_id": "V001", "check_in": "2026-09-10", "check_out": "2026-09-12",
         "status": "confirmed", "gross_booking_value": 2000, "currency": "USD", "ota_fee": 100,
         "refund_amount": 0, "channel": "OTA", "updated_at": "2026-09-01"},
        {"reservation_id": "R4", "property_id": "V001", "check_in": "2026-09-15", "check_out": "2026-09-16",
         "status": "confirmed", "gross_booking_value": 300, "currency": "IDR", "ota_fee": 10,
         "refund_amount": 500, "channel": "OTA", "updated_at": "2026-09-01"},
        {"reservation_id": "R5", "property_id": "V001", "check_in": "2026-09-20", "check_out": "2026-09-22",
         "status": "confirmed", "gross_booking_value": 400, "currency": "IDR", "ota_fee": -50,
         "refund_amount": 0, "channel": "OTA", "updated_at": "2026-09-01"},
    ])
    for col in ("check_in", "check_out", "updated_at"):
        reservations[col] = pd.to_datetime(reservations[col])

    expenses = pd.DataFrame([
        {"expense_id": "E1", "property_id": "V001", "expense_date": "2026-09-01",
         "category": "Cleaning", "amount": 100, "currency": "IDR", "payment_status": "paid"},
        {"expense_id": "E2", "property_id": "V777", "expense_date": "2026-09-01",
         "category": "Cleaning", "amount": 50, "currency": "IDR", "payment_status": "paid"},
    ])
    expenses["expense_date"] = pd.to_datetime(expenses["expense_date"])

    payments = pd.DataFrame([
        {"payment_id": "P1", "reservation_id": "R1", "property_id": "V001",
         "payment_date": "2026-09-02", "amount": 900, "currency": "IDR", "status": "received"},
        {"payment_id": "P2", "reservation_id": "R1", "property_id": "V001",
         "payment_date": "2026-09-02", "amount": 0, "currency": "IDR", "status": "received"},
    ])
    payments["payment_date"] = pd.to_datetime(payments["payment_date"])

    commission_rules = pd.DataFrame([
        {"property_id": "V001", "effective_from": "2026-09-01", "effective_to": "2026-12-31",
         "management_fee_rate": 0.17, "fee_basis": "gross_booking_value", "note": ""},
    ])
    for col in ("effective_from", "effective_to"):
        commission_rules[col] = pd.to_datetime(commission_rules[col])

    return {
        "properties": properties,
        "reservations": reservations,
        "expenses": expenses,
        "payments": payments,
        "commission_rules": commission_rules,
    }


def test_duplicate_reservation_row_is_excluded():
    report = run_quality_checks(_raw())
    assert (report.reservations["reservation_id"] == "R1").sum() == 1
    rule = report.exceptions[(report.exceptions["id"] == "R1") & (report.exceptions["rule"] == "duplicate_row")]
    assert rule.iloc[0]["severity"] == "excluded"


def test_unknown_property_is_excluded_from_reservations_and_expenses():
    report = run_quality_checks(_raw())
    assert "R2" not in set(report.reservations["reservation_id"])
    assert "E2" not in set(report.expenses["expense_id"])


def test_currency_mismatch_without_fx_is_excluded():
    report = run_quality_checks(_raw())
    assert "R3" not in set(report.reservations["reservation_id"])


def test_refund_exceeding_gross_is_excluded():
    report = run_quality_checks(_raw())
    assert "R4" not in set(report.reservations["reservation_id"])


def test_negative_ota_fee_is_flagged_but_row_kept():
    report = run_quality_checks(_raw())
    assert "R5" in set(report.reservations["reservation_id"])
    rule = report.exceptions[(report.exceptions["id"] == "R5") & (report.exceptions["rule"] == "negative_ota_fee")]
    assert rule.iloc[0]["severity"] == "requires_review"


def test_non_positive_payment_is_excluded():
    report = run_quality_checks(_raw())
    assert "P2" not in set(report.payments["payment_id"])
