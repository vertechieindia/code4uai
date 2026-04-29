"""Utility functions for the test project."""


def compute_total(items: list[float], tax_rate: float = 0.1) -> float:
    """Calculate the total price of items including tax.

    Args:
        items: List of item prices.
        tax_rate: Tax rate as a decimal (default 10%).

    Returns:
        Total price with tax applied.
    """
    subtotal = sum(items)
    return subtotal * (1 + tax_rate)
