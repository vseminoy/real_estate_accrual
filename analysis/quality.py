"""Data-quality checks over the raw CSVs.

Every row removed from a "clean" frame, or flagged without being removed, is
recorded in the `exceptions` frame with a `rule` name and a `severity`:

- "excluded"        — the row is dropped from every metric; the reason makes the
                       row's own numbers unusable (duplicate, orphan reference,
                       an impossible value).
- "requires_review" — the row (or one field of it) stays in the metrics, because
                       dropping it would distort an otherwise-usable booking, but
                       a human has to confirm it before the number is trusted.

Nothing here is "fixed" by guessing a corrected value — see README.md,
"Качество данных", for the full list and the reasoning behind each rule.
"""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class QualityReport:
    properties: pd.DataFrame
    reservations: pd.DataFrame
    expenses: pd.DataFrame
    payments: pd.DataFrame
    commission_rules: pd.DataFrame
    exceptions: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        columns=["entity", "id", "rule", "severity", "detail"]
    ))


def _add(exceptions: list[dict], entity: str, id_: str, rule: str, severity: str, detail: str) -> None:
    exceptions.append({"entity": entity, "id": id_, "rule": rule, "severity": severity, "detail": detail})


def _clean_reservations(reservations: pd.DataFrame, known_properties: set[str],
                         base_currency_by_property: dict[str, str],
                         exceptions: list[dict]) -> pd.DataFrame:
    df = reservations.copy()

    dup_mask = df.duplicated(keep="first")
    for rid in df.loc[dup_mask, "reservation_id"]:
        _add(exceptions, "reservation", rid, "duplicate_row", "excluded",
             "Строка полностью повторяет уже учтённую запись; оставлена первая.")
    df = df.loc[~dup_mask]

    unknown_prop = ~df["property_id"].isin(known_properties)
    for _, row in df.loc[unknown_prop].iterrows():
        _add(exceptions, "reservation", row["reservation_id"], "unknown_property", "excluded",
             f"property_id={row['property_id']} отсутствует в properties.csv.")
    df = df.loc[~unknown_prop]

    expected_currency = df["property_id"].map(base_currency_by_property)
    currency_mismatch = df["currency"] != expected_currency
    for _, row in df.loc[currency_mismatch].iterrows():
        _add(exceptions, "reservation", row["reservation_id"], "currency_mismatch_no_fx", "excluded",
             f"Валюта {row['currency']} отличается от базовой валюты объекта "
             f"({expected_currency[row.name]}); курс и дата курса не подтверждены.")
    df = df.loc[~currency_mismatch]

    refund_exceeds_gross = df["refund_amount"] > df["gross_booking_value"]
    for _, row in df.loc[refund_exceeds_gross].iterrows():
        _add(exceptions, "reservation", row["reservation_id"], "refund_exceeds_gross", "excluded",
             f"refund_amount={row['refund_amount']:.0f} > gross_booking_value={row['gross_booking_value']:.0f}.")
    df = df.loc[~refund_exceeds_gross]

    negative_fee = df["ota_fee"] < 0
    for _, row in df.loc[negative_fee].iterrows():
        _add(exceptions, "reservation", row["reservation_id"], "negative_ota_fee", "requires_review",
             f"ota_fee={row['ota_fee']:.0f} < 0; исключена из OTA Fees, gross_booking_value сохранён.")

    direct_with_fee = (df["channel"] == "Direct") & (df["ota_fee"] > 0)
    for _, row in df.loc[direct_with_fee].iterrows():
        _add(exceptions, "reservation", row["reservation_id"], "direct_channel_with_fee", "requires_review",
             "Канал Direct обычно не несёт OTA-комиссию; строка сохранена, вопрос — в README.")

    active = df[df["status"].isin(["confirmed", "modified"])].sort_values("check_in")
    for property_id, group in active.groupby("property_id"):
        intervals = list(group[["check_in", "check_out", "reservation_id"]].itertuples(index=False))
        for i in range(len(intervals)):
            ci1, co1, id1 = intervals[i]
            for j in range(i + 1, len(intervals)):
                ci2, co2, id2 = intervals[j]
                if ci2 < co1 and ci1 < co2:
                    _add(exceptions, "reservation", id1, "overlapping_stay", "requires_review",
                         f"Пересекается с {id2} по объекту {property_id}; обе записи сохранены в расчётах.")

    return df


def _clean_expenses(expenses: pd.DataFrame, known_properties: set[str],
                     exceptions: list[dict]) -> pd.DataFrame:
    df = expenses.copy()

    dup_mask = df.duplicated(keep="first")
    for eid in df.loc[dup_mask, "expense_id"]:
        _add(exceptions, "expense", eid, "duplicate_row", "excluded",
             "Строка полностью повторяет уже учтённую запись; оставлена первая.")
    df = df.loc[~dup_mask]

    unknown_prop = ~df["property_id"].isin(known_properties)
    for _, row in df.loc[unknown_prop].iterrows():
        _add(exceptions, "expense", row["expense_id"], "unknown_property", "excluded",
             f"property_id={row['property_id']} отсутствует в properties.csv.")
    df = df.loc[~unknown_prop]

    non_positive = df["amount"] <= 0
    for _, row in df.loc[non_positive].iterrows():
        _add(exceptions, "expense", row["expense_id"], "non_positive_amount", "excluded",
             f"amount={row['amount']:.0f} <= 0.")
    df = df.loc[~non_positive]

    return df


def _clean_payments(payments: pd.DataFrame, known_reservations: set[str],
                     exceptions: list[dict]) -> pd.DataFrame:
    df = payments.copy()

    dup_mask = df.duplicated(keep="first")
    for pid in df.loc[dup_mask, "payment_id"]:
        _add(exceptions, "payment", pid, "duplicate_row", "excluded",
             "Строка полностью повторяет уже учтённую запись; оставлена первая.")
    df = df.loc[~dup_mask]

    unknown_res = ~df["reservation_id"].isin(known_reservations)
    for _, row in df.loc[unknown_res].iterrows():
        _add(exceptions, "payment", row["payment_id"], "unknown_reservation", "excluded",
             f"reservation_id={row['reservation_id']} отсутствует в reservations.csv.")
    df = df.loc[~unknown_res]

    non_positive = df["amount"] <= 0
    for _, row in df.loc[non_positive].iterrows():
        _add(exceptions, "payment", row["payment_id"], "non_positive_amount", "excluded",
             f"amount={row['amount']:.0f}; платёж со статусом 'received' не может быть нулевым.")
    df = df.loc[~non_positive]

    return df


def run_quality_checks(raw: dict[str, pd.DataFrame]) -> QualityReport:
    properties = raw["properties"]
    known_properties = set(properties["property_id"])
    base_currency_by_property = dict(zip(properties["property_id"], properties["base_currency"]))

    exceptions: list[dict] = []

    reservations = _clean_reservations(
        raw["reservations"], known_properties, base_currency_by_property, exceptions
    )
    expenses = _clean_expenses(raw["expenses"], known_properties, exceptions)
    payments = _clean_payments(raw["payments"], set(reservations["reservation_id"]), exceptions)

    return QualityReport(
        properties=properties,
        reservations=reservations,
        expenses=expenses,
        payments=payments,
        commission_rules=raw["commission_rules"],
        exceptions=pd.DataFrame(exceptions, columns=["entity", "id", "rule", "severity", "detail"]),
    )
