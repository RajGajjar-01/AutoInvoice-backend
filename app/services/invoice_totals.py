"""Invoice money math.

This is the single source of truth for invoice totals. It mirrors the
frontend ``computeInvoiceTotals`` (src/features/invoices/invoice-form/utils.ts)
so that the numbers saved on create/update, the numbers printed in the PDF
and the numbers shown in the form are the same.

Rules:
- Line discount: ``flat`` takes an amount (capped at the line base); anything
  else is a percent of the line base.
- Invoice discount applies to the subtotal after line discounts, before tax.
- Line tax is computed on the line amount after its line discount. The
  invoice discount then reduces the tax in proportion to the taxable amount
  it removes. (The older frontend formula divided by the pre-discount
  subtotal, which reduced tax twice when a line had a discount.)
- Shipping and the extra charge are added after tax; round-off rounds the
  grand total to the nearest whole unit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


def _get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        value = item.get(key, default)
    else:
        value = getattr(item, key, default)
    return default if value is None else value


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class LineAmounts:
    line_base: float
    discount: float
    taxable: float
    tax: float
    total: float


@dataclass(frozen=True)
class TotalsBreakdown:
    subtotal: float = 0.0
    items_discount: float = 0.0
    invoice_discount: float = 0.0
    total_tax: float = 0.0
    shipping_charge: float = 0.0
    extra_charge_amount: float = 0.0
    raw_grand_total: float = 0.0
    grand_total: float = 0.0
    lines: list[LineAmounts] = field(default_factory=list)

    def persisted(self) -> dict[str, float]:
        """The values stored on the invoice row."""
        return {
            "subtotal": round(self.subtotal, 2),
            "total_tax": round(self.total_tax, 2),
            "discount": round(self.invoice_discount, 2),
            "grand_total": round(self.grand_total, 2),
        }


def line_amounts(item: Any) -> LineAmounts:
    quantity = _num(_get(item, "quantity", 0))
    price = _num(_get(item, "price", 0))
    tax_rate = _num(_get(item, "tax", 0))
    disc_value = _num(_get(item, "discount", 0))

    line_base = quantity * price
    if _get(item, "discount_type") == "flat":
        disc = min(disc_value, line_base)
    else:
        disc = line_base * (disc_value / 100)
    taxable = line_base - disc
    tax = taxable * tax_rate / 100
    return LineAmounts(line_base, disc, taxable, tax, taxable + tax)


def compute_totals(
    items: Sequence[Any],
    *,
    discount_type: str | None = None,
    discount_value: float = 0.0,
    legacy_discount: float = 0.0,
    shipping_charge: float = 0.0,
    extra_charge_amount: float = 0.0,
    round_off: bool = False,
    hide_pricing: bool = False,
) -> TotalsBreakdown:
    """Compute every total for an invoice.

    ``legacy_discount`` is the flat discount amount that older invoices (made
    before ``discount_type``/``discount_value`` existed) stored in
    ``discount``. It is used only when no ``discount_type`` is given.
    """
    if hide_pricing:
        return TotalsBreakdown()

    lines = [line_amounts(i) for i in items]
    subtotal = sum(line.line_base for line in lines)
    items_discount = sum(line.discount for line in lines)
    line_tax = sum(line.tax for line in lines)

    if discount_type is None and _num(discount_value) == 0 and legacy_discount:
        discount_type, discount_value = "flat", legacy_discount

    taxable_after_items = subtotal - items_discount
    value = _num(discount_value)
    if discount_type == "flat":
        invoice_discount = min(value, taxable_after_items)
    else:
        invoice_discount = taxable_after_items * (value / 100)

    net_before_tax = taxable_after_items - invoice_discount
    if taxable_after_items > 0:
        total_tax = line_tax * (net_before_tax / taxable_after_items)
    else:
        total_tax = 0.0

    shipping = _num(shipping_charge)
    extra = _num(extra_charge_amount)
    raw_grand = net_before_tax + total_tax + shipping + extra
    grand = float(round(raw_grand)) if round_off else raw_grand

    return TotalsBreakdown(
        subtotal=subtotal,
        items_discount=items_discount,
        invoice_discount=invoice_discount,
        total_tax=total_tax,
        shipping_charge=shipping,
        extra_charge_amount=extra,
        raw_grand_total=raw_grand,
        grand_total=grand,
        lines=lines,
    )


def compute_invoice_totals(invoice: Any) -> TotalsBreakdown:
    """Compute totals from a saved invoice (model or mapping)."""
    document_type = _get(invoice, "document_type", "invoice")
    document_type = getattr(document_type, "value", document_type)
    return compute_totals(
        _get(invoice, "items", []) or [],
        discount_type=_get(invoice, "discount_type"),
        discount_value=_num(_get(invoice, "discount_value", 0)),
        legacy_discount=_num(_get(invoice, "discount", 0)),
        shipping_charge=_num(_get(invoice, "shipping_charge", 0)),
        extra_charge_amount=_num(_get(invoice, "extra_charge_amount", 0)),
        round_off=bool(_get(invoice, "round_off", False)),
        hide_pricing=document_type == "challan",
    )
