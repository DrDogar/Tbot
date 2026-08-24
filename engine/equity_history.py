import csv

_FIELDNAMES = ["timestamp", "cycle", "cash", "market_value", "equity", "realized_pnl", "fees_paid", "pnl_pct"]


def append_equity_snapshot(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not path.exists()

    with open(path, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=_FIELDNAMES)

        if is_new_file:
            writer.writeheader()

        writer.writerow(row)


def load_equity_history(path):
    if not path.exists():
        return []

    with open(path, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))
