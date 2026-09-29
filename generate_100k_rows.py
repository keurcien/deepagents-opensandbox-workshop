"""Generate big_sheet.csv with 100 000 rows to import into Google Sheets (page 5)."""

import csv
import random
from datetime import date, timedelta

ROWS = 100_000
random.seed(42)

cities = ["Paris", "Lyon", "Marseille", "Toulouse", "Nantes", "Bordeaux", "Lille", "Nice"]
products = ["laptop", "phone", "headphones", "monitor", "keyboard", "mouse", "webcam"]
start = date(2025, 1, 1)

with open("big_sheet.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "date", "city", "product", "amount"])
    for i in range(1, ROWS + 1):
        writer.writerow(
            [
                i,
                (start + timedelta(days=random.randint(0, 364))).isoformat(),
                random.choice(cities),
                random.choice(products),
                round(random.uniform(5, 2000), 2),
            ]
        )

print(f"Wrote big_sheet.csv with {ROWS:,} rows")
