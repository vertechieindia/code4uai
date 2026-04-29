"""Dashboard module for displaying totals."""

from utils import compute_total


def render_dashboard(transactions: list[list[float]]) -> dict:
    """Render a summary dashboard from transaction data."""
    all_items = [item for group in transactions for item in group]
    grand_total = compute_total(all_items, tax_rate=0.09)
    return {
        "transaction_count": len(transactions),
        "item_count": len(all_items),
        "grand_total": grand_total,
    }
