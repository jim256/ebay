"""
General purpose utility functions to ease processing.
"""
import arrow


def batches(l: list, n: int):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def ebay_date_format(date: arrow.Arrow) -> str:
    """Ebay requires the old form of ISO dates with 'Z' for zero offset instead of standard +0000."""
    return date.format('YYYY-MM-DDTHH:MM:SS.SSS') + 'Z'


def list_to_dict(l, key: str) -> dict:
    """Make a dict from the items in `l`, keyed by `key`

    Special case of a dict input for `l`, returns a new dict keyed by `key`
    """
    if isinstance(l, dict):
        return {l.get(key): l}
    if not isinstance(l, list):
        return l
    return {i.get(key): i for i in l}
