"""Order processing module."""

from utils import compute_total


def process_order(item_prices: list[float]) -> dict:
    """Process a customer order and return the summary."""
    total = compute_total(item_prices)
    return {
        "item_count": len(item_prices),
        "subtotal": sum(item_prices),
        "total": total,
        "status": "processed",
    }
