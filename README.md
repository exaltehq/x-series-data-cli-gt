# X-Series Demo Data Generator

Generate demo data for your X-Series retail store: 100 products, 50 customers, and 50 sales.

## Quick Start

```bash
pip install -e .
xseries-demo
```

## Requirements

- Python 3.10+
- X-Series trial/demo account
- Personal access token with scopes: `customers:write`, `products:write`, `sales:write`

## Usage

```bash
xseries-demo           # Interactive mode
xseries-demo --dry-run # Preview without creating data
xseries-demo --debug   # Show API requests/responses
```

## What It Creates

| Type      | Count | Details                          |
|-----------|-------|----------------------------------|
| Products  | 100   | With inventory (100 qty each)    |
| Customers | 50    | Realistic names, emails, phones  |
| Sales     | 50    | Spread across past 90 days       |

## Output

Creates `demo-data-YYYY-MM-DD-HHMMSS.json` with all entity IDs:

```json
{
  "products": [{"sku": "APP-12345", "product_id": "...", "name": "...", "price": 29.99}],
  "customers": [{"email": "...", "customer_id": "...", "name": "Jane Smith"}],
  "sales": [{"sale_id": "...", "invoice": "1", "total": 108.99, "date": "..."}]
}
```

## Verticals

Choose from 4 product verticals with appropriate names and price ranges:

- **Apparel** ($15–$120)
- **Electronics** ($50–$1,200)
- **Home & Kitchen** ($10–$300)
- **Health & Beauty** ($8–$120)

## Warning

Creates real data. Use on trial/demo accounts only.
