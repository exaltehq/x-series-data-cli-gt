"""Product data generator using Faker and vertical-specific data."""

import json
import random
from pathlib import Path
from typing import Generator

from faker import Faker

fake = Faker()

# Load vertical data files
DATA_DIR = Path(__file__).parent.parent / "data"

VERTICAL_DATA: dict[str, dict] = {}


def load_vertical_data(prefix: str) -> dict:
    """Load vertical data from JSON file, with caching."""
    if prefix in VERTICAL_DATA:
        return VERTICAL_DATA[prefix]

    prefix_to_file = {
        "APP": "apparel.json",
        "ELE": "electronics.json",
        "HOM": "home.json",
        "BTY": "beauty.json",
    }

    filename = prefix_to_file.get(prefix)
    if not filename:
        raise ValueError(f"Unknown vertical prefix: {prefix}")

    filepath = DATA_DIR / filename
    with open(filepath) as f:
        data = json.load(f)

    VERTICAL_DATA[prefix] = data
    return data


def generate_sku(prefix: str, used_skus: set[str]) -> str:
    """Generate a unique SKU for the given vertical."""
    while True:
        sku = f"{prefix}-{random.randint(10000, 99999)}"
        if sku not in used_skus:
            used_skus.add(sku)
            return sku


def generate_price(min_price: float, max_price: float) -> float:
    """Generate a realistic retail price ending in .99 or .95."""
    base = random.uniform(min_price, max_price)
    rounded = int(base)
    ending = random.choice([0.95, 0.99])
    return round(rounded + ending, 2)


def generate_supply_price(retail_price: float, margin_min: float, margin_max: float) -> float:
    """Generate supply price as a percentage of retail."""
    margin = random.uniform(margin_min, margin_max)
    return round(retail_price * margin, 2)


def generate_product_name(data: dict) -> str:
    """Generate a product name from vertical data."""
    product = random.choice(data["products"])
    adjective = random.choice(data["adjectives"])

    # Some verticals have brands, others have materials
    if "brands" in data:
        brand = random.choice(data["brands"])
        return f"{brand} {adjective} {product}"
    elif "materials" in data:
        material = random.choice(data["materials"])
        # Randomly decide format
        if random.random() > 0.5:
            return f"{adjective} {material} {product}"
        else:
            return f"{material} {product}"
    else:
        return f"{adjective} {product}"


def generate_product(prefix: str, used_skus: set[str], tax_inclusive: bool = True) -> dict:
    """Generate a single product payload for X-Series API.

    Args:
        prefix: Vertical prefix (APP, ELE, HOM, BTY)
        used_skus: Set of already used SKUs to ensure uniqueness
        tax_inclusive: If True, use price_including_tax; if False, use price_excluding_tax
    """
    data = load_vertical_data(prefix)

    price_range = data["price_range"]
    supply_margin = data["supply_margin"]

    retail_price = generate_price(price_range["min"], price_range["max"])
    supply_price = generate_supply_price(
        retail_price, supply_margin["min"], supply_margin["max"]
    )

    price_field = "price_including_tax" if tax_inclusive else "price_excluding_tax"

    return {
        "name": generate_product_name(data),
        "sku": generate_sku(prefix, used_skus),
        price_field: retail_price,
        "supply_price": supply_price,
        "is_active": True,
    }


def generate_products(
    prefix: str, count: int = 50, tax_inclusive: bool = True
) -> Generator[dict, None, None]:
    """Generate multiple product payloads for the given vertical.

    Args:
        prefix: Vertical prefix (APP, ELE, HOM, BTY)
        count: Number of products to generate
        tax_inclusive: If True, use price_including_tax; if False, use price_excluding_tax
    """
    used_skus: set[str] = set()

    for _ in range(count):
        yield generate_product(prefix, used_skus, tax_inclusive)
