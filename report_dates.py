"""Shared helper for presenting the report date.

Every renderer must show when the underlying FRED data was actually collected,
not when the scoring run happened. Otherwise a re-score of last month's pull
presents itself as this month's numbers.
"""

from datetime import datetime


def display_date(data, fallback='April 2026'):
    """Return the 'Month YYYY' label for a calculated_metrics_reconciled.json dict.

    Prefers data_collection_date (when FRED was actually queried), falling back
    to the scoring-run timestamp for metrics files written before that field
    existed.
    """
    collected = data.get('data_collection_date')
    if collected:
        try:
            return datetime.strptime(collected, '%Y-%m-%d %H:%M:%S').strftime('%B %Y')
        except (TypeError, ValueError):
            pass

    ts = data.get('calculation_timestamp', '')
    if ts:
        try:
            return datetime.fromisoformat(ts).strftime('%B %Y')
        except (TypeError, ValueError):
            pass

    return data.get('calculation_date', fallback)
