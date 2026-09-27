"""The contract: what an invoice must look like for the code to accept it.

Pydantic turns this class into three things at once — a parser for the model's JSON,
a validator that rejects what the code cannot use, and a JSON Schema to hand the model
so it knows what to produce.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Line(BaseModel):
    description: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0, decimal_places=2)

    @property
    def amount(self) -> Decimal:
        return self.quantity * self.unit_price


class Invoice(BaseModel):
    invoice_number: str = Field(pattern=r"^INV-\d{4,}$")
    issued: date
    currency: Literal["EUR", "USD", "GBP"]
    lines: list[Line] = Field(min_length=1)
    total: Decimal = Field(gt=0, decimal_places=2)

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase(cls, value):
        """'eur' is not wrong, just untidy: normalise instead of rejecting."""
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def total_matches_lines(self):
        """The one rule no field can check on its own."""
        expected = sum((line.amount for line in self.lines), Decimal("0"))
        if abs(expected - self.total) > Decimal("0.01"):
            raise ValueError(
                f"total {self.total} does not equal the sum of the lines, {expected}"
            )
        return self


class InvoiceV2(Invoice):
    """Adds tax, with a default, so every version-1 invoice is still valid."""

    schema_version: Literal[2] = 2
    tax: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)


def upgrade(invoice: Invoice) -> InvoiceV2:
    """A version-1 invoice becomes a version-2 one with no tax recorded."""
    return InvoiceV2(**invoice.model_dump())
