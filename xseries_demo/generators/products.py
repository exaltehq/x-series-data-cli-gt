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
        "LIQ": "liquor.json",
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


def generate_product_name(data: dict, used_names: set[str]) -> str:
    """Generate a unique product name from vertical data.

    Args:
        data: Vertical data dict with products, adjectives, brands/materials
        used_names: Set of already used names to ensure uniqueness
    """
    max_attempts = 100  # Prevent infinite loop

    for _ in range(max_attempts):
        product = random.choice(data["products"])
        adjective = random.choice(data["adjectives"])

        # Some verticals have brands, others have materials
        if "brands" in data:
            brand = random.choice(data["brands"])
            name = f"{brand} {adjective} {product}"
        elif "materials" in data:
            material = random.choice(data["materials"])
            # Randomly decide format
            if random.random() > 0.5:
                name = f"{adjective} {material} {product}"
            else:
                name = f"{material} {product}"
        else:
            name = f"{adjective} {product}"

        if name not in used_names:
            used_names.add(name)
            return name

    # Fallback: add random suffix if too many collisions
    name = f"{name} #{random.randint(1000, 9999)}"
    used_names.add(name)
    return name


def generate_product(
    prefix: str, used_skus: set[str], used_names: set[str], tax_inclusive: bool = True
) -> dict:
    """Generate a single product payload for X-Series API.

    Args:
        prefix: Vertical prefix (APP, ELE, HOM, BTY, LIQ)
        used_skus: Set of already used SKUs to ensure uniqueness
        used_names: Set of already used names to ensure uniqueness
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
        "name": generate_product_name(data, used_names),
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
        prefix: Vertical prefix (APP, ELE, HOM, BTY, LIQ)
        count: Number of products to generate
        tax_inclusive: If True, use price_including_tax; if False, use price_excluding_tax
    """
    used_skus: set[str] = set()
    used_names: set[str] = set()

    for _ in range(count):
        yield generate_product(prefix, used_skus, used_names, tax_inclusive)
