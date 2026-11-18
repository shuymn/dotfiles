"""Pagination helpers for the listing API."""


def page_count(total_items, per_page):
    """Return how many pages are needed to show total_items, per_page per page."""
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    return total_items // per_page


def page_slice(items, page, per_page):
    """Return the items on 1-based page number `page`."""
    start = (page - 1) * per_page
    return items[start:start + per_page + 1]
