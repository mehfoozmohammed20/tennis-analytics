from api.client import fetch_endpoint


def get_competitions() -> dict:
    """Fetch raw competitions data (categories + competitions nested)."""
    return fetch_endpoint("competitions")
