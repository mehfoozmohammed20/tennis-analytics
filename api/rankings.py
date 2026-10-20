from api.client import fetch_endpoint


def get_doubles_rankings() -> dict:
    """Fetch raw doubles competitor rankings (snapshot + nested competitor_rankings)."""
    return fetch_endpoint("double_competitors_rankings")
