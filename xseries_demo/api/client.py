"""HTTP client for X-Series API with rate limiting and retries."""

import json
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from rich.console import Console

console = Console()


class RateLimitError(Exception):
    """Raised when rate limit is hit."""

    def __init__(self, retry_after: datetime | None = None):
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded")


class APIError(Exception):
    """Raised for API errors."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class XSeriesClient:
    """Client for X-Series API with rate limiting and retry support."""

    BASE_URL = "https://{domain}.retail.lightspeed.app/api/2.0"

    def __init__(self, domain: str, token: str, debug: bool = False):
        self.domain = domain
        self.token = token
        self.debug = debug
        self.base_url = self.BASE_URL.format(domain=domain)
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self.rate_limit_remaining: int | None = None
        self.rate_limit_total: int | None = None
        self.last_error: str | None = None  # Track last error for reporting

    def _log_debug(self, method: str, url: str, request_body: dict | None, response: httpx.Response) -> None:
        """Log request/response details for debugging."""
        if not self.debug:
            return
        console.print(f"\n[dim]─── DEBUG {method} {url} ───[/dim]")
        if request_body:
            console.print(f"[dim]Request: {json.dumps(request_body, indent=2)}[/dim]")
        console.print(f"[dim]Status: {response.status_code}[/dim]")
        try:
            resp_json = response.json()
            console.print(f"[dim]Response: {json.dumps(resp_json, indent=2)}[/dim]")
        except (ValueError, json.JSONDecodeError):
            console.print(f"[dim]Response: {response.text[:500]}[/dim]")
        console.print("[dim]───────────────────────────[/dim]\n")

    def _handle_response(self, response: httpx.Response) -> dict | None:
        """Handle API response, including rate limit headers."""
        # Update rate limit info from headers
        if "X-RateLimit-Remaining" in response.headers:
            self.rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        if "X-RateLimit-Limit" in response.headers:
            self.rate_limit_total = int(response.headers["X-RateLimit-Limit"])

        # Handle rate limiting
        if response.status_code == 429:
            retry_after = None
            if "Retry-After" in response.headers:
                try:
                    retry_after = parsedate_to_datetime(response.headers["Retry-After"])
                except (ValueError, TypeError):
                    pass
            raise RateLimitError(retry_after)

        # Handle auth errors
        if response.status_code == 401:
            raise APIError(401, "Invalid or expired token")

        if response.status_code == 403:
            raise APIError(403, "Insufficient permissions - check token scopes")

        if response.status_code == 404:
            raise APIError(404, f"Invalid domain: {self.domain}")

        # Handle server errors
        if response.status_code >= 500:
            raise APIError(response.status_code, "Server error - please try again")

        # Handle client errors
        if response.status_code >= 400:
            try:
                error_data = response.json()
                # Extract error message - APIs may use different fields
                message = error_data.get("error", "")
                # Check for detailed validation errors (API uses 'details' or 'fields')
                details = error_data.get("details") or error_data.get("fields")
                if details:
                    if isinstance(details, list):
                        # Join multiple validation errors
                        detail_msgs = [str(d) for d in details]
                        message = f"{message}: {'; '.join(detail_msgs)}" if message else "; ".join(detail_msgs)
                    elif isinstance(details, dict):
                        # Field-level errors like {"name": "Already exists"}
                        # Filter out internal fields like 'name_existing_id'
                        field_errors = [
                            f"{k}: {v}" for k, v in details.items()
                            if not k.endswith("_id")
                        ]
                        if field_errors:
                            message = f"{message}: {'; '.join(field_errors)}" if message else "; ".join(field_errors)
                    else:
                        message = f"{message}: {details}" if message else str(details)
                if not message:
                    message = response.text
            except (ValueError, json.JSONDecodeError):
                message = response.text
            raise APIError(response.status_code, message)

        # Success
        if response.status_code in (200, 201):
            # Return empty dict for responses with no body (e.g., v2.1 PUT)
            if not response.content:
                return {}
            return response.json()

        return None

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        json_data: dict | None = None,
        max_retries: int = 3,
    ) -> dict | None:
        """Make a request with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: Relative path (e.g., "/customers") or absolute URL
            json_data: Optional JSON body for the request
            max_retries: Maximum retry attempts for rate limits and server errors
        """
        delay = 0.1  # Start with 100ms delay between requests
        is_absolute_url = endpoint.startswith(("http://", "https://"))

        for attempt in range(max_retries + 1):
            try:
                # Add small delay between requests to avoid rate limiting
                time.sleep(delay)

                # Slow down if rate limit is getting low
                if self.rate_limit_remaining is not None and self.rate_limit_total:
                    ratio = self.rate_limit_remaining / self.rate_limit_total
                    if ratio < 0.1:
                        time.sleep(0.5)  # Slow down significantly

                # Use standalone httpx for absolute URLs, otherwise use the client
                if is_absolute_url:
                    response = httpx.request(
                        method,
                        endpoint,
                        json=json_data,
                        headers={
                            "Authorization": f"Bearer {self.token}",
                            "Content-Type": "application/json",
                        },
                        timeout=30.0,
                    )
                    self._log_debug(method, endpoint, json_data, response)
                else:
                    url = f"{self.base_url}{endpoint}"
                    response = self.client.request(method, endpoint, json=json_data)
                    self._log_debug(method, url, json_data, response)
                return self._handle_response(response)

            except RateLimitError as e:
                if e.retry_after:
                    wait_seconds = (e.retry_after - datetime.now(e.retry_after.tzinfo)).total_seconds()
                    if wait_seconds > 0:
                        console.print(f"[yellow]Rate limited. Waiting {wait_seconds:.0f}s...[/yellow]")
                        time.sleep(wait_seconds)
                else:
                    # Default wait of 60 seconds if no Retry-After header
                    console.print("[yellow]Rate limited. Waiting 60s...[/yellow]")
                    time.sleep(60)

                # Retry after waiting
                continue

            except APIError as e:
                # Don't retry client errors (4xx except 429)
                if 400 <= e.status_code < 500:
                    console.print(f"[red]Error: {e.message}[/red]")
                    self.last_error = e.message
                    return None

                # Retry server errors with exponential backoff
                if attempt < max_retries:
                    backoff = 2 ** attempt  # 1s, 2s, 4s
                    console.print(f"[yellow]Server error. Retrying in {backoff}s...[/yellow]")
                    time.sleep(backoff)
                else:
                    console.print(f"[red]Error after {max_retries} retries: {e.message}[/red]")
                    self.last_error = e.message
                    return None

            except httpx.RequestError as e:
                # Network errors - retry with backoff
                if attempt < max_retries:
                    backoff = 2 ** attempt
                    console.print(f"[yellow]Network error. Retrying in {backoff}s...[/yellow]")
                    time.sleep(backoff)
                else:
                    console.print(f"[red]Network error: {e}[/red]")
                    self.last_error = f"Network error: {e}"
                    return None

        return None

    def create_customer(self, customer_data: dict) -> dict | None:
        """Create a customer in X-Series."""
        result = self._request_with_retry("POST", "/customers", json_data=customer_data)
        if result and "data" in result:
            return result["data"]
        return result

    def create_product(self, product_data: dict) -> dict | None:
        """Create a product in X-Series."""
        result = self._request_with_retry("POST", "/products", json_data=product_data)
        if result and "data" in result:
            # Product API returns array of IDs
            ids = result["data"]
            if isinstance(ids, list) and len(ids) > 0:
                return {"id": ids[0]}
        return result

    def validate_credentials(self) -> tuple[bool, str, bool]:
        """Validate domain and token by calling GET /retailer.

        Returns:
            (True, retailer_name, tax_exclusive) if valid
            (False, error_message, False) if invalid
        """
        try:
            response = self.client.get("/retailer")
            if response.status_code == 200:
                data = response.json()
                retailer = data.get("data", {})
                name = retailer.get("name", "Unknown")
                tax_exclusive = retailer.get("tax_exclusive", False)
                return True, name, tax_exclusive
            elif response.status_code == 401:
                return False, "Invalid or expired token", False
            elif response.status_code == 404:
                return False, f"Invalid domain: {self.domain}", False
            else:
                return False, f"Unexpected error: {response.status_code}", False
        except httpx.RequestError as e:
            return False, f"Connection error: {e}", False

    def get_outlets(self) -> tuple[list[dict], str | None]:
        """Fetch all outlets for the account.

        Returns:
            (outlets, None) on success
            ([], error_message) on failure
        """
        result = self._request_with_retry("GET", "/outlets")
        if result is None:
            return [], "Failed to fetch outlets"
        if "data" in result:
            return result["data"], None
        if isinstance(result, list):
            return result, None
        return [], None

    def update_product_inventory(
        self, product_id: str, inventory: list[dict], max_retries: int = 3
    ) -> bool:
        """Update product inventory using v2.1 API.

        Args:
            product_id: UUID of the product to update
            inventory: List of dicts with outlet_id and current_amount
            max_retries: Maximum retry attempts for rate limits and server errors

        Returns:
            True if update succeeded, False otherwise
        """
        # v2.1 API required for inventory updates
        endpoint = f"https://{self.domain}.retail.lightspeed.app/api/2.1/products/{product_id}"
        # Must enable track_inventory in same call - v2.0 POST /products ignores this field
        payload = {
            "common": {"track_inventory": True},
            "details": {"inventory": inventory},
        }

        result = self._request_with_retry(
            "PUT", endpoint, json_data=payload, max_retries=max_retries
        )
        return result is not None

    def get_registers(self) -> tuple[list[dict], str | None]:
        """Fetch all registers for the account.

        Returns:
            (registers, None) on success
            ([], error_message) on failure
        """
        result = self._request_with_retry("GET", "/registers")
        if result is None:
            return [], "Failed to fetch registers"
        if "data" in result:
            return result["data"], None
        if isinstance(result, list):
            return result, None
        return [], None

    def get_users(self) -> tuple[list[dict], str | None]:
        """Fetch all users for the account.

        Returns:
            (users, None) on success
            ([], error_message) on failure
        """
        result = self._request_with_retry("GET", "/users")
        if result is None:
            return [], "Failed to fetch users"
        if "data" in result:
            return result["data"], None
        if isinstance(result, list):
            return result, None
        return [], None

    def get_payment_types(self) -> tuple[list[dict], str | None]:
        """Fetch all payment types for the account.

        Returns:
            (payment_types, None) on success
            ([], error_message) on failure
        """
        result = self._request_with_retry("GET", "/payment_types")
        if result is None:
            return [], "Failed to fetch payment types"
        if "data" in result:
            return result["data"], None
        if isinstance(result, list):
            return result, None
        return [], None

    def get_taxes(self) -> tuple[list[dict], str | None]:
        """Fetch all taxes for the account.

        Returns:
            (taxes, None) on success
            ([], error_message) on failure
        """
        result = self._request_with_retry("GET", "/taxes")
        if result is None:
            return [], "Failed to fetch taxes"
        if "data" in result:
            return result["data"], None
        if isinstance(result, list):
            return result, None
        return [], None

    def create_sale(self, sale_data: dict) -> dict | None:
        """Create a register sale using v0.9 API.

        Args:
            sale_data: Sale payload with user_id, register_id, state, etc.

        Returns:
            Created sale data or None on failure
        """
        # Sales API is v0.9 (no /2.0 prefix)
        endpoint = f"https://{self.domain}.retail.lightspeed.app/api/register_sales"
        result = self._request_with_retry("POST", endpoint, json_data=sale_data)
        if result and "register_sale" in result:
            return result["register_sale"]
        return result

    def get_variant_attributes(self) -> tuple[list[dict], str | None]:
        """Fetch all variant attributes for the account.

        Returns:
            (attributes, None) on success
            ([], error_message) on failure
        """
        result = self._request_with_retry("GET", "/variant_attributes")
        if result is None:
            return [], "Failed to fetch variant attributes"
        if "data" in result:
            return result["data"], None
        if isinstance(result, list):
            return result, None
        return [], None

    def create_variant_attribute(self, name: str) -> dict | None:
        """Create a variant attribute (e.g., Color, Size).

        Args:
            name: Attribute name

        Returns:
            Created attribute data or None on failure
        """
        result = self._request_with_retry("POST", "/variant_attributes", json_data={"name": name})
        if result and "data" in result:
            return result["data"]
        return result

    def create_variant_product(self, product_data: dict) -> list[str] | None:
        """Create a variant product family.

        Args:
            product_data: Product payload with name and variants array

        Returns:
            List of created variant product IDs or None on failure
        """
        result = self._request_with_retry("POST", "/products", json_data=product_data)
        if result and "data" in result:
            return result["data"]
        return None

    def update_variant_price(
        self, product_id: str, price: float, tax_inclusive: bool = True
    ) -> bool:
        """Update price for a variant product using v2.1 API.

        Args:
            product_id: UUID of the variant product
            price: Price to set
            tax_inclusive: If True, set price_including_tax; if False, price_excluding_tax

        Returns:
            True if update succeeded, False otherwise
        """
        endpoint = f"https://{self.domain}.retail.lightspeed.app/api/2.1/products/{product_id}"
        price_field = "price_including_tax" if tax_inclusive else "price_excluding_tax"
        payload = {"details": {price_field: price}}

        result = self._request_with_retry("PUT", endpoint, json_data=payload)
        return result is not None

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> "XSeriesClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
