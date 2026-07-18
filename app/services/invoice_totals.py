from __future__ import annotations


def compute_totals(
    items: list,
    *,
    discount: float = 0.0,
    hide_pricing: bool = False,
) -> dict[str, float]:
    if hide_pricing:
        return {"subtotal": 0.0, "total_tax": 0.0, "grand_total": 0.0}

    subtotal = sum(
        (i.quantity if hasattr(i, "quantity") else i.get("quantity", 0))
        * (i.price if hasattr(i, "price") else i.get("price", 0))
        for i in items
    )
    total_tax = sum(
        (i.quantity if hasattr(i, "quantity") else i.get("quantity", 0))
        * (i.price if hasattr(i, "price") else i.get("price", 0))
        * ((i.tax if hasattr(i, "tax") else i.get("tax", 0)) / 100.0)
        for i in items
    )
    grand_total = subtotal + total_tax - discount
    return {
        "subtotal": round(subtotal, 2),
        "total_tax": round(total_tax, 2),
        "grand_total": round(max(grand_total, 0.0), 2),
    }
