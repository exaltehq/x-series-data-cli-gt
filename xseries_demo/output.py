"""Output file generation for demo data results."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Set up module logger
logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False, domain: str | None = None) -> Path | None:
    """Configure logging for the application.

    Args:
        debug: If True, enable debug-level file logging
        domain: Domain prefix for log filename (optional)

    Returns:
        Path to debug log file if created, None otherwise
    """
    # Base logger for xseries_demo package
    root_logger = logging.getLogger("xseries_demo")

    if debug:
        logs_dir = get_logs_dir()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")

        if domain:
            log_filename = f"debug-{domain}-{timestamp}.log"
        else:
            log_filename = f"debug-{timestamp}.log"

        log_path = logs_dir / log_filename

        # File handler for debug output
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.DEBUG)

        return log_path

    return None


def get_logs_dir() -> Path:
    """Get or create the logs directory.

    Returns:
        Path to the logs directory
    """
    logs_dir = Path.cwd() / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


class CloneLogger:
    """Incremental logger for clone operations.

    Creates a log file immediately and writes entries as operations complete.
    - Success (200/201): Logs minimal info (status, IDs)
    - Failure (4xx/5xx): Logs full payload and response for debugging
    """

    def __init__(
        self,
        source_domain: str,
        dest_domain: str,
        output_dir: Path | None = None,
    ):
        """Initialize logger and create the log file.

        Args:
            source_domain: Source account domain prefix
            dest_domain: Destination account domain prefix
            output_dir: Directory for log file (defaults to logs/)
        """
        if output_dir is None:
            output_dir = get_logs_dir()

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        # Format: clone-{source}-to-{dest}-{timestamp}.json
        filename = f"clone-{source_domain}-to-{dest_domain}-{timestamp}.json"
        self.filepath = output_dir / filename
        self.source_domain = source_domain
        self.dest_domain = dest_domain

        # Initialize log structure
        self._data: dict[str, Any] = {
            "metadata": {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "source_domain": source_domain,
                "dest_domain": dest_domain,
                "status": "in_progress",
            },
            "summary": {
                "brands": {"success": 0, "failed": 0},
                "suppliers": {"success": 0, "failed": 0},
                "products": {"success": 0, "failed": 0},
                "customers": {"success": 0, "failed": 0},
                "sales": {"success": 0, "failed": 0},
                "inventory": {"success": 0, "failed": 0},
            },
            "error_summary": {
                "brands": {},
                "suppliers": {},
                "products": {},
                "customers": {},
                "sales": {},
            },
            "results": {
                "brands": [],
                "suppliers": [],
                "products": [],
                "customers": [],
                "sales": [],
                "failed_brands": [],
                "failed_suppliers": [],
                "failed_products": [],
                "failed_customers": [],
                "failed_sales": [],
            },
            "operations": [],
        }
        self._write()

    def _write(self) -> None:
        """Write current state to file."""
        with open(self.filepath, "w") as f:
            json.dump(self._data, f, indent=2)

    def log_success(
        self,
        entity_type: str,
        source_id: str | None,
        new_id: str | None,
        status_code: int,
        identifier: str | None = None,
        extra_data: dict | None = None,
    ) -> None:
        """Log a successful operation.

        Args:
            entity_type: Type of entity (product, customer, sale, inventory)
            source_id: ID in source account
            new_id: ID in destination account
            status_code: HTTP status code (200 or 201)
            identifier: Human-readable identifier (SKU, email, etc.)
            extra_data: Additional data to include in results (name, etc.)
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "entity_type": entity_type,
            "status_code": status_code,
            "source_id": source_id,
            "new_id": new_id,
        }
        if identifier:
            entry["identifier"] = identifier

        self._data["operations"].append(entry)
        self._data["summary"][entity_type]["success"] += 1

        # Add to results array (skip inventory - it's just a count)
        if entity_type in ("brands", "suppliers", "products", "customers", "sales"):
            result_entry = {"source_id": source_id, "new_id": new_id}
            if identifier:
                result_entry["identifier"] = identifier
            if extra_data:
                result_entry.update(extra_data)
            self._data["results"][entity_type].append(result_entry)

        self._write()

    def log_failure(
        self,
        entity_type: str,
        source_id: str | None,
        status_code: int | None,
        error_message: str,
        error_type: str = "unknown",
        request_payload: dict | None = None,
        response_body: dict | str | None = None,
        identifier: str | None = None,
        extra_data: dict | None = None,
    ) -> None:
        """Log a failed operation with full details for debugging.

        Args:
            entity_type: Type of entity (product, customer, sale, inventory)
            source_id: ID in source account
            status_code: HTTP status code (4xx, 5xx)
            error_message: Error message
            error_type: Category of error (duplicate, validation, permission, etc.)
            request_payload: Full request payload that was sent
            response_body: Full response body from API
            identifier: Human-readable identifier (SKU, email, etc.)
            extra_data: Additional data to include in results (name, etc.)
        """
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "entity_type": entity_type,
            "status_code": status_code,
            "source_id": source_id,
            "error": error_message,
            "error_type": error_type,
        }
        if identifier:
            entry["identifier"] = identifier
        if request_payload:
            entry["request_payload"] = request_payload
        if response_body:
            entry["response_body"] = response_body

        self._data["operations"].append(entry)
        self._data["summary"][entity_type]["failed"] += 1

        # Track error counts by type
        if entity_type in ("brands", "suppliers", "products", "customers", "sales"):
            error_counts = self._data["error_summary"][entity_type]
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

            # Add to failed results array
            failed_key = f"failed_{entity_type}"
            result_entry: dict[str, Any] = {
                "reason": error_message,
                "error_type": error_type,
            }
            if identifier:
                result_entry["identifier"] = identifier
            if extra_data:
                result_entry.update(extra_data)
            self._data["results"][failed_key].append(result_entry)

        self._write()

    def set_inventory_counts(self, updated: int, failed: int) -> None:
        """Set inventory update counts.

        Args:
            updated: Number of inventory updates that succeeded
            failed: Number of inventory updates that failed
        """
        self._data["summary"]["inventory"]["success"] = updated
        self._data["summary"]["inventory"]["failed"] = failed
        self._write()

    def get_error_summary(self) -> dict[str, dict[str, int]]:
        """Get error counts by type for each entity.

        Returns:
            Dict mapping entity_type -> error_type -> count
            Example: {"products": {"duplicate": 5, "validation": 2}}
        """
        return self._data["error_summary"]

    def get_results(self) -> dict[str, Any]:
        """Get the current results for display.

        Returns:
            Dict with products, customers, sales, failed_*, counts, and error_summary
        """
        return {
            "source_domain": self.source_domain,
            "dest_domain": self.dest_domain,
            "products": self._data["results"]["products"],
            "customers": self._data["results"]["customers"],
            "sales": self._data["results"]["sales"],
            "failed_products": self._data["results"]["failed_products"],
            "failed_customers": self._data["results"]["failed_customers"],
            "failed_sales": self._data["results"]["failed_sales"],
            "inventory_updated": self._data["summary"]["inventory"]["success"],
            "inventory_failed": self._data["summary"]["inventory"]["failed"],
            "error_summary": self._data["error_summary"],
            "log_file": str(self.filepath),
        }

    def complete(self, status: str = "completed") -> str:
        """Mark the clone operation as complete.

        Args:
            status: Final status (completed, failed, cancelled)

        Returns:
            Path to the log file
        """
        self._data["metadata"]["completed_at"] = datetime.now(timezone.utc).isoformat()
        self._data["metadata"]["status"] = status
        self._write()
        return str(self.filepath)


def write_output_file(results: dict, output_dir: Path | None = None) -> str:
    """Write the results to a JSON mapping file.

    Args:
        results: Dictionary containing created products and customers
        output_dir: Directory to write the file (defaults to logs/)

    Returns:
        Path to the created output file
    """
    if output_dir is None:
        output_dir = get_logs_dir()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    domain = results.get("domain", "unknown")
    # Format: demo-data-{domain}-{timestamp}.json
    filename = f"demo-data-{domain}-{timestamp}.json"
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


