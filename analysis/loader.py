"""Loads the raw CSVs from data/ into typed DataFrames. No cleaning here —
see quality.py for anomaly detection and exclusion."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name, encoding="utf-8-sig")


def load_raw() -> dict[str, pd.DataFrame]:
    properties = _read("properties.csv")
    reservations = _read("reservations.csv")
    expenses = _read("expenses.csv")
    payments = _read("payments.csv")
    commission_rules = _read("commission_rules.csv")

    for col in ("check_in", "check_out", "updated_at"):
        reservations[col] = pd.to_datetime(reservations[col])
    expenses["expense_date"] = pd.to_datetime(expenses["expense_date"])
    payments["payment_date"] = pd.to_datetime(payments["payment_date"])
    for col in ("effective_from", "effective_to"):
        commission_rules[col] = pd.to_datetime(commission_rules[col])

    return {
        "properties": properties,
        "reservations": reservations,
        "expenses": expenses,
        "payments": payments,
        "commission_rules": commission_rules,
    }
