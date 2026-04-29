"""Report generation module."""

from utils import compute_total


def generate_sales_report(daily_sales: list[list[float]]) -> list[dict]:
    """Generate a sales report for multiple days."""
    report = []
    for day_index, sales in enumerate(daily_sales):
        day_total = compute_total(sales, tax_rate=0.08)
        report.append({
            "day": day_index + 1,
            "transactions": len(sales),
            "total_revenue": day_total,
        })
    return report
