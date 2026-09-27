"""A stand-in for a model that extracts invoices from documents.

Given a document it returns JSON text, deterministically for a given (seed, document,
attempt), with the mistakes real models make: a total that does not add up, a date in
the wrong format, prose around the JSON, a missing field, a negative number. Given
the validation errors from its last attempt, it fixes what was reported nine times in
ten.
"""

import json
import random
from datetime import date
from decimal import Decimal

MISTAKES = ["total off", "date format", "prose around json", "no lines", "negative quantity", "lowercase currency"]
FIRST_TRY = {"total off": 0.12, "date format": 0.08, "prose around json": 0.08, "no lines": 0.04, "negative quantity": 0.03, "lowercase currency": 0.05}
FIX_RATE = 0.9


def make_document(i: int) -> dict:
    """The true invoice the model is supposed to read; the demo generates 200 of them."""
    rng = random.Random(f"doc:{i}")
    lines = [
        {"description": rng.choice(["consulting", "hosting", "support", "licence", "training"]), "quantity": rng.randint(1, 6), "unit_price": f"{rng.randint(20, 900)}.{rng.randint(0, 99):02d}"}
        for _ in range(rng.randint(1, 4))
    ]
    total = sum(Decimal(line["unit_price"]) * line["quantity"] for line in lines)
    return {
        "invoice_number": f"INV-{1000 + i}",
        "issued": date(2026, rng.randint(1, 9), rng.randint(1, 28)).isoformat(),
        "currency": rng.choice(["EUR", "USD", "GBP"]),
        "lines": lines,
        "total": f"{total:.2f}",
    }


class ScriptedExtractor:
    def __init__(self, seed: int = 0):
        self.seed = seed

    def extract(self, document: dict, feedback: list[str] | None, attempt: int) -> str:
        rng = random.Random(f"{self.seed}:{document['invoice_number']}:{attempt}")
        mistake = None
        if feedback is None:  # first try: a mistake with the usual rates
            roll = rng.random()
            for name, rate in FIRST_TRY.items():
                roll -= rate
                if roll < 0:
                    mistake = name
                    break
        elif rng.random() >= FIX_RATE:  # a retry that did not take the feedback
            mistake = rng.choice(MISTAKES)
        return self.render(document, mistake, rng)

    @staticmethod
    def render(document: dict, mistake: str | None, rng: random.Random) -> str:
        data = json.loads(json.dumps(document))  # a deep copy
        if mistake == "total off":
            data["total"] = f"{Decimal(data['total']) + Decimal(rng.randint(1, 50)):.2f}"
        elif mistake == "date format":
            y, m, d = data["issued"].split("-")
            data["issued"] = f"{d}/{m}/{y}"
        elif mistake == "no lines":
            data["lines"] = []
        elif mistake == "negative quantity":
            data["lines"][0]["quantity"] = -data["lines"][0]["quantity"]
        elif mistake == "lowercase currency":
            data["currency"] = data["currency"].lower()
        text = json.dumps(data)
        if mistake == "prose around json":
            text = f"Here is the extracted invoice:\n{text}\nLet me know if you need anything else."
        return text
