"""Clone functionality to copy data between X-Series accounts."""

from typing import Any

from rich.console import Console


def classify_error(
    status_code: int | None,
    error_message: str,
    response_body: dict | str | None = None,
) -> str:
    """Classify an API error into a category for reporting.

    Args:
        status_code: HTTP status code (4xx, 5xx)
        error_message: Error message from API
        response_body: Full response body (optional)

    Returns:
        Error type: duplicate, validation, permission, not_found, server, unknown
    """
    if status_code is None:
        return "unknown"

    # Permission errors
    if status_code == 403:
        return "permission"
    if status_code == 401:
        return "permission"

    # Server errors (temporary, could retry)
    if status_code >= 500:
        return "server"

    # Check message for specific patterns
    msg_lower = error_message.lower() if error_message else ""

    if "already exists" in msg_lower or "duplicate" in msg_lower:
        return "duplicate"

    if "not found" in msg_lower:
        return "not_found"

    # Generic validation error (400 Bad Request, 422 Unprocessable Entity)
    if status_code in (400, 422):
        return "validation"

    # 404 without "not found" message
    if status_code == 404:
        return "not_found"

    return "unknown"
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from xseries_demo.api.client import XSeriesClient
from xseries_demo.output import CloneLogger

console = Console()


# Fields accepted by POST /products (whitelist approach)
# Based on API 2.0 spec - only these fields are valid for creation
PRODUCT_ALLOWED_FIELDS = {
    "name",  # required
    "description",
    "handle",
    "sku",
    "product_codes",  # needs nested cleanup
    "source",
    "source_id",
    "source_variant_id",
    "is_active",
    "price_including_tax",
    "price_excluding_tax",
    "supply_price",
    "supplier_id",
    "supplier_code",
    "product_suppliers",  # needs nested cleanup
    "product_type_id",
    "product_category_id",
    "brand_id",
    "tag_ids",
    # "attributes",  # GET returns array, POST expects object - skip for now
    # "images",  # Would need transformation
    # "inventory",  # Handled separately after creation
    "account_code_sale",
    "account_code_purchase",
    "loyalty_amount",
    "weight",
    "weight_unit",
    "length",
    "width",
    "height",
    "dimensions_unit",
    # "variants",  # Complex - skip for now
    "all_outlets_tax",
    "outlet_taxes",
    # "composite",  # Would need product ID mapping
}

# Fields to strip when transforming customers for creation
CUSTOMER_STRIP_FIELDS = {
    "id",
    "version",
    "created_at",
    "updated_at",
    "deleted_at",
    "customer_code",
    "year_to_date",
    "balance",
    "loyalty_balance",
    "loyalty_email_sent",
    "custom_field_1",
    "custom_field_2",
    "custom_field_3",
    "custom_field_4",
}

# Fields to strip when transforming sales for creation
SALE_STRIP_FIELDS = {
    "id",
    "version",
    "created_at",
    "updated_at",
    "sequence",
    "receipt_number",
    "invoice_number",
    "invoice_sequence",
    "return_for",
}


def transform_product_for_creation(
    product: dict,
    tax_inclusive: bool = True,
    brand_mapping: dict[str, str] | None = None,
    supplier_mapping: dict[str, str] | None = None,
) -> dict:
    """Transform a product from source to be created in destination.

    Uses whitelist approach - only includes fields accepted by POST /products.

    Args:
        product: Full product data from source account
        tax_inclusive: If True, use price_including_tax; else price_excluding_tax
        brand_mapping: Mapping of source brand_id -> dest brand_id
        supplier_mapping: Mapping of source supplier_id -> dest supplier_id

    Returns:
        Product payload suitable for POST /products
    """
    brand_mapping = brand_mapping or {}
    supplier_mapping = supplier_mapping or {}
    transformed = {}

    for key, value in product.items():
        # Only include whitelisted fields
        if key not in PRODUCT_ALLOWED_FIELDS:
            continue
        if value is None:
            continue

        # Map brand_id to destination
        if key == "brand_id":
            if value in brand_mapping:
                transformed[key] = brand_mapping[value]
            # Skip if brand not mapped (don't include unmapped brand_id)
            continue

        # Map supplier_id to destination
        if key == "supplier_id":
            if value in supplier_mapping:
                transformed[key] = supplier_mapping[value]
            # Skip if supplier not mapped
            continue

        # Clean nested objects - strip id fields
        if key == "product_codes" and isinstance(value, list):
            cleaned = []
            for code in value:
                if isinstance(code, dict):
                    cleaned.append({
                        k: v for k, v in code.items()
                        if k in ("type", "code") and v is not None
                    })
            if cleaned:
                transformed[key] = cleaned
            continue

        if key == "product_suppliers" and isinstance(value, list):
            cleaned = []
            for supplier in value:
                if isinstance(supplier, dict):
                    # Map supplier_id if present
                    supplier_cleaned = {}
                    for k, v in supplier.items():
                        if k not in ("supplier_id", "price", "code") or v is None:
                            continue
                        if k == "supplier_id" and v in supplier_mapping:
                            supplier_cleaned[k] = supplier_mapping[v]
                        elif k != "supplier_id":
                            supplier_cleaned[k] = v
                    if supplier_cleaned:
                        cleaned.append(supplier_cleaned)
            if cleaned:
                transformed[key] = cleaned
            continue

        transformed[key] = value

    # Handle "active" -> "is_active" field name mismatch
    if "is_active" not in transformed and "active" in product:
        transformed["is_active"] = product["active"]

    # API doesn't allow both price fields - keep only one
    if "price_including_tax" in transformed and "price_excluding_tax" in transformed:
        if tax_inclusive:
            del transformed["price_excluding_tax"]
        else:
            del transformed["price_including_tax"]

    return transformed


def transform_customer_for_creation(customer: dict) -> dict:
    """Transform a customer from source to be created in destination.

    Strips IDs and system-managed fields, keeping only data needed for creation.

    Args:
        customer: Full customer data from source account

    Returns:
        Customer payload suitable for POST /customers
    """
    transformed = {}

    for key, value in customer.items():
        if key in CUSTOMER_STRIP_FIELDS:
            continue
        if value is None:
            continue
        # Handle nested objects that might have IDs
        if key == "customer_group" and isinstance(value, dict):
            # Skip customer group - would need to be mapped separately
            continue
        transformed[key] = value

    return transformed


def map_outlets_by_name(
    source_outlets: list[dict], dest_outlets: list[dict]
) -> dict[str, str]:
    """Create a mapping from source outlet IDs to destination outlet IDs by name.

    Args:
        source_outlets: Outlets from source account
        dest_outlets: Outlets from destination account

    Returns:
        Dict mapping source_outlet_id -> dest_outlet_id
    """
    # Build name -> id mapping for destination
    dest_by_name = {outlet["name"]: outlet["id"] for outlet in dest_outlets}

    # Map source IDs to destination IDs
    mapping = {}
    for outlet in source_outlets:
        source_id = outlet["id"]
        name = outlet["name"]
        if name in dest_by_name:
            mapping[source_id] = dest_by_name[name]

    return mapping


def transform_inventory_for_destination(
    inventory: list[dict], outlet_mapping: dict[str, str]
) -> list[dict]:
    """Transform inventory records from source to destination outlet IDs.

    Args:
        inventory: Inventory records from source
        outlet_mapping: source_outlet_id -> dest_outlet_id mapping

    Returns:
        Inventory records with destination outlet IDs
    """
    transformed = []
    for record in inventory:
        source_outlet_id = record.get("outlet_id")
        if source_outlet_id in outlet_mapping:
            transformed.append({
                "outlet_id": outlet_mapping[source_outlet_id],
                "current_amount": record.get("current_amount", 0),
            })
    return transformed


def map_by_name(source_items: list[dict], dest_items: list[dict]) -> dict[str, str]:
    """Create a mapping from source IDs to destination IDs by matching names.

    Works for registers, users, payment_types, and taxes.

    Args:
        source_items: Items from source account (must have 'id' and 'name')
        dest_items: Items from destination account (must have 'id' and 'name')

    Returns:
        Dict mapping source_id -> dest_id
    """
    dest_by_name = {item.get("name"): item.get("id") for item in dest_items if item.get("name")}
    mapping = {}
    for item in source_items:
        source_id = item.get("id")
        name = item.get("name")
        if source_id and name and name in dest_by_name:
            mapping[source_id] = dest_by_name[name]
    return mapping


def transform_sale_for_creation(
    sale: dict,
    product_mapping: dict[str, str],
    customer_mapping: dict[str, str],
    register_mapping: dict[str, str],
    user_mapping: dict[str, str],
    tax_mapping: dict[str, str],
    payment_type_mapping: dict[str, str],
) -> dict | None:
    """Transform a sale from source to be created in destination.

    Args:
        sale: Full sale data from source account
        product_mapping: source_product_id -> dest_product_id
        customer_mapping: source_customer_id -> dest_customer_id
        register_mapping: source_register_id -> dest_register_id
        user_mapping: source_user_id -> dest_user_id
        tax_mapping: source_tax_id -> dest_tax_id
        payment_type_mapping: source_payment_type_id -> dest_payment_type_id

    Returns:
        Sale payload suitable for POST /register_sales, or None if required mappings missing
    """
    # Map required fields
    source_register_id = sale.get("register_id")
    source_user_id = sale.get("user_id")

    if source_register_id not in register_mapping:
        return None
    if source_user_id not in user_mapping:
        return None

    transformed: dict[str, Any] = {
        "register_id": register_mapping[source_register_id],
        "user_id": user_mapping[source_user_id],
        "status": "CLOSED",  # Always create as closed historical sale
        "sale_date": sale.get("sale_date"),
    }

    # Map optional customer
    source_customer_id = sale.get("customer_id")
    if source_customer_id and source_customer_id in customer_mapping:
        transformed["customer_id"] = customer_mapping[source_customer_id]

    # Transform line items (register_sale_products)
    line_items = sale.get("register_sale_products", [])
    transformed_items = []
    for item in line_items:
        source_product_id = item.get("product_id")
        if source_product_id not in product_mapping:
            continue  # Skip products that weren't cloned

        transformed_item: dict[str, Any] = {
            "product_id": product_mapping[source_product_id],
            "quantity": item.get("quantity", 1),
            "price": item.get("price", 0),
            "discount": item.get("discount", 0),
            "loyalty_value": item.get("loyalty_value", 0),
        }

        # Map tax if present
        source_tax_id = item.get("tax_id")
        if source_tax_id and source_tax_id in tax_mapping:
            transformed_item["tax_id"] = tax_mapping[source_tax_id]

        transformed_items.append(transformed_item)

    if not transformed_items:
        return None  # No valid line items

    transformed["register_sale_products"] = transformed_items

    # Transform payments (register_sale_payments)
    payments = sale.get("register_sale_payments", [])
    transformed_payments = []
    for payment in payments:
        source_payment_type_id = payment.get("payment_type_id")
        if source_payment_type_id not in payment_type_mapping:
            continue

        transformed_payments.append({
            "payment_type_id": payment_type_mapping[source_payment_type_id],
            "amount": payment.get("amount", 0),
        })

    if transformed_payments:
        transformed["register_sale_payments"] = transformed_payments

    # Copy other relevant fields
    for field in ["note", "short_code", "total_price", "total_tax"]:
        if field in sale and sale[field] is not None:
            transformed[field] = sale[field]

    return transformed


def fetch_source_products(
    client: XSeriesClient,
    progress: Progress,
    include_inventory: bool = True,
) -> tuple[list[dict], list[dict]]:
    """Fetch all products and their inventory from source account.

    Args:
        client: Source account client
        progress: Rich progress instance
        include_inventory: Whether to fetch inventory for each product

    Returns:
        (products_with_details, inventory_data)
    """
    # First, get list of all products
    fetch_task = progress.add_task(f"[cyan]Fetching products from {client.domain}...", total=None)
    products, error = client.get_all_products()
    if error:
        progress.update(fetch_task, description=f"[red]Error fetching products: {error}[/red]")
        return [], []

    progress.update(
        fetch_task,
        description=f"[green]Found {len(products)} products in {client.domain}[/green]",
        total=len(products),
        completed=len(products),
    )

    # Fetch detailed product info and inventory
    products_with_inventory = []
    inventory_data = []

    if include_inventory and products:
        inv_task = progress.add_task(
            f"[cyan]Fetching inventory from {client.domain}...", total=len(products)
        )
        for product in products:
            product_id = product.get("id")
            if product_id:
                inv = client.get_product_inventory(product_id)
                if inv:
                    inventory_data.append({
                        "product_id": product_id,
                        "sku": product.get("sku"),
                        "inventory": inv,
                    })
            products_with_inventory.append(product)
            progress.advance(inv_task)
    else:
        products_with_inventory = products

    return products_with_inventory, inventory_data


def fetch_source_customers(
    client: XSeriesClient, progress: Progress
) -> list[dict]:
    """Fetch all customers from source account.

    Args:
        client: Source account client
        progress: Rich progress instance

    Returns:
        List of customer data
    """
    fetch_task = progress.add_task(f"[cyan]Fetching customers from {client.domain}...", total=None)
    customers, error = client.get_all_customers()
    if error:
        progress.update(fetch_task, description=f"[red]Error fetching customers: {error}[/red]")
        return []

    progress.update(
        fetch_task,
        description=f"[green]Found {len(customers)} customers in {client.domain}[/green]",
        total=len(customers),
        completed=len(customers),
    )
    return customers


def clone_brands(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    progress: Progress,
    logger: CloneLogger,
) -> dict[str, str]:
    """Clone all brands from source to destination account.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        progress: Rich progress instance
        logger: CloneLogger for incremental logging

    Returns:
        Mapping of source_brand_id -> dest_brand_id
    """
    brand_mapping: dict[str, str] = {}

    # Fetch brands from source
    fetch_task = progress.add_task(
        f"[cyan]Fetching brands from {source_client.domain}...", total=None
    )
    source_brands, error = source_client.get_brands()
    progress.update(fetch_task, completed=True)

    if error or not source_brands:
        return brand_mapping

    # Get existing brands in destination to avoid duplicates
    dest_brands, _ = dest_client.get_brands()
    dest_brand_names = {b.get("name", "").lower(): b.get("id") for b in dest_brands}

    # Create brands in destination
    create_task = progress.add_task(
        f"[cyan]Creating brands in {dest_client.domain}...", total=len(source_brands)
    )

    for brand in source_brands:
        source_id = brand.get("id")
        name = brand.get("name", "")

        # Skip if brand already exists (by name)
        if name.lower() in dest_brand_names:
            brand_mapping[source_id] = dest_brand_names[name.lower()]
            progress.advance(create_task)
            continue

        # Create brand
        brand_data = {"name": name}
        if brand.get("description"):
            brand_data["description"] = brand["description"]

        result = dest_client.create_brand(brand_data)

        if result and result.get("id"):
            new_id = result["id"]
            brand_mapping[source_id] = new_id
            logger.log_success(
                entity_type="brands",
                source_id=source_id,
                new_id=new_id,
                status_code=dest_client.last_status_code or 200,
                identifier=name,
            )
        else:
            error_msg = dest_client.last_error or "Unknown error"
            logger.log_failure(
                entity_type="brands",
                source_id=source_id,
                status_code=dest_client.last_status_code,
                error_message=error_msg,
                error_type=classify_error(dest_client.last_status_code, error_msg),
                request_payload=brand_data,
                response_body=dest_client.last_response_body,
                identifier=name,
            )

        progress.advance(create_task)

    return brand_mapping


def clone_suppliers(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    progress: Progress,
    logger: CloneLogger,
) -> dict[str, str]:
    """Clone all suppliers from source to destination account.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        progress: Rich progress instance
        logger: CloneLogger for incremental logging

    Returns:
        Mapping of source_supplier_id -> dest_supplier_id
    """
    supplier_mapping: dict[str, str] = {}

    # Fetch suppliers from source
    fetch_task = progress.add_task(
        f"[cyan]Fetching suppliers from {source_client.domain}...", total=None
    )
    source_suppliers, error = source_client.get_suppliers()
    progress.update(fetch_task, completed=True)

    if error or not source_suppliers:
        return supplier_mapping

    # Get existing suppliers in destination to avoid duplicates
    dest_suppliers, _ = dest_client.get_suppliers()
    dest_supplier_names = {s.get("name", "").lower(): s.get("id") for s in dest_suppliers}

    # Create suppliers in destination
    create_task = progress.add_task(
        f"[cyan]Creating suppliers in {dest_client.domain}...", total=len(source_suppliers)
    )

    # Fields allowed for supplier creation
    supplier_fields = {"name", "description", "contact"}

    for supplier in source_suppliers:
        source_id = supplier.get("id")
        name = supplier.get("name", "")

        # Skip if supplier already exists (by name)
        if name.lower() in dest_supplier_names:
            supplier_mapping[source_id] = dest_supplier_names[name.lower()]
            progress.advance(create_task)
            continue

        # Build supplier data with allowed fields
        supplier_data = {
            k: v for k, v in supplier.items()
            if k in supplier_fields and v is not None
        }

        result = dest_client.create_supplier(supplier_data)

        if result and result.get("id"):
            new_id = result["id"]
            supplier_mapping[source_id] = new_id
            logger.log_success(
                entity_type="suppliers",
                source_id=source_id,
                new_id=new_id,
                status_code=dest_client.last_status_code or 200,
                identifier=name,
            )
        else:
            error_msg = dest_client.last_error or "Unknown error"
            logger.log_failure(
                entity_type="suppliers",
                source_id=source_id,
                status_code=dest_client.last_status_code,
                error_message=error_msg,
                error_type=classify_error(dest_client.last_status_code, error_msg),
                request_payload=supplier_data,
                response_body=dest_client.last_response_body,
                identifier=name,
            )

        progress.advance(create_task)

    return supplier_mapping


def clone_products(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    progress: Progress,
    logger: CloneLogger,
    include_inventory: bool = True,
    dest_tax_inclusive: bool = True,
    brand_mapping: dict[str, str] | None = None,
    supplier_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Clone all products from source to destination account.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        progress: Rich progress instance
        logger: CloneLogger for incremental logging
        include_inventory: Whether to clone inventory data
        dest_tax_inclusive: Whether destination uses tax-inclusive pricing
        brand_mapping: Mapping of source brand_id -> dest brand_id
        supplier_mapping: Mapping of source supplier_id -> dest supplier_id

    Returns:
        Results dict with created products and failed items
    """
    brand_mapping = brand_mapping or {}
    supplier_mapping = supplier_mapping or {}
    results: dict[str, Any] = {
        "products": [],
        "failed_products": [],
        "inventory_updated": 0,
        "inventory_failed": 0,
    }

    # Fetch products from source
    products, inventory_data = fetch_source_products(
        source_client, progress, include_inventory
    )

    if not products:
        return results

    # Get outlet mapping for inventory
    outlet_mapping = {}
    if include_inventory and inventory_data:
        source_outlets, _ = source_client.get_outlets()
        dest_outlets, _ = dest_client.get_outlets()
        outlet_mapping = map_outlets_by_name(source_outlets, dest_outlets)

        if not outlet_mapping:
            console.print(
                "[yellow]Warning: No matching outlets found between accounts. "
                "Inventory will not be cloned.[/yellow]"
            )

    # Create products in destination
    create_task = progress.add_task(
        f"[cyan]Creating products in {dest_client.domain}...", total=len(products)
    )

    # Build SKU -> inventory lookup
    inventory_by_sku: dict[str, list[dict]] = {}
    for inv_record in inventory_data:
        sku = inv_record.get("sku")
        if sku:
            inventory_by_sku[sku] = inv_record.get("inventory", [])

    for product in products:
        # Transform product for creation
        transformed = transform_product_for_creation(
            product, dest_tax_inclusive, brand_mapping, supplier_mapping
        )

        # Create in destination
        result = dest_client.create_product(transformed)
        source_id = product.get("id")
        sku = product.get("sku")

        if result:
            new_id = result.get("id")
            results["products"].append({
                "source_id": source_id,
                "new_id": new_id,
                "sku": sku,
                "name": product.get("name"),
            })
            # Log success
            logger.log_success(
                entity_type="products",
                source_id=source_id,
                new_id=new_id,
                status_code=dest_client.last_status_code or 201,
                identifier=sku,
            )

            # Update inventory if we have it
            if (
                include_inventory
                and new_id
                and sku
                and sku in inventory_by_sku
                and outlet_mapping
            ):
                source_inventory = inventory_by_sku[sku]
                dest_inventory = transform_inventory_for_destination(
                    source_inventory, outlet_mapping
                )
                if dest_inventory:
                    if dest_client.update_product_inventory(new_id, dest_inventory):
                        results["inventory_updated"] += 1
                        logger.log_success(
                            entity_type="inventory",
                            source_id=source_id,
                            new_id=new_id,
                            status_code=dest_client.last_status_code or 200,
                            identifier=sku,
                        )
                    else:
                        results["inventory_failed"] += 1
                        error_msg = dest_client.last_error or "Unknown error"
                        logger.log_failure(
                            entity_type="inventory",
                            source_id=source_id,
                            status_code=dest_client.last_status_code,
                            error_message=error_msg,
                            error_type=classify_error(
                                dest_client.last_status_code, error_msg
                            ),
                            request_payload=dest_client.last_request_payload,
                            response_body=dest_client.last_response_body,
                            identifier=sku,
                        )
        else:
            error_msg = dest_client.last_error or "Unknown error"
            results["failed_products"].append({
                "sku": sku,
                "name": product.get("name"),
                "reason": error_msg,
            })
            # Log failure with full details
            logger.log_failure(
                entity_type="products",
                source_id=source_id,
                status_code=dest_client.last_status_code,
                error_message=error_msg,
                error_type=classify_error(dest_client.last_status_code, error_msg),
                request_payload=transformed,
                response_body=dest_client.last_response_body,
                identifier=sku,
            )

        progress.advance(create_task)

    return results


def clone_customers(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    progress: Progress,
    logger: CloneLogger,
) -> dict[str, Any]:
    """Clone all customers from source to destination account.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        progress: Rich progress instance
        logger: CloneLogger for incremental logging

    Returns:
        Results dict with created customers and failed items
    """
    results: dict[str, Any] = {
        "customers": [],
        "failed_customers": [],
    }

    # Fetch customers from source
    customers = fetch_source_customers(source_client, progress)

    if not customers:
        return results

    # Create customers in destination
    create_task = progress.add_task(
        f"[cyan]Creating customers in {dest_client.domain}...", total=len(customers)
    )

    for customer in customers:
        # Transform customer for creation
        transformed = transform_customer_for_creation(customer)
        source_id = customer.get("id")
        email = customer.get("email")
        name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()

        # Create in destination
        result = dest_client.create_customer(transformed)
        if result:
            new_id = result.get("id")
            results["customers"].append({
                "source_id": source_id,
                "new_id": new_id,
                "email": email,
                "name": name,
            })
            # Log success
            logger.log_success(
                entity_type="customers",
                source_id=source_id,
                new_id=new_id,
                status_code=dest_client.last_status_code or 201,
                identifier=email,
            )
        else:
            error_msg = dest_client.last_error or "Unknown error"
            results["failed_customers"].append({
                "email": email,
                "name": name,
                "reason": error_msg,
            })
            # Log failure with full details
            logger.log_failure(
                entity_type="customers",
                source_id=source_id,
                status_code=dest_client.last_status_code,
                error_message=error_msg,
                error_type=classify_error(dest_client.last_status_code, error_msg),
                request_payload=transformed,
                response_body=dest_client.last_response_body,
                identifier=email,
            )

        progress.advance(create_task)

    return results


def fetch_source_sales(
    client: XSeriesClient, progress: Progress
) -> list[dict]:
    """Fetch all sales from source account.

    Args:
        client: Source account client
        progress: Rich progress instance

    Returns:
        List of sale data
    """
    fetch_task = progress.add_task(f"[cyan]Fetching sales from {client.domain}...", total=None)
    sales, error = client.get_all_sales()
    if error:
        progress.update(fetch_task, description=f"[red]Error fetching sales: {error}[/red]")
        return []

    progress.update(
        fetch_task,
        description=f"[green]Found {len(sales)} sales in {client.domain}[/green]",
        total=len(sales),
        completed=len(sales),
    )
    return sales


def clone_sales(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    progress: Progress,
    logger: CloneLogger,
    product_mapping: dict[str, str],
    customer_mapping: dict[str, str],
) -> dict[str, Any]:
    """Clone all sales from source to destination account.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        progress: Rich progress instance
        logger: CloneLogger for incremental logging
        product_mapping: source_product_id -> dest_product_id from cloned products
        customer_mapping: source_customer_id -> dest_customer_id from cloned customers

    Returns:
        Results dict with created sales and failed items
    """
    results: dict[str, Any] = {
        "sales": [],
        "failed_sales": [],
    }

    # Fetch sales from source
    sales = fetch_source_sales(source_client, progress)

    if not sales:
        return results

    # Build mappings for registers, users, taxes, payment types
    console.print("[cyan]Building account mappings...[/cyan]")

    source_registers, _ = source_client.get_registers()
    dest_registers, _ = dest_client.get_registers()
    register_mapping = map_by_name(source_registers, dest_registers)

    source_users, _ = source_client.get_users()
    dest_users, _ = dest_client.get_users()
    user_mapping = map_by_name(source_users, dest_users)

    source_taxes, _ = source_client.get_taxes()
    dest_taxes, _ = dest_client.get_taxes()
    tax_mapping = map_by_name(source_taxes, dest_taxes)

    source_payment_types, _ = source_client.get_payment_types()
    dest_payment_types, _ = dest_client.get_payment_types()
    payment_type_mapping = map_by_name(source_payment_types, dest_payment_types)

    # Warn about missing mappings
    if not register_mapping:
        console.print(
            "[yellow]Warning: No matching registers found between accounts. "
            "Sales cannot be cloned without register mapping.[/yellow]"
        )
        return results

    if not user_mapping:
        console.print(
            "[yellow]Warning: No matching users found between accounts. "
            "Sales cannot be cloned without user mapping.[/yellow]"
        )
        return results

    # Create sales in destination
    create_task = progress.add_task(
        f"[cyan]Creating sales in {dest_client.domain}...", total=len(sales)
    )

    for sale in sales:
        source_id = sale.get("id")
        receipt_number = sale.get("receipt_number")

        # Transform sale for creation
        transformed = transform_sale_for_creation(
            sale,
            product_mapping,
            customer_mapping,
            register_mapping,
            user_mapping,
            tax_mapping,
            payment_type_mapping,
        )

        if transformed is None:
            error_msg = "Missing required mappings (register, user, or products)"
            results["failed_sales"].append({
                "source_id": source_id,
                "receipt_number": receipt_number,
                "reason": error_msg,
            })
            # Log transformation failure (not_found because mappings missing)
            logger.log_failure(
                entity_type="sales",
                source_id=source_id,
                status_code=None,
                error_message=error_msg,
                error_type="not_found",
                request_payload=None,
                response_body=None,
                identifier=receipt_number,
            )
            progress.advance(create_task)
            continue

        # Create in destination
        result = dest_client.create_sale(transformed)
        if result:
            new_id = result.get("id")
            results["sales"].append({
                "source_id": source_id,
                "new_id": new_id,
                "receipt_number": receipt_number,
                "total": sale.get("total_price"),
            })
            # Log success
            logger.log_success(
                entity_type="sales",
                source_id=source_id,
                new_id=new_id,
                status_code=dest_client.last_status_code or 201,
                identifier=receipt_number,
            )
        else:
            error_msg = dest_client.last_error or "Unknown error"
            results["failed_sales"].append({
                "source_id": source_id,
                "receipt_number": receipt_number,
                "reason": error_msg,
            })
            # Log failure with full details
            logger.log_failure(
                entity_type="sales",
                source_id=source_id,
                status_code=dest_client.last_status_code,
                error_message=error_msg,
                error_type=classify_error(dest_client.last_status_code, error_msg),
                request_payload=transformed,
                response_body=dest_client.last_response_body,
                identifier=receipt_number,
            )

        progress.advance(create_task)

    return results


def run_clone(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    clone_products_flag: bool = True,
    clone_customers_flag: bool = True,
    clone_sales_flag: bool = False,
    include_inventory: bool = True,
) -> dict[str, Any]:
    """Run the clone operation.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        clone_products_flag: Whether to clone products
        clone_customers_flag: Whether to clone customers
        clone_sales_flag: Whether to clone sales (requires products to be cloned)
        include_inventory: Whether to clone inventory (if cloning products)

    Returns:
        Combined results from all clone operations (from logger)
    """
    # Create logger immediately - file is written on init
    logger = CloneLogger(source_client.domain, dest_client.domain)
    console.print(f"[dim]Logging to: {logger.filepath}[/dim]\n")

    # Get destination tax setting
    dest_retailer = dest_client.get_retailer()
    # tax_exclusive=True means prices exclude tax, so tax_inclusive=False
    dest_tax_inclusive = not dest_retailer.get("tax_exclusive", False)

    # Track inventory counts separately (not per-operation)
    inventory_updated = 0
    inventory_failed = 0

    # Track mappings for dependent resources
    brand_mapping: dict[str, str] = {}
    supplier_mapping: dict[str, str] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,  # Hide completed tasks for cleaner output
    ) as progress:
        # Clone brands first (products depend on them)
        if clone_products_flag:
            console.print("\n[bold]Cloning brands...[/bold]")
            brand_mapping = clone_brands(source_client, dest_client, progress, logger)

            console.print("\n[bold]Cloning suppliers...[/bold]")
            supplier_mapping = clone_suppliers(source_client, dest_client, progress, logger)

            console.print("\n[bold]Cloning products...[/bold]")
            product_results = clone_products(
                source_client, dest_client, progress, logger,
                include_inventory, dest_tax_inclusive,
                brand_mapping, supplier_mapping
            )
            inventory_updated = product_results["inventory_updated"]
            inventory_failed = product_results["inventory_failed"]

        # Clone customers
        if clone_customers_flag:
            console.print("\n[bold]Cloning customers...[/bold]")
            clone_customers(source_client, dest_client, progress, logger)

        # Clone sales (requires products to be cloned first)
        if clone_sales_flag:
            if not clone_products_flag:
                console.print(
                    "[yellow]Warning: Sales cloning requires products to be cloned. "
                    "Skipping sales.[/yellow]"
                )
            else:
                console.print("\n[bold]Cloning sales...[/bold]")

                # Build product mapping from logger results
                logger_results = logger.get_results()
                product_mapping = {
                    p["source_id"]: p["new_id"]
                    for p in logger_results["products"]
                    if p.get("source_id") and p.get("new_id")
                }

                # Build customer mapping from logger results
                customer_mapping = {
                    c["source_id"]: c["new_id"]
                    for c in logger_results["customers"]
                    if c.get("source_id") and c.get("new_id")
                }

                clone_sales(
                    source_client, dest_client, progress, logger,
                    product_mapping, customer_mapping
                )

    # Set inventory counts and mark complete
    logger.set_inventory_counts(inventory_updated, inventory_failed)
    logger.complete()

    # Return results from logger (single source of truth)
    return logger.get_results()
