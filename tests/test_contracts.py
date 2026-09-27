"""The contract accepts what it should, rejects what it should with a usable message,
normalises what it can, and the retry loop uses the errors."""

import random
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contracts_demo import extract
from contracts_model import ScriptedExtractor, make_document
from contracts_models import Invoice, InvoiceV2, upgrade

GOOD = {
    "invoice_number": "INV-2026",
    "issued": "2026-03-12",
    "currency": "EUR",
    "lines": [{"description": "hosting", "quantity": 2, "unit_price": "40.00"}],
    "total": "80.00",
}


def test_a_valid_invoice_parses_to_typed_fields():
    invoice = Invoice.model_validate(GOOD)
    assert invoice.issued.year == 2026 and invoice.total == Decimal("80.00")
    assert invoice.lines[0].amount == Decimal("80.00")


def test_lowercase_currency_is_normalised_not_rejected():
    assert Invoice.model_validate({**GOOD, "currency": "eur"}).currency == "EUR"


def test_a_total_that_does_not_add_up_is_rejected_with_the_reason():
    with pytest.raises(ValidationError) as caught:
        Invoice.model_validate({**GOOD, "total": "90.00"})
    assert "does not equal the sum of the lines" in str(caught.value)


@pytest.mark.parametrize("field, bad", [("issued", "12/03/2026"), ("invoice_number", "2026"), ("currency", "CHF"), ("lines", [])])
def test_the_wrong_shape_is_rejected(field, bad):
    with pytest.raises(ValidationError):
        Invoice.model_validate({**GOOD, field: bad})


def test_prose_around_the_json_is_rejected():
    with pytest.raises(ValidationError):
        Invoice.model_validate_json('Here you go: {"invoice_number": "INV-2026"}')


def test_the_schema_names_every_field_and_the_required_ones():
    schema = Invoice.model_json_schema()
    assert set(schema["required"]) == {"invoice_number", "issued", "currency", "lines", "total"}
    assert schema["properties"]["currency"]["enum"] == ["EUR", "USD", "GBP"]


def test_version_two_accepts_a_version_one_invoice():
    v2 = upgrade(Invoice.model_validate(GOOD))
    assert v2.schema_version == 2 and v2.tax == Decimal("0")
    assert InvoiceV2.model_validate(GOOD).tax == Decimal("0")


class FailsOnce:
    def extract(self, document, feedback, attempt):
        assert (feedback is None) == (attempt == 1)  # the errors come back on the second try
        return ScriptedExtractor.render(document, "total off" if attempt == 1 else None, random.Random(0))


def test_the_retry_loop_feeds_the_errors_back():
    invoice, attempts, history = extract(make_document(1), FailsOnce())
    assert invoice is not None and attempts == 2
    assert history == [["value_error"]]


def test_the_scripted_extractor_is_deterministic():
    a, b = ScriptedExtractor(seed=0), ScriptedExtractor(seed=0)
    doc = make_document(7)
    assert [a.extract(doc, None, 1) for _ in range(3)] == [b.extract(doc, None, 1) for _ in range(3)]
