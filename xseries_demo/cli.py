"""Interactive CLI for X-Series Demo Data Generator."""

import re
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

console = Console()

BANNER = r"""
██╗  ██╗      ███████╗███████╗██████╗ ██╗███████╗███████╗
╚██╗██╔╝      ██╔════╝██╔════╝██╔══██╗██║██╔════╝██╔════╝
 ╚███╔╝ █████╗███████╗█████╗  ██████╔╝██║█████╗  ███████╗
 ██╔██╗ ╚════╝╚════██║██╔══╝  ██╔══██╗██║██╔══╝  ╚════██║
██╔╝ ██╗      ███████║███████╗██║  ██║██║███████╗███████║
╚═╝  ╚═╝      ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝
"""

VERTICALS = {
    "1": ("Apparel", "APP"),
    "2": ("Electronics", "ELE"),
    "3": ("Home & Kitchen", "HOM"),
    "4": ("Health & Beauty", "BTY"),
}


VERSION = "1.0.0"


def show_welcome_banner() -> None:
    """Display the welcome banner and description."""
    console.print(BANNER, style="bold cyan")
    console.print(f"Demo Data Generator [dim]v{VERSION}[/dim]", style="bold white")
    console.print("[dim]Created by Geanny Tavarez <geanny.tavarez@lightspeedhq.com>[/dim]")
    console.print("[dim]Last updated: 2026-01-05[/dim]\n")
    console.print(
        "Generate demo data (products, customers, and sales) for your\n"
        "X-Series retail store.\n"
    )


def show_warning() -> bool:
    """Display warning and get confirmation to proceed."""
    warning = Text()
    warning.append("WARNING\n\n", style="bold yellow")
    warning.append(
        "This creates real records in X-Series.\n"
        "Use only on demo/trial stores.\n"
        "Cleanup requires manual deletion."
    )
    console.print(Panel(warning, border_style="yellow"))
    console.print()
    return Confirm.ask("Continue?", default=True)


def prompt_domain() -> str:
    """Prompt for domain prefix and confirm."""
    console.print()
    console.print("[dim]The domain prefix is the part before .retail.lightspeed.app[/dim]")
    domain = Prompt.ask("Enter your X-Series domain prefix")

    console.print(f"\nStore URL: [cyan]https://{domain}.retail.lightspeed.app[/cyan]")
    console.print("[dim]Press Enter to confirm, or type N to re-enter[/dim]")
    response = Prompt.ask("Confirm?", default="y")
    if response.lower() == "n":
        return prompt_domain()

    return domain


def show_token_instructions(include_sales: bool = True) -> None:
    """Display instructions for obtaining a personal access token."""
    console.print()
    scopes = "customers:write, products:write"
    if include_sales:
        scopes += ", sales:write"
    instructions = (
        "[bold]Personal Access Token[/bold]\n\n"
        f"In X-Series: [cyan]Setup > Personal Tokens > New Token[/cyan]\n"
        f"Required scopes: [cyan]{scopes}[/cyan]\n\n"
        "[dim]Paste token and press Enter (input hidden for security).[/dim]"
    )
    console.print(Panel(instructions, border_style="blue"))


def validate_token(token: str) -> bool:
    """Validate basic token format.

    Tokens should be at least 32 characters and contain only
    alphanumeric characters, hyphens, underscores, and dots.
    """
    if len(token) < 32:
        return False
    return bool(re.match(r'^[\w\-\.]+$', token))


def prompt_token() -> str:
    """Prompt for personal access token (masked input)."""
    console.print()
    token = Prompt.ask("Enter your personal access token", password=True)

    if not token:
        console.print("[red]Token cannot be empty. Please try again.[/red]")
        return prompt_token()

    if not validate_token(token):
        console.print(
            "[red]Token appears to be invalid.[/red]\n"
            "[dim]Tokens should be at least 32 characters and contain only "
            "letters, numbers, hyphens, underscores, or dots.[/dim]"
        )
        return prompt_token()

    return token


def validate_connection(domain: str, token: str) -> tuple[bool, str, int, bool]:
    """Validate credentials with a spinner animation.

    Returns:
        (True, retailer_name, outlet_count, tax_inclusive) if valid
        (False, error_message, 0, False) if invalid
    """
    from xseries_demo.api.client import XSeriesClient
    from rich.status import Status

    console.print()
    outlet_count = 0
    tax_inclusive = True
    with Status("[bold cyan]Validating credentials...[/bold cyan]", spinner="dots", console=console):
        with XSeriesClient(domain, token) as client:
            valid, result, tax_exclusive = client.validate_credentials()
            if valid:
                outlets, _ = client.get_outlets()
                outlet_count = len(outlets)
                tax_inclusive = not tax_exclusive

    if valid:
        console.print(f"[green]✓ Connected: {result} ({domain})[/green]")
        if outlet_count:
            console.print(f"[green]  Outlets: {outlet_count}[/green]")
        tax_mode = "tax-inclusive" if tax_inclusive else "tax-exclusive"
        console.print(f"[green]  Pricing: {tax_mode}[/green]")
        return True, result, outlet_count, tax_inclusive
    else:
        console.print(f"[red]✗ {result}[/red]")
        return False, result, 0, False


VERTICAL_PRICES = {
    "1": "$15–$120",
    "2": "$50–$1,200",
    "3": "$10–$300",
    "4": "$8–$120",
}


def prompt_vertical() -> tuple[str, str]:
    """Prompt user to select a vertical pack."""
    console.print("\n[bold]Select a product vertical (determines names and price range):[/bold]\n")

    for key, (name, prefix) in VERTICALS.items():
        price_range = VERTICAL_PRICES.get(key, "")
        console.print(f"  [{key}] {name} [dim]{price_range}[/dim]")

    console.print()
    choice = Prompt.ask("Enter your choice", choices=list(VERTICALS.keys()), default="1")

    return VERTICALS[choice]


def prompt_tax_setting() -> bool:
    """Prompt for store tax setting (inclusive vs exclusive).

    Returns:
        True if tax-inclusive, False if tax-exclusive
    """
    console.print("\n[bold]How is your store configured for product prices?[/bold]\n")
    console.print("  [1] Tax-inclusive (display prices include tax)")
    console.print("  [2] Tax-exclusive (display prices exclude tax)")
    console.print("[dim]If unsure, check Setup > Taxes in X-Series.[/dim]")
    console.print()
    choice = Prompt.ask("Enter your choice", choices=["1", "2"], default="1")

    return choice == "1"


def prompt_add_inventory() -> bool:
    """Ask if user wants to add inventory to products."""
    console.print()
    console.print("[bold]Inventory Setup[/bold]")
    console.print("[dim]Sets 100 units per product across all outlets.[/dim]")
    return Confirm.ask("Add inventory?", default=True)


def prompt_create_sales() -> bool:
    """Ask if user wants to create demo sales."""
    console.print()
    console.print("[bold]Demo Sales[/bold]")
    console.print("[dim]Creates 50 sales spread across the past 90 days.[/dim]")
    console.print("[dim]Uses created products and customers.[/dim]")
    return Confirm.ask("Create demo sales?", default=True)


def prompt_create_variants(vertical_prefix: str) -> bool:
    """Ask if user wants to create variant products."""
    console.print()
    console.print("[bold]Variant Products[/bold]")
    console.print("[dim]Creates 20 product families with 5 variants each (100 variant SKUs).[/dim]")

    # Show vertical-appropriate attribute info
    if vertical_prefix == "APP":
        console.print("[dim]Variants by: Color + Size[/dim]")
    elif vertical_prefix == "BTY":
        console.print("[dim]Variants by: Shade[/dim]")
    else:
        console.print("[dim]Variants by: Color[/dim]")

    return Confirm.ask("Create variant products?", default=False)


def show_creation_summary(
    domain: str,
    vertical_name: str,
    retailer_name: str = "",
    create_sales: bool = False,
    add_inventory: bool = False,
    create_variants: bool = False,
) -> bool:
    """Show summary of what will be created and confirm."""
    console.print()

    # Calculate total records
    total_records = 100 + 50  # products + customers
    if create_sales:
        total_records += 50
    if create_variants:
        total_records += 100  # 20 families × 5 variants

    sales_line = "  Sales:     [cyan]50 (past 90 days)[/cyan]\n" if create_sales else ""
    inventory_line = "  Inventory: [cyan]100 qty per product[/cyan]\n" if add_inventory else ""
    variants_line = "  Variants:  [cyan]20 families × 5 colors = 100 SKUs[/cyan]\n" if create_variants else ""
    store_line = f"  Store:     [cyan]{retailer_name}[/cyan]\n" if retailer_name else ""

    summary = (
        f"[bold]Ready to create demo data[/bold]\n\n"
        f"{store_line}"
        f"  Domain:    [cyan]{domain}.retail.lightspeed.app[/cyan]\n"
        f"  Vertical:  [cyan]{vertical_name}[/cyan]\n\n"
        f"  Products:  [cyan]100[/cyan]\n"
        f"{inventory_line}"
        f"{variants_line}"
        f"  Customers: [cyan]50[/cyan]\n"
        f"{sales_line}\n"
        f"  [bold]Total records: {total_records}[/bold]\n"
        f"  [dim]Mode: LIVE (API writes enabled)[/dim]"
    )
    console.print(Panel(summary, border_style="green"))
    console.print()
    response = Prompt.ask("Type [bold]CREATE[/bold] to start (or press Enter to cancel)")
    return response.upper() == "CREATE"


def run_creation(
    domain: str,
    token: str,
    vertical: tuple[str, str],
    tax_inclusive: bool,
    dry_run: bool = False,
    add_inventory: bool = False,
    create_sales: bool = False,
    create_variants: bool = False,
    debug: bool = False,
) -> dict:
    """Execute the creation of products, customers, and optionally sales."""
    from xseries_demo.generators.customers import generate_customers
    from xseries_demo.generators.products import generate_products

    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

    vertical_name, vertical_prefix = vertical

    results = {
        "domain": domain,
        "vertical": vertical_name,
        "products": [],
        "customers": [],
    }

    if dry_run:
        console.print("\n[bold yellow]DRY RUN - No data will be created[/bold yellow]\n")

        products = list(generate_products(vertical_prefix, count=100, tax_inclusive=tax_inclusive))
        customers = list(generate_customers(count=50))

        console.print("[bold]Sample Products:[/bold]")
        for p in products[:3]:
            price = p.get("price_including_tax") or p.get("price_excluding_tax")
            console.print(f"  {p['sku']}: {p['name']} - ${price}")
        console.print(f"  ... and {len(products) - 3} more products\n")

        console.print("[bold]Sample Customers:[/bold]")
        for c in customers[:3]:
            console.print(f"  {c['first_name']} {c['last_name']} <{c['email']}>")
        console.print(f"  ... and {len(customers) - 3} more")

        results["dry_run"] = True
        results["products"] = [{"name": p["name"], "sku": p["sku"]} for p in products]
        results["customers"] = [{"name": f"{c['first_name']} {c['last_name']}", "email": c["email"]} for c in customers]
        return results

    # Real creation - import API client
    from xseries_demo.api.client import XSeriesClient
    from xseries_demo.output import write_output_file

    client = XSeriesClient(domain, token, debug=debug)

    # Track failed items with reasons
    failed_products: list[dict] = []
    failed_customers: list[dict] = []
    failed_inventory = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # Create products first
        product_task = progress.add_task("Creating products...", total=100)
        products = generate_products(vertical_prefix, count=100, tax_inclusive=tax_inclusive)

        for product in products:
            result = client.create_product(product)
            if result:
                price = product.get("price_including_tax") or product.get("price_excluding_tax")
                results["products"].append({
                    "sku": product["sku"],
                    "product_id": result["id"],
                    "name": product["name"],
                    "price": price,
                })
            else:
                failed_products.append({
                    "name": product["name"],
                    "sku": product["sku"],
                    "reason": client.last_error or "Unknown error",
                })
            progress.advance(product_task)

        # Add inventory if requested
        if add_inventory and results["products"]:
            # Fetch outlets
            outlets, outlets_error = client.get_outlets()
            if outlets_error:
                console.print(f"[yellow]Warning: {outlets_error}. Skipping inventory.[/yellow]")
            elif outlets:
                # Build inventory payload (100 qty per outlet)
                inventory_payload = [
                    {"outlet_id": outlet["id"], "current_amount": 100}
                    for outlet in outlets
                ]

                inventory_task = progress.add_task(
                    f"Adding inventory ({len(outlets)} outlet(s))...",
                    total=len(results["products"])
                )

                for product in results["products"]:
                    if not client.update_product_inventory(product["product_id"], inventory_payload):
                        failed_inventory += 1
                    progress.advance(inventory_task)

                results["inventory_added"] = True
                results["outlets_count"] = len(outlets)

        # Then create customers
        customer_task = progress.add_task("Creating customers...", total=50)
        customers = generate_customers(count=50)

        for customer in customers:
            result = client.create_customer(customer)
            if result:
                results["customers"].append({
                    "email": customer["email"],
                    "customer_id": result["id"],
                    "name": f"{customer['first_name']} {customer['last_name']}",
                })
            else:
                failed_customers.append({
                    "name": f"{customer['first_name']} {customer['last_name']}",
                    "email": customer["email"],
                    "reason": client.last_error or "Unknown error",
                })
            progress.advance(customer_task)

        # Create sales if requested
        failed_sales: list[dict] = []
        if create_sales and results["products"] and results["customers"]:
            from xseries_demo.generators.sales import generate_sales

            # Fetch required data for sales
            registers, reg_err = client.get_registers()
            users, user_err = client.get_users()
            payment_types, pt_err = client.get_payment_types()
            taxes, tax_err = client.get_taxes()

            if reg_err or user_err or pt_err or tax_err:
                error_msg = reg_err or user_err or pt_err or tax_err
                console.print(f"[yellow]Warning: {error_msg}. Skipping sales creation.[/yellow]")
            elif registers and users and payment_types and taxes:
                # Find Cash payment type
                cash_payment = next(
                    (pt for pt in payment_types if pt.get("name", "").lower() == "cash"),
                    payment_types[0] if payment_types else None
                )
                # Find No Tax or first available tax
                no_tax = next(
                    (t for t in taxes if "no tax" in t.get("name", "").lower()),
                    taxes[0] if taxes else None
                )

                if cash_payment and no_tax:
                    sales_task = progress.add_task("Creating sales...", total=50)
                    results["sales"] = []

                    sales = generate_sales(
                        products=results["products"],
                        customers=results["customers"],
                        user_id=users[0]["id"],
                        register_id=registers[0]["id"],
                        payment_type_id=cash_payment["id"],
                        tax_id=no_tax["id"],
                        count=50,
                    )

                    for sale_data in sales:
                        result = client.create_sale(sale_data)
                        if result:
                            results["sales"].append({
                                "sale_id": result.get("id"),
                                "invoice": result.get("invoice_number"),
                                "total": result.get("total_price"),
                                "date": result.get("sale_date"),
                            })
                        else:
                            failed_sales.append({
                                "date": sale_data.get("sale_date", "Unknown"),
                                "reason": client.last_error or "Unknown error",
                            })
                        progress.advance(sales_task)

        # Create variant products if requested
        failed_variants: list[dict] = []
        if create_variants:
            from xseries_demo.generators.variants import (
                generate_variant_products,
                get_or_create_variant_attributes,
            )

            # Get or create variant attributes (vertical-aware)
            attr_result = get_or_create_variant_attributes(client, vertical_prefix)
            if attr_result is None:
                console.print("[yellow]Warning: Could not create variant attributes. Skipping variants.[/yellow]")
            else:
                color_id, size_id = attr_result  # size_id is None for non-apparel
                results["variants"] = []

                variant_task = progress.add_task("Creating variant products...", total=20)

                variants = generate_variant_products(
                    prefix=vertical_prefix,
                    color_attribute_id=color_id,
                    size_attribute_id=size_id,  # None for non-apparel
                    count=20,
                )

                for variant_data in variants:
                    variant_ids = client.create_variant_product(variant_data["payload"])
                    if variant_ids:
                        # Update prices for each variant
                        for vid in variant_ids:
                            client.update_variant_price(
                                vid,
                                variant_data["base_price"],
                                tax_inclusive=tax_inclusive,
                            )

                        results["variants"].append({
                            "name": variant_data["name"],
                            "variant_count": len(variant_ids),
                            "variant_ids": variant_ids,
                            "price": variant_data["base_price"],
                        })
                    else:
                        failed_variants.append({
                            "name": variant_data["name"],
                            "reason": client.last_error or "Unknown error",
                        })
                    progress.advance(variant_task)

    # Track failures in results
    if failed_products or failed_customers or failed_inventory or failed_sales or failed_variants:
        results["failed"] = {
            "products": failed_products,
            "customers": failed_customers,
            "inventory": failed_inventory,
            "sales": failed_sales,
            "variants": failed_variants,
        }

    # Write output file
    output_file = write_output_file(results)
    results["output_file"] = output_file

    return results


def show_complete(results: dict) -> None:
    """Display completion summary."""
    console.print()

    if results.get("dry_run"):
        summary = (
            "[bold yellow]Dry run complete![/bold yellow]\n\n"
            "  Would create: [cyan]100 products, 50 customers[/cyan]\n"
            "  No API calls were made."
        )
        console.print(Panel(summary, border_style="yellow"))
        return

    products_created = len(results["products"])
    customers_created = len(results["customers"])
    sales_created = len(results.get("sales", []))
    variants_created = results.get("variants", [])
    total_variant_skus = sum(v.get("variant_count", 0) for v in variants_created)
    output_file = results.get("output_file", "demo-data.json")

    inventory_line = ""
    if results.get("inventory_added"):
        outlets_count = results.get("outlets_count", 1)
        inventory_line = f"\n  Inventory added:   [cyan]100 qty × {outlets_count} outlet(s)[/cyan]"

    sales_line = ""
    if sales_created:
        sales_line = f"\n  Sales created:     [cyan]{sales_created}[/cyan]"

    variants_line = ""
    if variants_created:
        variants_line = f"\n  Variants created:  [cyan]{len(variants_created)} families ({total_variant_skus} SKUs)[/cyan]"

    # Check for failures
    failed = results.get("failed", {})
    failed_products = failed.get("products", [])
    failed_customers = failed.get("customers", [])
    failed_inventory = failed.get("inventory", 0)
    failed_sales = failed.get("sales", [])
    failed_variants = failed.get("variants", [])

    has_failures = failed_products or failed_customers or failed_inventory or failed_sales or failed_variants

    # Build failure summary line
    failed_line = ""
    if has_failures:
        parts = []
        if failed_products:
            parts.append(f"{len(failed_products)} products")
        if failed_customers:
            parts.append(f"{len(failed_customers)} customers")
        if failed_inventory:
            parts.append(f"{failed_inventory} inventory updates")
        if failed_sales:
            parts.append(f"{len(failed_sales)} sales")
        if failed_variants:
            parts.append(f"{len(failed_variants)} variant families")
        if parts:
            failed_line = f"\n\n  [red]Failed: {', '.join(parts)}[/red]"

    border_style = "yellow" if has_failures else "green"
    status = "[bold yellow]Creation complete (with errors)[/bold yellow]" if has_failures else "[bold green]Creation complete![/bold green]"

    summary = (
        f"{status}\n\n"
        f"  Products created:  [cyan]{products_created}[/cyan]{inventory_line}{variants_line}\n"
        f"  Customers created: [cyan]{customers_created}[/cyan]{sales_line}\n\n"
        f"  Output file: [cyan]{output_file}[/cyan]{failed_line}"
    )
    console.print(Panel(summary, border_style=border_style))

    # Show detailed failure reasons if any
    if failed_products:
        console.print("\n[bold red]Failed Products:[/bold red]")
        for item in failed_products:
            console.print(f"  • {item['sku']}: {item['name']}")
            console.print(f"    [dim]{item['reason']}[/dim]")

    if failed_customers:
        console.print("\n[bold red]Failed Customers:[/bold red]")
        for item in failed_customers:
            console.print(f"  • {item['name']} <{item['email']}>")
            console.print(f"    [dim]{item['reason']}[/dim]")


def prompt_next_action() -> str:
    """Ask user what to do after completion.

    Returns:
        'vertical' to import another vertical
        'store' to switch to another store
        'exit' to quit
    """
    console.print()
    console.print("[bold]What would you like to do next?[/bold]\n")
    console.print("  [1] Import another vertical (same store)")
    console.print("  [2] Switch to another store")
    console.print("  [3] Exit")
    console.print()
    choice = Prompt.ask("Enter your choice", choices=["1", "2", "3"], default="3")

    if choice == "1":
        return "vertical"
    elif choice == "2":
        return "store"
    else:
        return "exit"


# ============================================================================
# Clone Account Feature
# ============================================================================


def prompt_main_menu() -> str:
    """Prompt user to choose between Generate and Clone modes.

    Returns:
        'generate' or 'clone'
    """
    console.print()
    console.print("[bold]What would you like to do?[/bold]\n")
    console.print("  [1] Generate Demo Data (create random products, customers, sales)")
    console.print("  [2] Clone Account Data (copy products/customers from another account)")
    console.print()
    choice = Prompt.ask("Enter your choice", choices=["1", "2"], default="1")

    return "generate" if choice == "1" else "clone"


def prompt_domain_with_label(label: str) -> str:
    """Prompt for domain prefix with a custom label."""
    console.print()
    console.print(f"[bold]{label}[/bold]")
    console.print("[dim]The domain prefix is the part before .retail.lightspeed.app[/dim]")
    domain = Prompt.ask("Enter the X-Series domain prefix")

    console.print(f"\nStore URL: [cyan]https://{domain}.retail.lightspeed.app[/cyan]")
    console.print("[dim]Press Enter to confirm, or type N to re-enter[/dim]")
    response = Prompt.ask("Confirm?", default="y")
    if response.lower() == "n":
        return prompt_domain_with_label(label)

    return domain


def prompt_clone_options() -> dict[str, bool]:
    """Prompt user to select what to clone.

    Returns:
        Dict with 'products' and 'customers' boolean flags
    """
    console.print()
    console.print("[bold]What would you like to clone?[/bold]\n")
    console.print("[dim]Select one or more options:[/dim]")

    clone_products = Confirm.ask("  Clone products (with inventory)?", default=True)
    clone_customers = Confirm.ask("  Clone customers?", default=True)

    if not clone_products and not clone_customers:
        console.print("[yellow]You must select at least one option to clone.[/yellow]")
        return prompt_clone_options()

    return {
        "products": clone_products,
        "customers": clone_customers,
    }


def show_clone_summary(
    source_domain: str,
    source_name: str,
    dest_domain: str,
    dest_name: str,
    options: dict[str, bool],
) -> bool:
    """Show clone summary and get confirmation.

    Returns:
        True if user confirms with 'CLONE'
    """
    console.print()

    items = []
    if options.get("products"):
        items.append("Products (with inventory)")
    if options.get("customers"):
        items.append("Customers")

    items_str = ", ".join(items)

    summary = (
        f"[bold]Ready to clone account data[/bold]\n\n"
        f"  Source:      [cyan]{source_name}[/cyan] ({source_domain})\n"
        f"  Destination: [cyan]{dest_name}[/cyan] ({dest_domain})\n\n"
        f"  Cloning:     [cyan]{items_str}[/cyan]\n\n"
        f"  [yellow]Warning: This will create new records in the destination account.[/yellow]\n"
        f"  [dim]Existing records with duplicate SKUs/emails may fail.[/dim]"
    )
    console.print(Panel(summary, border_style="yellow"))
    console.print()
    response = Prompt.ask("Type [bold]CLONE[/bold] to start (or press Enter to cancel)")
    return response.upper() == "CLONE"


def show_clone_complete(results: dict[str, Any]) -> None:
    """Display clone completion summary."""
    console.print()

    products_cloned = len(results.get("products", []))
    customers_cloned = len(results.get("customers", []))
    failed_products = results.get("failed_products", [])
    failed_customers = results.get("failed_customers", [])
    inventory_updated = results.get("inventory_updated", 0)
    inventory_failed = results.get("inventory_failed", 0)
    output_file = results.get("output_file", "clone-results.json")

    has_failures = failed_products or failed_customers

    # Build summary lines
    product_line = ""
    if results.get("products") is not None:
        inv_info = ""
        if inventory_updated > 0:
            inv_info = f" (inventory: {inventory_updated}"
            if inventory_failed > 0:
                inv_info += f", {inventory_failed} failed"
            inv_info += ")"
        product_line = f"  Products cloned:  [cyan]{products_cloned}[/cyan]{inv_info}\n"

    customer_line = ""
    if results.get("customers") is not None:
        customer_line = f"  Customers cloned: [cyan]{customers_cloned}[/cyan]\n"

    failed_line = ""
    if has_failures:
        parts = []
        if failed_products:
            parts.append(f"{len(failed_products)} products")
        if failed_customers:
            parts.append(f"{len(failed_customers)} customers")
        failed_line = f"\n  [red]Failed: {', '.join(parts)}[/red]"

    border_style = "yellow" if has_failures else "green"
    status = "[bold yellow]Clone complete (with errors)[/bold yellow]" if has_failures else "[bold green]Clone complete![/bold green]"

    summary = (
        f"{status}\n\n"
        f"  Source:           [cyan]{results.get('source_domain')}[/cyan]\n"
        f"  Destination:      [cyan]{results.get('dest_domain')}[/cyan]\n\n"
        f"{product_line}"
        f"{customer_line}\n"
        f"  Output file: [cyan]{output_file}[/cyan]{failed_line}"
    )
    console.print(Panel(summary, border_style=border_style))

    # Show detailed failure reasons if any
    if failed_products:
        console.print("\n[bold red]Failed Products:[/bold red]")
        for item in failed_products[:10]:  # Limit to first 10
            console.print(f"  • {item.get('sku', 'N/A')}: {item.get('name', 'N/A')}")
            console.print(f"    [dim]{item.get('reason', 'Unknown error')}[/dim]")
        if len(failed_products) > 10:
            console.print(f"  [dim]... and {len(failed_products) - 10} more[/dim]")

    if failed_customers:
        console.print("\n[bold red]Failed Customers:[/bold red]")
        for item in failed_customers[:10]:  # Limit to first 10
            console.print(f"  • {item.get('name', 'N/A')} <{item.get('email', 'N/A')}>")
            console.print(f"    [dim]{item.get('reason', 'Unknown error')}[/dim]")
        if len(failed_customers) > 10:
            console.print(f"  [dim]... and {len(failed_customers) - 10} more[/dim]")


def run_clone_wizard(debug: bool = False) -> None:
    """Run the clone account wizard."""
    from xseries_demo.api.client import XSeriesClient
    from xseries_demo.clone import run_clone
    from xseries_demo.output import write_clone_output_file

    # === SOURCE ACCOUNT ===
    console.print("\n[bold cyan]━━━ SOURCE ACCOUNT ━━━[/bold cyan]")
    source_domain = prompt_domain_with_label("Source Account (copy FROM)")

    show_token_instructions(include_sales=False)
    console.print("[dim]Required scopes: products:read, customers:read[/dim]")

    # Validate source credentials
    while True:
        source_token = prompt_token()
        valid, source_name, _, _ = validate_connection(source_domain, source_token)
        if valid:
            break
        console.print("\n[yellow]Please re-enter your source credentials.[/yellow]")
        if not Confirm.ask("Try again?", default=True):
            console.print("\n[yellow]Aborted.[/yellow]")
            return
        source_domain = prompt_domain_with_label("Source Account (copy FROM)")
        show_token_instructions(include_sales=False)

    # === DESTINATION ACCOUNT ===
    console.print("\n[bold cyan]━━━ DESTINATION ACCOUNT ━━━[/bold cyan]")
    dest_domain = prompt_domain_with_label("Destination Account (copy TO)")

    show_token_instructions(include_sales=False)
    console.print("[dim]Required scopes: products:write, customers:write[/dim]")

    # Validate destination credentials
    while True:
        dest_token = prompt_token()
        valid, dest_name, _, _ = validate_connection(dest_domain, dest_token)
        if valid:
            break
        console.print("\n[yellow]Please re-enter your destination credentials.[/yellow]")
        if not Confirm.ask("Try again?", default=True):
            console.print("\n[yellow]Aborted.[/yellow]")
            return
        dest_domain = prompt_domain_with_label("Destination Account (copy TO)")
        show_token_instructions(include_sales=False)

    # Check that source and destination are different
    if source_domain.lower() == dest_domain.lower():
        console.print("\n[red]Error: Source and destination accounts must be different.[/red]")
        return

    # === CLONE OPTIONS ===
    options = prompt_clone_options()

    # === CONFIRMATION ===
    if not show_clone_summary(source_domain, source_name, dest_domain, dest_name, options):
        console.print("\n[yellow]Aborted.[/yellow]")
        return

    # === EXECUTE CLONE ===
    console.print()
    with XSeriesClient(source_domain, source_token, debug=debug) as source_client:
        with XSeriesClient(dest_domain, dest_token, debug=debug) as dest_client:
            results = run_clone(
                source_client=source_client,
                dest_client=dest_client,
                clone_products_flag=options["products"],
                clone_customers_flag=options["customers"],
                include_inventory=options["products"],  # Include inventory if cloning products
            )

    # Write output file
    output_file = write_clone_output_file(results)
    results["output_file"] = output_file

    # Show completion
    show_clone_complete(results)


@click.command()
@click.option("--dry-run", is_flag=True, help="Preview generated data without creating anything")
@click.option("--debug", is_flag=True, help="Enable debug logging of API requests/responses")
def main(dry_run: bool, debug: bool) -> None:
    """X-Series Demo Data Generator - Create demo customers and products."""
    try:
        show_welcome_banner()

        if not dry_run:
            if not show_warning():
                console.print("\n[yellow]Aborted.[/yellow]")
                raise SystemExit(0)

            # Show main menu (only in non-dry-run mode)
            mode = prompt_main_menu()

            if mode == "clone":
                run_clone_wizard(debug=debug)
                console.print("\n[green]Done. Goodbye![/green]")
                raise SystemExit(0)

        # Generate mode (original flow)
        # Outer loop for switching stores
        while True:
            domain = prompt_domain()

            retailer_name = ""
            tax_inclusive = True  # Default for dry-run
            if not dry_run:
                show_token_instructions()

                # Loop until valid credentials or user gives up
                while True:
                    token = prompt_token()
                    valid, retailer_name, _, tax_inclusive = validate_connection(domain, token)
                    if valid:
                        break
                    console.print("\n[yellow]Please re-enter your credentials to continue.[/yellow]")
                    if not Confirm.ask("Try again?", default=True):
                        console.print("\n[yellow]Aborted.[/yellow]")
                        raise SystemExit(0)
                    # Re-prompt for both domain and token
                    domain = prompt_domain()
                    show_token_instructions()
            else:
                token = ""  # Not needed for dry run
                # For dry-run, ask for tax setting since we can't detect it
                tax_inclusive = prompt_tax_setting()

            # Inner loop for importing multiple verticals to same store
            while True:
                vertical = prompt_vertical()
                vertical_name, vertical_prefix = vertical

                add_inventory = False
                create_sales = False
                create_variants = False
                if not dry_run:
                    add_inventory = prompt_add_inventory()
                    create_variants = prompt_create_variants(vertical_prefix)
                    create_sales = prompt_create_sales()

                if not dry_run:
                    if not show_creation_summary(
                        domain, vertical_name, retailer_name, create_sales, add_inventory, create_variants
                    ):
                        console.print("\n[yellow]Aborted.[/yellow]")
                        raise SystemExit(0)

                results = run_creation(
                    domain, token, vertical, tax_inclusive,
                    dry_run, add_inventory, create_sales, create_variants, debug
                )
                show_complete(results)

                # For dry-run, just exit after one run
                if dry_run:
                    raise SystemExit(0)

                # Ask what to do next
                next_action = prompt_next_action()

                if next_action == "vertical":
                    # Continue inner loop - import another vertical to same store
                    console.print(f"\n[cyan]Continuing with store: {retailer_name}[/cyan]")
                    continue
                elif next_action == "store":
                    # Break inner loop, continue outer loop - switch stores
                    console.print("\n[cyan]Switching to another store...[/cyan]")
                    break
                else:
                    # Exit
                    console.print("\n[green]Done. Goodbye![/green]")
                    raise SystemExit(0)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user.[/yellow]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
