# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python CLI tool to generate demo customers, products, and sales in Lightspeed Retail (X-Series) accounts using personal access tokens. Partners use this to populate realistic demo data for integration testing and demonstrations.

## Build Commands

```bash
# Install dependencies
pip install -e .

# Run CLI
xseries-demo --help
xseries-demo              # Interactive mode
xseries-demo --dry-run    # Preview without creating data
xseries-demo --debug      # Show API requests/responses

# Run tests
pytest
pytest tests/test_generators.py -v        # Run single test file
pytest -k "test_customer"                  # Run tests matching pattern

# Type checking
mypy xseries_demo/

# Lint
ruff check xseries_demo/
```

## Architecture

### Data Flow
1. `cli.py` orchestrates the interactive wizard, collecting domain/token/options
2. Generators (`generators/*.py`) produce Faker-based payloads without API knowledge
3. `api/client.py` handles all HTTP communication with rate limiting and retries
4. `output.py` writes results to timestamped JSON files

### API Client (`api/client.py`)
- Uses httpx with 30s timeout
- Rate limit handling: monitors `X-RateLimit-Remaining`, slows when <10%
- On 429: parses `Retry-After` header, waits, then resumes
- Exponential backoff (1s, 2s, 4s) for 5xx errors
- Uses v2.0 API for most operations, v2.1 for inventory/price updates, v0.9 for sales

### Generator Pattern
Each generator module exports a `generate_*` function that yields dicts:
```python
def generate_products(prefix: str, count: int, tax_inclusive: bool) -> Generator[dict, None, None]
def generate_customers(count: int) -> Generator[dict, None, None]
def generate_sales(products, customers, user_id, register_id, ...) -> Iterator[dict]
def generate_variant_products(prefix, color_attribute_id, size_attribute_id, count) -> Iterator[dict]
```

### Vertical Data Files (`data/*.json`)
Each vertical (apparel, electronics, home, beauty) has a JSON file containing:
- `products`: list of product types
- `adjectives`: descriptive terms
- `brands` or `materials`: vertical-specific naming components
- `price_range`: min/max for the vertical
- `supply_margin`: min/max percentage of retail price

## Key Implementation Details

### Tax Handling
Store setting determines price field: `price_including_tax` vs `price_excluding_tax`. The CLI detects this from `GET /retailer` response (`tax_exclusive` field) and passes to generators.

### Safe Demo Data
- Emails use RFC 2606 reserved domain: `{first}.{last}.{hex}@example.com`
- Phones use fictional 555 prefix: `+1-555-XXX-XXXX`
- SKUs use vertical prefix: `APP-12345`, `ELE-67890`

### Variant Products
Apparel uses Color + Size attributes; other verticals use Color (or Shade for Beauty) only. `get_or_create_variant_attributes()` handles idempotent attribute creation.

### Clone Account Feature (`clone.py`)
Copies products and customers from one X-Series account to another:
- `get_all_products()` / `get_all_customers()`: Paginated fetching from source
- `transform_product_for_creation()` / `transform_customer_for_creation()`: Strip IDs, system fields
- `map_outlets_by_name()`: Match outlet IDs between accounts for inventory cloning
- Inventory is cloned with exact quantities when outlets match by name

## Key Documents

- `SPEC.md` - Complete functional specification with API schemas and implementation plan
- `openapi/legacy-api-v2-0.yml` - X-Series API specification
