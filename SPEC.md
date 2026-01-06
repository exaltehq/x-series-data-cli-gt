# X-Series Demo Data CLI - Functional Specification

## Overview

A lightweight Python CLI tool to generate demo customers and products in Lightspeed Retail (X-Series) accounts using personal access tokens. Designed for partners who need realistic demo data to validate integrations and demonstrations.

## Technology Stack

- **Language**: Python 3.10+
- **Data Generation**: Faker + faker-commerce
- **HTTP Client**: httpx (async support)
- **CLI Framework**: Click or Typer
- **Progress Display**: rich

---

## API Reference

### Base URL
```
https://{domain_prefix}.retail.lightspeed.app/api/2.0
```

### Authentication
- **Method**: Bearer token (JWT)
- **Header**: `Authorization: Bearer <personal_access_token>`
- **Required Scopes**: `customers:write`, `products:write`

### Endpoints Used

| Operation | Method | Endpoint | Required Scope |
|-----------|--------|----------|----------------|
| Create Customer | POST | `/customers` | `customers:write` |
| Create Product | POST | `/products` | `products:write` |
| List Outlets | GET | `/outlets` | `outlets:read` |

---

## Customer Creation

### Endpoint
`POST /api/2.0/customers`

### Required Fields
| Field | Type | Description |
|-------|------|-------------|
| `first_name` | string | Customer's first name |
| `last_name` | string | Customer's last name |

### Optional Fields (used by CLI)
| Field | Type | Description |
|-------|------|-------------|
| `email` | string | Email address |
| `phone` | string | Phone number |
| `mobile` | string | Mobile phone |
| `company_name` | string | Company name |
| `physical_address_1` | string | Street address |
| `physical_city` | string | City |
| `physical_state` | string | State/Province |
| `physical_postcode` | string | Postal/ZIP code |
| `physical_country_id` | string | ISO country code (e.g., "US", "NZ") |

### Example Payload
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane.smith.a1b2@example.com",
  "phone": "+1-555-123-4567",
  "physical_address_1": "123 Main Street",
  "physical_city": "Portland",
  "physical_state": "OR",
  "physical_postcode": "97201",
  "physical_country_id": "US"
}
```

### Response (201 Created)
```json
{
  "data": {
    "id": "0af7b240-ab83-11e7-eddc-4023c64c85e5",
    "customer_code": "Jane-37YP",
    "name": "Jane Smith",
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane.smith.a1b2@example.com",
    ...
  }
}
```

---

## Product Creation

### Endpoint
`POST /api/2.0/products`

### Required Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Product name |

### Optional Fields (used by CLI)
| Field | Type | Description |
|-------|------|-------------|
| `sku` | string | Stock keeping unit (must be unique) |
| `description` | string | Product description (can contain HTML) |
| `price_including_tax` | number | Price with tax included |
| `price_excluding_tax` | number | Price before tax (use one or the other, not both) |
| `supply_price` | number | Cost/supply price |
| `is_active` | boolean | Whether product is active (default: true) |

### Example Payload
```json
{
  "name": "Classic White T-Shirt - Medium",
  "sku": "APP-TSH-WHT-M-001",
  "description": "Comfortable 100% cotton t-shirt",
  "price_including_tax": 29.99,
  "supply_price": 12.00,
  "is_active": true
}
```

### Response (200 OK)
```json
{
  "data": [
    "0717b8d6-a4eb-858b-351d-16274fdf186c"
  ]
}
```

### Important Constraints
- **Price fields are mutually exclusive**: Use either `price_including_tax` OR `price_excluding_tax`, never both
- **SKU uniqueness**: SKUs should be unique across all products

---

## Rate Limiting

### Limits
- **Formula**: `300 × <number_of_registers> + 50` requests per 5-minute window
- **Minimum** (1 register): 350 requests / 5 minutes (~1.17 req/sec)

### Response Headers
| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Total request limit |
| `X-RateLimit-Remaining` | Remaining requests in window |

### Rate Limited Response (429)
```json
{
  "error": "Too Many Requests",
  "message": "Rate limiting enforced"
}
```
- **Retry-After Header**: RFC1123 date format (e.g., `Wed, 15 Jul 2020 15:04:05 GMT`)

### CLI Strategy
1. Add 100ms delay between requests (conservative pacing)
2. Monitor `X-RateLimit-Remaining` header
3. If remaining < 10% of limit, slow down to 500ms delay
4. On 429: parse `Retry-After`, display countdown, resume automatically
5. Exponential backoff on 5xx errors (1s, 2s, 4s, max 3 retries)

---

## Vertical Dataset Packs

Pre-configured product sets using Faker + faker-commerce for data generation.

### Available Packs (4 Verticals)

| Pack | Prefix | Price Range | Supply Price | Example Products |
|------|--------|-------------|--------------|------------------|
| **Apparel** | `APP` | $15 - $120 | 40-60% of retail | T-shirts, jeans, jackets, shoes |
| **Electronics** | `ELE` | $50 - $1,200 | 50-70% of retail | Headphones, cables, speakers, accessories |
| **Home & Kitchen** | `HOM` | $10 - $300 | 45-60% of retail | Kitchenware, decor, bedding, tools |
| **Health & Beauty** | `BTY` | $8 - $120 | 30-50% of retail | Skincare, makeup, wellness, fragrances |

### Data Generation Strategy

#### What faker-commerce Provides (use as-is)
- `ecommerce_name()` → Product names like "Ergonomic Wooden Chair"
- `ecommerce_category()` → 22 categories (Electronics, Clothing, Beauty, Home, etc.)
- `ecommerce_material()` → 11 materials (Steel, Wooden, Cotton, Plastic, etc.)

**Built-in adjectives**: Small, Ergonomic, Rustic, Intelligent, Gorgeous, Incredible, Fantastic, Practical, Sleek, Awesome, Generic, Handcrafted, Handmade, Licensed, Refined, Unbranded, Tasty

**Built-in products**: Chair, Car, Computer, Keyboard, Mouse, Bike, Ball, Gloves, Pants, Shirt, Table, Shoes, Hat, Towels, Soap, Tuna, Chicken, Fish, Cheese, Bacon, Pizza, Salad, Sausages, Chips

#### What We Override/Customize

| Field | Why Override | Our Approach |
|-------|--------------|--------------|
| **Price** | faker-commerce range is $1-$999,999 | Custom ranges per vertical |
| **SKU** | Not provided | Generate `{PREFIX}-{###}` with uniqueness check |
| **Product types** | Generic list includes food items | Curated lists per vertical (JSON files) |
| **Categories** | Need vertical-specific | Filter to relevant categories per pack |

### Field Population Rules

#### Apparel Pack (`APP`)
```
SKU format:    APP-{5 random digits}
Name:          Uses ecommerce_name() filtered to clothing items
Price range:   $15.00 - $120.00
Supply price:  40-60% of retail price
Products:      Pants, Shirt, Shoes, Hat, Gloves + custom apparel items
```

#### Electronics Pack (`ELE`)
```
SKU format:    ELE-{5 random digits}
Name:          Uses ecommerce_name() filtered to tech items
Price range:   $50.00 - $1,200.00
Supply price:  50-70% of retail price
Products:      Computer, Keyboard, Mouse + custom electronics items
```

#### Home & Kitchen Pack (`HOM`)
```
SKU format:    HOM-{5 random digits}
Name:          Uses ecommerce_name() with materials (Steel, Wooden, etc.)
Price range:   $10.00 - $300.00
Supply price:  45-60% of retail price
Products:      Chair, Table, Towels + custom home items
```

#### Health & Beauty Pack (`BTY`)
```
SKU format:    BTY-{5 random digits}
Name:          Uses ecommerce_name() filtered to beauty/health items
Price range:   $8.00 - $120.00
Supply price:  30-50% of retail price
Products:      Soap + custom beauty/wellness items
```

### Custom Product Lists (JSON)

Each vertical has a supplementary JSON file with curated product names:

```json
// data/apparel_products.json
{
  "products": ["T-Shirt", "Hoodie", "Jeans", "Sneakers", "Jacket", "Dress", "Skirt", "Sweater"],
  "adjectives": ["Classic", "Vintage", "Modern", "Slim-Fit", "Relaxed", "Premium"],
  "materials": ["Cotton", "Denim", "Wool", "Polyester", "Leather", "Linen"]
}
```

### Price Generation

```python
import random

def generate_price(min_price: float, max_price: float) -> float:
    """Generate realistic retail price ending in .99 or .95"""
    base = random.uniform(min_price, max_price)
    return round(base - (base % 1) + random.choice([0.95, 0.99]), 2)

def generate_supply_price(retail_price: float, margin_low: float, margin_high: float) -> float:
    """Generate supply price as percentage of retail"""
    margin = random.uniform(margin_low, margin_high)
    return round(retail_price * margin, 2)
```

---

## Customer Data Generation

Uses Python Faker library for all customer fields.

### Faker Methods Used

| X-Series Field | Faker Method | Example Output |
|----------------|--------------|----------------|
| `first_name` | `fake.first_name()` | "Jane" |
| `last_name` | `fake.last_name()` | "Smith" |
| `email` | Custom (see below) | "jane.smith.a1b2c3@example.com" |
| `phone` | Custom (see below) | "+1-555-867-5309" |
| `physical_address_1` | `fake.street_address()` | "791 Crist Parks" |
| `physical_city` | `fake.city()` | "Sashabury" |
| `physical_state` | `fake.state_abbr()` | "IL" |
| `physical_postcode` | `fake.postcode()` | "86039" |
| `physical_country_id` | `fake.current_country_code()` | "US" |

### Email Strategy
- **Domain**: Use reserved domains per RFC 2606: `example.com`
- **Format**: `{firstname}.{lastname}.{unique_id}@example.com`
- **Example**: `jane.smith.a1b2c3@example.com`
- **Uniqueness**: 6-character alphanumeric suffix ensures no collisions

```python
import secrets
from faker import Faker

fake = Faker()

def generate_email(first_name: str, last_name: str) -> str:
    """Generate safe dummy email using reserved domain"""
    unique_id = secrets.token_hex(3)  # 6 hex characters
    local = f"{first_name}.{last_name}.{unique_id}".lower()
    return f"{local}@example.com"
```

### Phone Numbers
- **Format**: `+1-555-{random 7 digits}` (555 prefix = fictional)
- Ensures no accidental real phone numbers

```python
import random

def generate_phone() -> str:
    """Generate fictional US phone number"""
    return f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}"
```

### Complete Customer Generator

```python
from faker import Faker

fake = Faker('en_US')

def generate_customer() -> dict:
    """Generate a single customer payload for X-Series API"""
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
        "physical_country_id": "US"
    }
```

---

## CLI Interface

### Interactive Mode (Default)

```
$ x-series-demo

🏪 X-Series Demo Data Generator

? Enter domain prefix: mystore
? Enter personal access token: ********
? Select dataset pack(s): (Use arrow keys, space to select)
  ❯ ◉ Apparel
    ◯ Electronics
    ◯ Home & Kitchen
    ◯ Health & Beauty

? Number of products to create: (50)
? Number of customers to create: (50)

Confirm generation:
  Domain:     mystore.retail.lightspeed.app
  Products:   50 (Apparel)
  Customers:  50

? Proceed? (Y/n)
```

### Execution Progress

```
Creating customers...
  [████████████████████░░░░░░░░░░░] 32/50 (64%)
  Rate limit: 287/350 remaining

Creating products...
  [██████████████████████████████░] 48/50 (96%)
  Rate limit: 239/350 remaining

✓ Complete!
  Customers created: 50
  Products created:  50
  Output file:       ./demo-data-2024-01-15-143022.json
```

### Non-Interactive Mode (Flags)

```
$ x-series-demo \
  --domain mystore \
  --token "$XSERIES_TOKEN" \
  --pack apparel \
  --pack electronics \
  --products 100 \
  --customers 75 \
  --output ./my-demo-data.json \
  --yes
```

### Command Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--domain` | `-d` | Domain prefix | (required) |
| `--token` | `-t` | Personal access token | `$XSERIES_TOKEN` env var |
| `--pack` | `-p` | Dataset pack (repeatable) | (interactive select) |
| `--products` | | Number of products | 50 |
| `--customers` | | Number of customers | 50 |
| `--output` | `-o` | Output JSON file path | `./demo-data-{timestamp}.json` |
| `--yes` | `-y` | Skip confirmation prompt | false |
| `--dry-run` | | Validate without creating | false |
| `--verbose` | `-v` | Show detailed output | false |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `XSERIES_TOKEN` | Personal access token (alternative to `--token`) |
| `XSERIES_DOMAIN` | Domain prefix (alternative to `--domain`) |

---

## Output Artifacts

### JSON Mapping File

Generated after successful execution with mappings for created entities.

```json
{
  "metadata": {
    "generated_at": "2024-01-15T14:30:22Z",
    "domain": "mystore",
    "packs": ["apparel"],
    "counts": {
      "customers": 50,
      "products": 50
    }
  },
  "customers": [
    {
      "email": "jane.smith.a1b2c3@example.com",
      "customer_id": "0af7b240-ab83-11e7-eddc-4023c64c85e5",
      "name": "Jane Smith"
    }
  ],
  "products": [
    {
      "sku": "APP-TSH-BLU-L-001",
      "product_id": "0717b8d6-a4eb-858b-351d-16274fdf186c",
      "name": "Blue T-Shirt - Large",
      "price": 29.99
    }
  ]
}
```

---

## Error Handling

### API Errors

| Status | Handling |
|--------|----------|
| 400 Bad Request | Log error, skip item, continue |
| 401 Unauthorized | Exit with auth error message |
| 403 Forbidden | Exit with scope/permission error |
| 404 Not Found | Exit with invalid domain message |
| 409 Conflict | Log duplicate, skip item, continue |
| 429 Rate Limited | Wait per Retry-After, resume |
| 5xx Server Error | Retry with exponential backoff (max 3) |

### Validation Errors

- Invalid domain format → prompt for correction
- Invalid token format → prompt for correction
- Products/customers count < 1 or > 500 → clamp to valid range

### Recovery

- On partial failure: output file contains successfully created entities
- Log file with detailed error information for debugging

---

## Implementation Breakdown

### Module Structure (Python)

```
xseries_demo/
├── __init__.py
├── __main__.py           # Entry point (python -m xseries_demo)
├── cli.py                # Click/Typer CLI definition
├── api/
│   ├── __init__.py
│   ├── client.py         # HTTP client with auth & rate limiting
│   ├── customers.py      # Customer creation endpoint
│   └── products.py       # Product creation endpoint
├── generators/
│   ├── __init__.py
│   ├── customers.py      # Faker-based customer generation
│   └── products.py       # Product generation with vertical packs
├── data/
│   ├── apparel.json      # Apparel product types, adjectives
│   ├── electronics.json  # Electronics product types
│   ├── home.json         # Home & Kitchen product types
│   └── beauty.json       # Health & Beauty product types
└── output.py             # JSON mapping file writer

pyproject.toml            # Project config, dependencies
README.md                 # Usage documentation
```

### Dependencies (pyproject.toml)

```toml
[project]
name = "xseries-demo"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "faker>=22.0.0",
    "faker-commerce>=1.0.3",
    "httpx>=0.26.0",
    "click>=8.1.0",
    "rich>=13.0.0",
]

[project.scripts]
xseries-demo = "xseries_demo.cli:main"
```

### Suggested Implementation Order

1. **API Client** - httpx client with auth, rate limit handling, retries
2. **Customer Module** - Faker generator + API integration
3. **Product Module (Apparel)** - Single pack as proof of concept
4. **CLI Framework** - Click commands + rich progress
5. **Output/Mapping** - JSON file generation
6. **Remaining Packs** - Electronics, Home, Beauty verticals
7. **Polish** - Error messages, progress UI, dry-run mode

---

## Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.10+ | Faker ecosystem is strongest in Python |
| Data generation | Faker + faker-commerce | Most mature, well-documented libraries |
| HTTP client | httpx | Async support, modern API |
| CLI framework | Click | Mature, well-documented, rich integration |
| Vertical packs | 4 (Apparel, Electronics, Home, Beauty) | Covers common retail verticals |
| Email domain | `example.com` | RFC 2606 reserved, guaranteed safe |
| Phone prefix | `555` | Fictional number range |
| Price format | `price_including_tax` | Simpler, one field covers all stores |
| Price generation | Custom per vertical | faker-commerce range ($1-$1M) unusable |
| SKU format | `{PACK}-{5 digits}` | Unique, sortable, identifiable by pack |
| Images | Skip for v1 | Simplifies implementation, can add later |
| Supplier/Category | Skip for v1 | Requires fetching/creating dependencies |
| Tags | Skip for v1 | Same as above |
| API version | 2.0 | Most complete, stable endpoints |

---

## Out of Scope (v1)

- OAuth2 flow (personal access tokens only)
- Sales generation (use existing random sales tool)
- Image uploads
- Supplier/category/tag creation
- Multi-tenant orchestration
- GUI interface
- Inventory levels per outlet (products created without stock)

---

## Future Enhancements (v2+)

- Image support via URL
- Supplier and category creation/linking
- Inventory initialization per outlet
- Additional locales for customer addresses
- Custom field population
- Import from CSV template
- Batch/bulk API endpoints if available
