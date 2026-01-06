"""Tests for the clone module."""

import pytest

from xseries_demo.clone import (
    CUSTOMER_STRIP_FIELDS,
    PRODUCT_STRIP_FIELDS,
    map_outlets_by_name,
    transform_customer_for_creation,
    transform_inventory_for_destination,
    transform_product_for_creation,
)


class TestTransformProductForCreation:
    """Tests for transform_product_for_creation function."""

    def test_strips_id_fields(self):
        """Should strip id and version fields."""
        product = {
            "id": "test-uuid-123",
            "version": 5,
            "name": "Test Product",
            "sku": "TEST-001",
        }
        result = transform_product_for_creation(product)

        assert "id" not in result
        assert "version" not in result
        assert result["name"] == "Test Product"
        assert result["sku"] == "TEST-001"

    def test_strips_all_system_fields(self):
        """Should strip all fields in PRODUCT_STRIP_FIELDS."""
        product = {
            "id": "uuid",
            "version": 1,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-02",
            "deleted_at": None,
            "source_id": "src-123",
            "variant_source_id": "var-src",
            "variant_parent_id": "parent-123",
            "image_thumbnail_url": "http://example.com/thumb.jpg",
            "image_large_url": "http://example.com/large.jpg",
            "images": [{"url": "http://example.com/img.jpg"}],
            "inventory": [{"outlet_id": "o1", "amount": 50}],
            "has_variants": True,
            "variant_count": 5,
            "variant_products": [],
            "source": "api",
            "name": "Keep This",
            "sku": "KEEP-001",
        }
        result = transform_product_for_creation(product)

        for field in PRODUCT_STRIP_FIELDS:
            assert field not in result, f"Field {field} should be stripped"

        assert result["name"] == "Keep This"
        assert result["sku"] == "KEEP-001"

    def test_preserves_price_fields(self):
        """Should preserve price fields."""
        product = {
            "id": "uuid",
            "name": "Product",
            "sku": "SKU-001",
            "price_including_tax": 29.99,
            "supply_price": 15.00,
        }
        result = transform_product_for_creation(product)

        assert result["price_including_tax"] == 29.99
        assert result["supply_price"] == 15.00

    def test_skips_none_values(self):
        """Should not include fields with None values."""
        product = {
            "id": "uuid",
            "name": "Product",
            "sku": "SKU-001",
            "description": None,
            "brand": None,
        }
        result = transform_product_for_creation(product)

        assert "description" not in result
        assert "brand" not in result

    def test_empty_product(self):
        """Should handle empty product dict."""
        result = transform_product_for_creation({})
        assert result == {}


class TestTransformCustomerForCreation:
    """Tests for transform_customer_for_creation function."""

    def test_strips_id_fields(self):
        """Should strip id and version fields."""
        customer = {
            "id": "cust-uuid-123",
            "version": 3,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
        }
        result = transform_customer_for_creation(customer)

        assert "id" not in result
        assert "version" not in result
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["email"] == "john@example.com"

    def test_strips_all_system_fields(self):
        """Should strip all fields in CUSTOMER_STRIP_FIELDS."""
        customer = {
            "id": "uuid",
            "version": 1,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-02",
            "deleted_at": None,
            "customer_code": "CUST-001",
            "year_to_date": 500.00,
            "balance": 0.00,
            "loyalty_balance": 100,
            "loyalty_email_sent": True,
            "custom_field_1": "custom1",
            "custom_field_2": "custom2",
            "custom_field_3": "custom3",
            "custom_field_4": "custom4",
            "first_name": "Jane",
            "email": "jane@example.com",
        }
        result = transform_customer_for_creation(customer)

        for field in CUSTOMER_STRIP_FIELDS:
            assert field not in result, f"Field {field} should be stripped"

        assert result["first_name"] == "Jane"
        assert result["email"] == "jane@example.com"

    def test_strips_customer_group(self):
        """Should strip customer_group nested object."""
        customer = {
            "id": "uuid",
            "first_name": "John",
            "customer_group": {"id": "group-123", "name": "VIP"},
        }
        result = transform_customer_for_creation(customer)

        assert "customer_group" not in result

    def test_preserves_address_fields(self):
        """Should preserve address fields."""
        customer = {
            "id": "uuid",
            "first_name": "John",
            "physical_address_1": "123 Main St",
            "physical_city": "Springfield",
            "physical_state": "IL",
            "physical_postcode": "62701",
            "physical_country_id": "US",
        }
        result = transform_customer_for_creation(customer)

        assert result["physical_address_1"] == "123 Main St"
        assert result["physical_city"] == "Springfield"
        assert result["physical_country_id"] == "US"


class TestMapOutletsByName:
    """Tests for map_outlets_by_name function."""

    def test_maps_matching_outlets(self):
        """Should map outlets that have matching names."""
        source = [
            {"id": "src-1", "name": "Main Store"},
            {"id": "src-2", "name": "Warehouse"},
        ]
        dest = [
            {"id": "dst-1", "name": "Main Store"},
            {"id": "dst-2", "name": "Warehouse"},
        ]
        result = map_outlets_by_name(source, dest)

        assert result["src-1"] == "dst-1"
        assert result["src-2"] == "dst-2"

    def test_ignores_non_matching_outlets(self):
        """Should not include outlets that don't exist in destination."""
        source = [
            {"id": "src-1", "name": "Main Store"},
            {"id": "src-2", "name": "Old Location"},
        ]
        dest = [
            {"id": "dst-1", "name": "Main Store"},
            {"id": "dst-3", "name": "New Location"},
        ]
        result = map_outlets_by_name(source, dest)

        assert result["src-1"] == "dst-1"
        assert "src-2" not in result

    def test_empty_outlets(self):
        """Should handle empty outlet lists."""
        assert map_outlets_by_name([], []) == {}
        assert map_outlets_by_name([{"id": "s1", "name": "Store"}], []) == {}
        assert map_outlets_by_name([], [{"id": "d1", "name": "Store"}]) == {}

    def test_case_sensitive_matching(self):
        """Outlet names should be matched case-sensitively."""
        source = [{"id": "src-1", "name": "Main Store"}]
        dest = [{"id": "dst-1", "name": "main store"}]
        result = map_outlets_by_name(source, dest)

        assert "src-1" not in result  # Names don't match due to case


class TestTransformInventoryForDestination:
    """Tests for transform_inventory_for_destination function."""

    def test_transforms_inventory_with_mapping(self):
        """Should transform inventory using outlet mapping."""
        inventory = [
            {"outlet_id": "src-1", "current_amount": 100},
            {"outlet_id": "src-2", "current_amount": 50},
        ]
        mapping = {"src-1": "dst-1", "src-2": "dst-2"}

        result = transform_inventory_for_destination(inventory, mapping)

        assert len(result) == 2
        assert result[0]["outlet_id"] == "dst-1"
        assert result[0]["current_amount"] == 100
        assert result[1]["outlet_id"] == "dst-2"
        assert result[1]["current_amount"] == 50

    def test_skips_unmapped_outlets(self):
        """Should skip inventory for outlets not in mapping."""
        inventory = [
            {"outlet_id": "src-1", "current_amount": 100},
            {"outlet_id": "src-2", "current_amount": 50},
        ]
        mapping = {"src-1": "dst-1"}  # src-2 not mapped

        result = transform_inventory_for_destination(inventory, mapping)

        assert len(result) == 1
        assert result[0]["outlet_id"] == "dst-1"

    def test_handles_missing_current_amount(self):
        """Should default to 0 if current_amount is missing."""
        inventory = [{"outlet_id": "src-1"}]
        mapping = {"src-1": "dst-1"}

        result = transform_inventory_for_destination(inventory, mapping)

        assert result[0]["current_amount"] == 0

    def test_empty_inventory(self):
        """Should handle empty inventory list."""
        result = transform_inventory_for_destination([], {"src-1": "dst-1"})
        assert result == []

    def test_empty_mapping(self):
        """Should return empty list if no mapping exists."""
        inventory = [{"outlet_id": "src-1", "current_amount": 100}]
        result = transform_inventory_for_destination(inventory, {})
        assert result == []
