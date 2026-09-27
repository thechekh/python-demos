"""Pydantic v2 as the contract between code and model.

Article: https://chekh.dev/writing/pydantic-v2-as-the-contract-between-code-and-model/
Run:     uv run python contracts_demo.py                 (a few seconds)
         uv run python contracts_demo.py --charts-only   (redraw from results/)
         uv run pytest tests/test_contracts.py

Two hundred documents through a scripted extractor: parse each answer against the
Invoice contract, and when it fails, send the validation errors back and try again,
up to three times. Counts what went wrong and how many tries each document needed.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from pydantic import ValidationError

from _common import ACCENT, DANGER, INK, INK_2, MUTED, save
from contracts_model import ScriptedExtractor, make_document
from contracts_models import Invoice

SLUG = "pydantic-v2-as-the-contract-between-code-and-model"
DOCUMENTS, MAX_ATTEMPTS = 200, 3


def extract(document: dict, model: ScriptedExtractor, max_attempts: int = MAX_ATTEMPTS):
    """Ask, validate, and on failure ask again with the errors as feedback."""
    feedback = None
    history = []
    for attempt in range(1, max_attempts + 1):
        text = model.extract(document, feedback, attempt)
        try:
            return Invoice.model_validate_json(text), attempt, history
        except ValidationError as e:
            feedback = [f"{'.'.join(str(p) for p in err['loc']) or 'invoice'}: {err['msg']}" for err in e.errors()]
            history.append([err["type"] for err in e.errors()])
    return None, max_attempts, history


def compute() -> dict:
    model = ScriptedExtractor(seed=0)
    attempts_needed = Counter()
    first_errors = Counter()
    failed = 0
    for i in range(DOCUMENTS):
        invoice, attempt, history = extract(make_document(i), model)
        if invoice is None:
            failed += 1
        else:
            attempts_needed[attempt] += 1
        if history:
            first_errors[", ".join(sorted(set(history[0])))] += 1
    success_by_budget = {k: sum(v for a, v in attempts_needed.items() if a <= k) / DOCUMENTS for k in range(1, MAX_ATTEMPTS + 1)}
    # First answers with a lowercase currency: the contract normalises them instead of rejecting.
    normalised = 0
    for i in range(DOCUMENTS):
        try:
            normalised += json.loads(model.extract(make_document(i), None, 1))["currency"].islower()
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass
    print(f"{DOCUMENTS} documents, up to {MAX_ATTEMPTS} attempts each")
    for k, share in success_by_budget.items():
        print(f"  valid within {k} attempt{'s' if k > 1 else ''}: {share:.1%}")
    print(f"  gave up: {failed}")
    print(f"  first answers with a lowercase currency, normalised rather than rejected: {normalised}")
    print("first-attempt validation errors:")
    for kind, n in first_errors.most_common():
        print(f"  {n:3d}  {kind}")
    schema = Invoice.model_json_schema()
    return {
        "documents": DOCUMENTS, "max_attempts": MAX_ATTEMPTS,
        "attempts_needed": {str(k): v for k, v in sorted(attempts_needed.items())}, "failed": failed,
        "success_by_budget": success_by_budget, "first_errors": dict(first_errors.most_common()),
        "normalised_currency": normalised, "schema": schema,
    }


ERROR_LABELS = {
    "value_error": "total does not add up (model_validator)",
    "json_invalid": "prose around the JSON",
    "date_from_datetime_parsing": "date in the wrong format",
    "too_short": "no lines at all",
    "greater_than_equal": "negative quantity",
}


def draw_contract() -> None:
    fig, ax = plt.subplots(figsize=(7.6, 2.9))
    ax.set_xlim(0, 7.6)
    ax.set_ylim(0, 2.9)
    ax.axis("off")

    def box(x, y, w, h, title, body, strong=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.02", facecolor="#faf9f6", edgecolor=ACCENT if strong else MUTED, linewidth=1.4 if strong else 1))
        ax.text(x + w / 2, y + h - 0.08, title, ha="center", va="top", fontsize=8.8 if len(title) > 12 else 9.5, color=INK, fontweight="semibold")
        ax.text(x + w / 2, y + 0.08, body, ha="center", va="bottom", fontsize=7.8, color=INK_2, linespacing=1.3)

    box(0.2, 1.5, 1.6, 1.0, "model", "reads the document,\nwrites JSON text")
    box(2.6, 1.5, 2.5, 1.0, "Invoice.model_validate_json", "parses, checks types,\nranges, the total", strong=True)
    box(5.9, 1.5, 1.5, 1.0, "your code", "an Invoice object:\ntyped, checked")
    ax.add_patch(FancyArrowPatch((1.8, 2.0), (2.6, 2.0), arrowstyle="-|>", mutation_scale=10, color=INK_2, linewidth=1))
    ax.text(2.2, 2.09, "JSON text", ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.add_patch(FancyArrowPatch((5.1, 2.0), (5.9, 2.0), arrowstyle="-|>", mutation_scale=10, color=ACCENT, linewidth=1.2))
    ax.text(5.5, 2.09, "valid", ha="center", va="bottom", fontsize=8, color=ACCENT)
    ax.add_patch(FancyArrowPatch((3.85, 1.5), (1.0, 1.5), arrowstyle="-|>", mutation_scale=10, color=DANGER, linewidth=1.2, connectionstyle="arc3,rad=0.55"))
    ax.text(2.45, 0.3, "ValidationError: the exact fields and reasons,\nsent back as the next prompt — up to three times", ha="center", va="center", fontsize=8, color=DANGER, linespacing=1.3)
    ax.text(3.85, 2.75, "the contract, one Python class, also gives the model its JSON Schema", ha="center", va="center", fontsize=8.5, color=INK_2)
    save(fig, SLUG, "contract")


def draw_attempts(results: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    labels = [f"valid on try {k}" for k in results["attempts_needed"]] + ["still invalid after 3"]
    values = list(results["attempts_needed"].values()) + [results["failed"]]
    colors = [ACCENT] + [INK_2] * (len(values) - 2) + [DANGER]
    for i, (label, value) in enumerate(zip(labels, values)):
        ax.barh(i, value, height=0.55, color=colors[i])
        ax.annotate(f"{value} ({value / results['documents']:.0%})", (value, i), xytext=(5, 0), textcoords="offset points", va="center", fontsize=9.5, color=INK)
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, results["documents"] * 1.15)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel(f"documents, of {results['documents']}")
    ax.set_title("How many tries each document took", fontsize=10.5)
    save(fig, SLUG, "attempts")


def draw_errors(results: dict) -> None:
    errors = results["first_errors"]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for i, (kind, n) in enumerate(errors.items()):
        ax.barh(i, n, height=0.55, color=INK_2)
        ax.annotate(str(n), (n, i), xytext=(5, 0), textcoords="offset points", va="center", fontsize=9.5, color=INK)
    ax.set_yticks(range(len(errors)), [ERROR_LABELS.get(kind, kind) for kind in errors], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, max(errors.values()) * 1.2)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel("documents whose first answer failed with this error type")
    ax.set_title("What the contract caught on the first try", fontsize=10.5)
    fig.subplots_adjust(left=0.3)
    save(fig, SLUG, "errors")


if __name__ == "__main__":
    path = Path(__file__).parent / "results" / f"{SLUG}.json"
    if "--charts-only" in sys.argv:
        results = json.loads(path.read_text())
    else:
        results = compute()
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(results, indent=2, default=str))
        print(f"  wrote {path.name}")
    draw_contract()
    draw_attempts(results)
    draw_errors(results)
