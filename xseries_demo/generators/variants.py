"""Variant product generator for X-Series demo data."""

import json
import random
from pathlib import Path
from typing import Iterator

DATA_DIR = Path(__file__).parent.parent / "data"


def load_variant_data() -> dict:
    """Load variant product data from JSON file."""
    filepath = DATA_DIR / "variants.json"
    with open(filepath) as f:
        return json.load(f)


def generate_variant_sku(prefix: str, product_name: str, color: str, size: str = "") -> str:
    """Generate a SKU for a variant product.

    Format: {PREFIX}-{PRODUCT_ABBREV}-{COLOR_ABBREV}[-{SIZE}]
    Example: APP-TSHIRT-BLK-M or HOM-PILLOW-IVY
    """
    # Create product abbreviation (first word, max 6 chars, uppercase)
    words = product_name.upper().split()
    product_abbrev = words[-1][:6] if words else "PROD"

    # Create color abbreviation (first 3 chars)
    color_abbrev = color.upper().replace(" ", "")[:3]

    # Size abbreviation (optional)
    if size:
        size_abbrev = size.upper().replace(" ", "")[:2]
        return f"{prefix}-{product_abbrev}-{color_abbrev}-{size_abbrev}"
    else:
        return f"{prefix}-{product_abbrev}-{color_abbrev}"


def generate_variant_products(
    prefix: str,
    color_attribute_id: str,
    size_attribute_id: str | None = None,
    count: int = 20,
) -> Iterator[dict]:
    """Generate variant product payloads for the X-Series API.

    Each product family has 5 color/shade variants.

    Args:
        prefix: Vertical prefix (APP, ELE, HOM, BTY)
        color_attribute_id: UUID of the Color/Shade variant attribute
        size_attribute_id: UUID of the Size variant attribute (only for Apparel)
        count: Number of variant product families to generate

    Yields:
        Variant product payload dicts ready for the API
    """
    data = load_variant_data()
    vertical_data = data["verticals"].get(prefix)

    if not vertical_data:
        raise ValueError(f"Unknown vertical prefix: {prefix}")

    products = vertical_data["products"]
    colors = vertical_data["colors"]
    sizes = vertical_data.get("sizes", [])
    use_size = prefix == "APP" and size_attribute_id and sizes

    # Select products (up to count, or all available)
    selected_products = products[:count] if len(products) >= count else products

    for product in selected_products:
        name = product["name"]
        base_price = product["base_price"]

        # Build variants array with 5 colors/shades
        variants = []
        for color in colors:
            if use_size:
                # For apparel, vary size
                size = random.choice(sizes)
                sku = generate_variant_sku(prefix, name, color, size)
                variants.append({
                    "sku": sku,
                    "variant_definitions": [
                        {"attribute_id": color_attribute_id, "value": color},
                        {"attribute_id": size_attribute_id, "value": size},
                    ],
                })
            else:
                # For other verticals, just color/shade
                sku = generate_variant_sku(prefix, name, color, "")
                variants.append({
                    "sku": sku,
                    "variant_definitions": [
                        {"attribute_id": color_attribute_id, "value": color},
                    ],
                })

        yield {
            "name": name,
            "base_price": base_price,
            "payload": {
                "name": name,
                "variants": variants,
            },
        }


def get_or_create_variant_attributes(
    client, prefix: str = "APP"
) -> tuple[str, str | None] | None:
    """Get or create variant attributes based on vertical.

    Args:
        client: XSeriesClient instance
        prefix: Vertical prefix (APP, ELE, HOM, BTY)

    Returns:
        (color_id, size_id) for Apparel
        (color_id, None) for other verticals
        None on failure
    """
    # Fetch existing attributes
    attributes, error = client.get_variant_attributes()
    if error:
        return None

    # Determine attribute names based on vertical
    color_name = "Shade" if prefix == "BTY" else "Color"
    need_size = prefix == "APP"

    color_id = None
    size_id = None

    # Look for existing attributes
    for attr in attributes:
        name = attr.get("name", "").lower()
        if name in ("color", "colour", "shade"):
            color_id = attr["id"]
        elif name == "size":
            size_id = attr["id"]

    # Create color/shade attribute if missing
    if not color_id:
        result = client.create_variant_attribute(color_name)
        if result:
            color_id = result["id"]
        else:
            return None

    # Create size attribute only for Apparel
    if need_size and not size_id:
        result = client.create_variant_attribute("Size")
        if result:
            size_id = result["id"]
        else:
            return None

    return color_id, size_id if need_size else None
