"""Clone functionality to copy data between X-Series accounts."""

from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from xseries_demo.api.client import XSeriesClient

console = Console()


# Fields to strip when transforming products for creation
PRODUCT_STRIP_FIELDS = {
    "id",
    "version",
    "created_at",
    "updated_at",
    "deleted_at",
    "source_id",
    "variant_source_id",
    "variant_parent_id",
    "image_thumbnail_url",
    "image_large_url",
    "images",
    "inventory",  # Handled separately
    "has_variants",
    "variant_count",
    "variant_products",
    "source",
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


def transform_product_for_creation(product: dict) -> dict:
    """Transform a product from source to be created in destination.

    Strips IDs and system-managed fields, keeping only data needed for creation.

    Args:
        product: Full product data from source account

    Returns:
        Product payload suitable for POST /products
    """
    transformed = {}

    for key, value in product.items():
        if key in PRODUCT_STRIP_FIELDS:
            continue
        if value is None:
            continue
        transformed[key] = value

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
    fetch_task = progress.add_task("[cyan]Fetching products...", total=None)
    products, error = client.get_all_products()
    if error:
        console.print(f"[red]Error fetching products: {error}[/red]")
        return [], []

    progress.update(fetch_task, total=len(products), completed=len(products))
    console.print(f"[green]Found {len(products)} products[/green]")

    # Fetch detailed product info and inventory
    products_with_inventory = []
    inventory_data = []

    if include_inventory and products:
        inv_task = progress.add_task(
            "[cyan]Fetching inventory...", total=len(products)
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
    fetch_task = progress.add_task("[cyan]Fetching customers...", total=None)
    customers, error = client.get_all_customers()
    if error:
        console.print(f"[red]Error fetching customers: {error}[/red]")
        return []

    progress.update(fetch_task, total=len(customers), completed=len(customers))
    console.print(f"[green]Found {len(customers)} customers[/green]")
    return customers


def clone_products(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    progress: Progress,
    include_inventory: bool = True,
) -> dict[str, Any]:
    """Clone all products from source to destination account.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        progress: Rich progress instance
        include_inventory: Whether to clone inventory data

    Returns:
        Results dict with created products and failed items
    """
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
        "[cyan]Creating products...", total=len(products)
    )

    # Build SKU -> inventory lookup
    inventory_by_sku: dict[str, list[dict]] = {}
    for inv_record in inventory_data:
        sku = inv_record.get("sku")
        if sku:
            inventory_by_sku[sku] = inv_record.get("inventory", [])

    for product in products:
        # Transform product for creation
        transformed = transform_product_for_creation(product)

        # Create in destination
        result = dest_client.create_product(transformed)
        if result:
            new_id = result.get("id")
            results["products"].append({
                "source_id": product.get("id"),
                "new_id": new_id,
                "sku": product.get("sku"),
                "name": product.get("name"),
            })

            # Update inventory if we have it
            sku = product.get("sku")
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
                    else:
                        results["inventory_failed"] += 1
        else:
            results["failed_products"].append({
                "sku": product.get("sku"),
                "name": product.get("name"),
                "reason": dest_client.last_error or "Unknown error",
            })

        progress.advance(create_task)

    return results


def clone_customers(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    progress: Progress,
) -> dict[str, Any]:
    """Clone all customers from source to destination account.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        progress: Rich progress instance

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
        "[cyan]Creating customers...", total=len(customers)
    )

    for customer in customers:
        # Transform customer for creation
        transformed = transform_customer_for_creation(customer)

        # Create in destination
        result = dest_client.create_customer(transformed)
        if result:
            results["customers"].append({
                "source_id": customer.get("id"),
                "new_id": result.get("id"),
                "email": customer.get("email"),
                "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            })
        else:
            results["failed_customers"].append({
                "email": customer.get("email"),
                "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                "reason": dest_client.last_error or "Unknown error",
            })

        progress.advance(create_task)

    return results


def run_clone(
    source_client: XSeriesClient,
    dest_client: XSeriesClient,
    clone_products_flag: bool = True,
    clone_customers_flag: bool = True,
    include_inventory: bool = True,
) -> dict[str, Any]:
    """Run the clone operation.

    Args:
        source_client: Client for source account
        dest_client: Client for destination account
        clone_products_flag: Whether to clone products
        clone_customers_flag: Whether to clone customers
        include_inventory: Whether to clone inventory (if cloning products)

    Returns:
        Combined results from all clone operations
    """
    results: dict[str, Any] = {
        "source_domain": source_client.domain,
        "dest_domain": dest_client.domain,
        "products": [],
        "failed_products": [],
        "customers": [],
        "failed_customers": [],
        "inventory_updated": 0,
        "inventory_failed": 0,
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # Clone products
        if clone_products_flag:
            console.print("\n[bold]Cloning products...[/bold]")
            product_results = clone_products(
                source_client, dest_client, progress, include_inventory
            )
            results["products"] = product_results["products"]
            results["failed_products"] = product_results["failed_products"]
            results["inventory_updated"] = product_results["inventory_updated"]
            results["inventory_failed"] = product_results["inventory_failed"]

        # Clone customers
        if clone_customers_flag:
            console.print("\n[bold]Cloning customers...[/bold]")
            customer_results = clone_customers(source_client, dest_client, progress)
            results["customers"] = customer_results["customers"]
            results["failed_customers"] = customer_results["failed_customers"]

    return results
