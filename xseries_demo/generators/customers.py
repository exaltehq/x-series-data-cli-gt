"""Customer data generator using Faker."""

import random
import secrets
from typing import Generator

from faker import Faker

fake = Faker("en_US")


def generate_email(first_name: str, last_name: str) -> str:
    """Generate a safe dummy email using reserved domain (RFC 2606)."""
    unique_id = secrets.token_hex(3)  # 6 hex characters
    local = f"{first_name}.{last_name}.{unique_id}".lower()
    # Replace any spaces or special chars
    local = local.replace(" ", "").replace("'", "")
    return f"{local}@example.com"


def generate_phone() -> str:
    """Generate a fictional US phone number using 555 prefix."""
    return f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"


def generate_customer() -> dict:
    """Generate a single customer payload for X-Series API."""
    first = fake.first_name()
    last = fake.last_name()

    return {
        "first_name": first,
        "last_name": last,
        "email": generate_email(first, last),
        "phone": generate_phone(),
        "physical_address_1": fake.street_address(),
        "physical_city": fake.city(),
        "physical_state": fake.state_abbr(),
        "physical_postcode": fake.postcode(),
        "physical_country_id": "US",
    }


def generate_customers(count: int = 50) -> Generator[dict, None, None]:
    """Generate multiple customer payloads."""
    for _ in range(count):
        yield generate_customer()
