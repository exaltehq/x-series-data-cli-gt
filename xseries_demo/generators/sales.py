"""Sales generator for X-Series demo data."""

import random
from datetime import datetime, timedelta, timezone
from typing import Iterator


def generate_sale_date(days_back: int = 90) -> str:
    """Generate a random sale date within the past N days.

    Args:
        days_back: Maximum days in the past (default 90)

    Returns:
        ISO 8601 formatted date string
    """
    now = datetime.now(timezone.utc)
    random_days = random.randint(0, days_back)
    random_hours = random.randint(8, 20)  # Business hours 8am-8pm
    random_minutes = random.randint(0, 59)

    sale_time = now - timedelta(days=random_days)
    sale_time = sale_time.replace(hour=random_hours, minute=random_minutes, second=0)

    return sale_time.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_sales(
    products: list[dict],
    customers: list[dict],
    user_id: str,
    register_id: str,
    payment_type_id: str,
    tax_id: str,
    count: int = 50,
) -> Iterator[dict]:
    """Generate sale payloads for the X-Series API.

    Args:
        products: List of created products with id, name, sku, price
        customers: List of created customers with customer_id, name, email
        user_id: ID of the user (cashier) to assign sales to
        register_id: ID of the register for the sales
        payment_type_id: ID of the payment type (typically Cash)
        tax_id: ID of the tax to apply (typically No Tax)
        count: Number of sales to generate

    Yields:
        Sale payload dicts ready for the API
    """
    for _ in range(count):
        # Pick 1-3 random products for this sale
        num_products = random.randint(1, min(3, len(products)))
        sale_products = random.sample(products, num_products)

        # Build line items
        line_items = []
        total_price = 0.0

        for product in sale_products:
            quantity = random.randint(1, 3)
            price = product.get("price", 0)
            if not price:
                price = 50.0  # Fallback price

            line_total = price * quantity
            total_price += line_total

            line_items.append({
                "product_id": product["product_id"],
                "quantity": quantity,
                "price": price,
                "tax": 0,
                "tax_id": tax_id,
            })

        # Randomly assign a customer (80% of sales) or leave as walk-in (20%)
        customer_id = None
        if customers and random.random() < 0.8:
            customer = random.choice(customers)
            customer_id = customer["customer_id"]

        sale_payload = {
            "user_id": user_id,
            "register_id": register_id,
            "state": "closed",
            "sale_date": generate_sale_date(),
            "register_sale_products": line_items,
            "register_sale_payments": [
                {
                    "retailer_payment_type_id": payment_type_id,
                    "amount": round(total_price, 2),
                }
            ],
        }

        if customer_id:
            sale_payload["customer_id"] = customer_id

        yield sale_payload
