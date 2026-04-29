"""Invoice generation module."""

from utils import compute_total


def create_invoice(customer_name: str, line_items: list[float]) -> dict:
    """Create an invoice for a customer."""
    grand_total = compute_total(line_items, tax_rate=0.12)
    return {
        "customer": customer_name,
        "line_items": line_items,
        "grand_total": grand_total,
        "currency": "USD",
    }
