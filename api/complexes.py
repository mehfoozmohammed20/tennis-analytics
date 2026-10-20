from api.client import fetch_endpoint


def get_complexes() -> dict:
    """Fetch raw complexes data (complexes + nested venues)."""
    return fetch_endpoint("complexes")
