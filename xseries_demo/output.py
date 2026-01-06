"""Output file generation for demo data results."""

import json
from datetime import datetime, timezone
from pathlib import Path


def write_output_file(results: dict, output_dir: Path | None = None) -> str:
    """Write the results to a JSON mapping file.

    Args:
        results: Dictionary containing created products and customers
        output_dir: Directory to write the file (defaults to current directory)

    Returns:
        Path to the created output file
    """
    if output_dir is None:
        output_dir = Path.cwd()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    filename = f"demo-data-{timestamp}.json"
    filepath = output_dir / filename

    variants = results.get("variants", [])
    total_variant_skus = sum(v.get("variant_count", 0) for v in variants)

    output = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "domain": results.get("domain", ""),
            "vertical": results.get("vertical", ""),
            "counts": {
                "products": len(results.get("products", [])),
                "customers": len(results.get("customers", [])),
                "sales": len(results.get("sales", [])),
                "variant_families": len(variants),
                "variant_skus": total_variant_skus,
            },
        },
        "products": results.get("products", []),
        "customers": results.get("customers", []),
        "sales": results.get("sales", []),
        "variants": variants,
    }

    try:
        with open(filepath, "w") as f:
            json.dump(output, f, indent=2)
    except PermissionError:
        raise RuntimeError(
            f"Cannot write to {filepath}: Permission denied. "
            "Try running from a directory where you have write access."
        )
    except OSError as e:
        raise RuntimeError(f"Failed to write output file {filepath}: {e}")

    return str(filepath)


def write_clone_output_file(results: dict, output_dir: Path | None = None) -> str:
    """Write the clone results to a JSON mapping file.

    Args:
        results: Dictionary containing cloned products and customers
        output_dir: Directory to write the file (defaults to current directory)

    Returns:
        Path to the created output file
    """
    if output_dir is None:
        output_dir = Path.cwd()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    filename = f"clone-results-{timestamp}.json"
    filepath = output_dir / filename

    output = {
        "metadata": {
            "cloned_at": datetime.now(timezone.utc).isoformat(),
            "source_domain": results.get("source_domain", ""),
            "dest_domain": results.get("dest_domain", ""),
            "counts": {
                "products_cloned": len(results.get("products", [])),
                "products_failed": len(results.get("failed_products", [])),
                "customers_cloned": len(results.get("customers", [])),
                "customers_failed": len(results.get("failed_customers", [])),
                "inventory_updated": results.get("inventory_updated", 0),
                "inventory_failed": results.get("inventory_failed", 0),
            },
        },
        "products": results.get("products", []),
        "customers": results.get("customers", []),
        "failed_products": results.get("failed_products", []),
        "failed_customers": results.get("failed_customers", []),
    }

    try:
        with open(filepath, "w") as f:
            json.dump(output, f, indent=2)
    except PermissionError:
        raise RuntimeError(
            f"Cannot write to {filepath}: Permission denied. "
            "Try running from a directory where you have write access."
        )
    except OSError as e:
        raise RuntimeError(f"Failed to write output file {filepath}: {e}")

    return str(filepath)
