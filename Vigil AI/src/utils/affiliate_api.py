"""
affiliate_api.py - Router for fetching products.
Currently returns placeholder data.
"""

def search_products(provider, search_term):
    """
    Returns a list of 5 placeholder products.
    In the next step, we will integrate real APIs here.
    """
    products = []
    for i in range(1, 6):
        products.append({
            "name": f"{search_term.capitalize()} Pro {i}000",
            "price": f"${19.99 + i * 10:.2f}",
            "description": f"High-quality {search_term} with premium features. Perfect for daily use.",
            "image_url": "https://via.placeholder.com/150",
            "affiliate_link": f"https://example.com/affiliate/{search_term}_{i}"
        })
    return products