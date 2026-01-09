"""Tests for the clone module."""

import pytest

from xseries_demo.clone import (
    CUSTOMER_STRIP_FIELDS,
    PRODUCT_ALLOWED_FIELDS,
    SALE_STRIP_FIELDS,
    map_by_name,
    map_outlets_by_name,
    transform_customer_for_creation,
    transform_inventory_for_destination,
    transform_product_for_creation,
    transform_sale_for_creation,
)


class TestTransformProductForCreation:
    """Tests for transform_product_for_creation function."""

    def test_strips_id_fields(self):
        """Should strip id and version fields (not in whitelist)."""
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
        """Should only include fields in PRODUCT_ALLOWED_FIELDS."""
        product = {
            "id": "uuid",
            "version": 1,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-02",
            "deleted_at": None,
            "variant_parent_id": "parent-123",
            "image_thumbnail_url": "http://example.com/thumb.jpg",
            "image_large_url": "http://example.com/large.jpg",
            "has_variants": True,
            "variant_count": 5,
            "variant_products": [],
            "name": "Keep This",
            "sku": "KEEP-001",
        }
        result = transform_product_for_creation(product)

        # These system fields should not be in result
        assert "id" not in result
        assert "version" not in result
        assert "created_at" not in result
        assert "updated_at" not in result
        assert "deleted_at" not in result
        assert "variant_parent_id" not in result
        assert "image_thumbnail_url" not in result
        assert "image_large_url" not in result
        assert "has_variants" not in result
        assert "variant_count" not in result
        assert "variant_products" not in result

        # Whitelisted fields should be preserved
        assert result["name"] == "Keep This"
        assert result["sku"] == "KEEP-001"

    def test_preserves_price_fields(self):
        """Should preserve allowed price field (not both)."""
        product = {
            "id": "uuid",
            "name": "Product",
            "sku": "SKU-001",
            "price_including_tax": 29.99,
            "supply_price": 15.00,
        }
        result = transform_product_for_creation(product, tax_inclusive=True)

        assert result["price_including_tax"] == 29.99
        assert result["supply_price"] == 15.00

    def test_skips_none_values(self):
        """Should not include fields with None values."""
        product = {
            "id": "uuid",
            "name": "Product",
            "sku": "SKU-001",
            "description": None,
            "brand_id": None,
        }
        result = transform_product_for_creation(product)

        assert "description" not in result
        assert "brand_id" not in result

    def test_empty_product(self):
        """Should handle empty product dict."""
        result = transform_product_for_creation({})
        assert result == {}

    def test_cleans_product_codes_nested_objects(self):
        """Should strip id fields from nested product_codes."""
        product = {
            "name": "Product",
            "sku": "SKU-001",
            "product_codes": [
                {
                    "id": "code-uuid-123",
                    "type": "CUSTOM",
                    "code": "SKU-001",
                    "created_at": "2024-01-01",
                }
            ],
        }
        result = transform_product_for_creation(product)

        assert len(result["product_codes"]) == 1
        assert "id" not in result["product_codes"][0]
        assert "created_at" not in result["product_codes"][0]
        assert result["product_codes"][0]["type"] == "CUSTOM"
        assert result["product_codes"][0]["code"] == "SKU-001"

    def test_cleans_product_suppliers_nested_objects(self):
        """Should strip id fields from nested product_suppliers and map supplier_id."""
        product = {
            "name": "Product",
            "sku": "SKU-001",
            "product_suppliers": [
                {
                    "id": "supplier-uuid-123",
                    "product_id": "prod-uuid-456",
                    "supplier_id": "sup-uuid-789",
                    "price": 10.00,
                    "code": "SUP-001",
                }
            ],
        }
        # Provide supplier mapping to map the supplier_id
        supplier_mapping = {"sup-uuid-789": "new-sup-uuid-999"}
        result = transform_product_for_creation(
            product, supplier_mapping=supplier_mapping
        )

        assert len(result["product_suppliers"]) == 1
        assert "id" not in result["product_suppliers"][0]
        assert "product_id" not in result["product_suppliers"][0]
        # supplier_id should be mapped to new value
        assert result["product_suppliers"][0]["supplier_id"] == "new-sup-uuid-999"
        assert result["product_suppliers"][0]["price"] == 10.00
        assert result["product_suppliers"][0]["code"] == "SUP-001"

    def test_maps_active_to_is_active(self):
        """Should map 'active' field to 'is_active'."""
        product = {
            "name": "Product",
            "sku": "SKU-001",
            "active": True,
        }
        result = transform_product_for_creation(product)

        assert "active" not in result
        assert result["is_active"] is True

    def test_handles_both_price_fields_tax_inclusive(self):
        """Should keep only price_including_tax when tax_inclusive=True."""
        product = {
            "name": "Product",
            "sku": "SKU-001",
            "price_including_tax": 29.99,
            "price_excluding_tax": 24.99,
        }
        result = transform_product_for_creation(product, tax_inclusive=True)

        assert result["price_including_tax"] == 29.99
        assert "price_excluding_tax" not in result

    def test_handles_both_price_fields_tax_exclusive(self):
        """Should keep only price_excluding_tax when tax_inclusive=False."""
        product = {
            "name": "Product",
            "sku": "SKU-001",
            "price_including_tax": 29.99,
            "price_excluding_tax": 24.99,
        }
        result = transform_product_for_creation(product, tax_inclusive=False)

        assert result["price_excluding_tax"] == 24.99
        assert "price_including_tax" not in result


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


class TestMapByName:
    """Tests for map_by_name function."""

    def test_maps_matching_items(self):
        """Should map items that have matching names."""
        source = [
            {"id": "src-1", "name": "Register 1"},
            {"id": "src-2", "name": "Register 2"},
        ]
        dest = [
            {"id": "dst-1", "name": "Register 1"},
            {"id": "dst-2", "name": "Register 2"},
        ]
        result = map_by_name(source, dest)

        assert result["src-1"] == "dst-1"
        assert result["src-2"] == "dst-2"

    def test_ignores_non_matching_items(self):
        """Should not include items that don't exist in destination."""
        source = [
            {"id": "src-1", "name": "Register 1"},
            {"id": "src-2", "name": "Old Register"},
        ]
        dest = [
            {"id": "dst-1", "name": "Register 1"},
            {"id": "dst-3", "name": "New Register"},
        ]
        result = map_by_name(source, dest)

        assert result["src-1"] == "dst-1"
        assert "src-2" not in result

    def test_empty_lists(self):
        """Should handle empty lists."""
        assert map_by_name([], []) == {}
        assert map_by_name([{"id": "s1", "name": "R1"}], []) == {}
        assert map_by_name([], [{"id": "d1", "name": "R1"}]) == {}

    def test_handles_missing_fields(self):
        """Should handle items with missing id or name."""
        source = [
            {"id": "src-1", "name": "Register 1"},
            {"name": "No ID"},
            {"id": "no-name"},
        ]
        dest = [
            {"id": "dst-1", "name": "Register 1"},
        ]
        result = map_by_name(source, dest)

        assert result == {"src-1": "dst-1"}


class TestTransformSaleForCreation:
    """Tests for transform_sale_for_creation function."""

    def setup_method(self):
        """Set up common test data."""
        self.product_mapping = {"prod-src-1": "prod-dst-1", "prod-src-2": "prod-dst-2"}
        self.customer_mapping = {"cust-src-1": "cust-dst-1"}
        self.register_mapping = {"reg-src-1": "reg-dst-1"}
        self.user_mapping = {"user-src-1": "user-dst-1"}
        self.tax_mapping = {"tax-src-1": "tax-dst-1"}
        self.payment_type_mapping = {"pay-src-1": "pay-dst-1"}

    def test_transforms_basic_sale(self):
        """Should transform a basic sale with all required fields."""
        sale = {
            "id": "sale-123",
            "register_id": "reg-src-1",
            "user_id": "user-src-1",
            "sale_date": "2024-01-15T10:30:00Z",
            "register_sale_products": [
                {
                    "product_id": "prod-src-1",
                    "quantity": 2,
                    "price": 29.99,
                    "discount": 0,
                }
            ],
            "register_sale_payments": [
                {"payment_type_id": "pay-src-1", "amount": 59.98}
            ],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is not None
        assert result["register_id"] == "reg-dst-1"
        assert result["user_id"] == "user-dst-1"
        assert result["status"] == "CLOSED"
        assert len(result["register_sale_products"]) == 1
        assert result["register_sale_products"][0]["product_id"] == "prod-dst-1"
        assert len(result["register_sale_payments"]) == 1
        assert result["register_sale_payments"][0]["payment_type_id"] == "pay-dst-1"

    def test_returns_none_if_register_not_mapped(self):
        """Should return None if register is not in mapping."""
        sale = {
            "register_id": "unmapped-register",
            "user_id": "user-src-1",
            "register_sale_products": [{"product_id": "prod-src-1"}],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is None

    def test_returns_none_if_user_not_mapped(self):
        """Should return None if user is not in mapping."""
        sale = {
            "register_id": "reg-src-1",
            "user_id": "unmapped-user",
            "register_sale_products": [{"product_id": "prod-src-1"}],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is None

    def test_returns_none_if_no_valid_products(self):
        """Should return None if no products can be mapped."""
        sale = {
            "register_id": "reg-src-1",
            "user_id": "user-src-1",
            "register_sale_products": [{"product_id": "unmapped-product"}],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is None

    def test_maps_customer_if_present(self):
        """Should map customer_id if present and in mapping."""
        sale = {
            "register_id": "reg-src-1",
            "user_id": "user-src-1",
            "customer_id": "cust-src-1",
            "register_sale_products": [{"product_id": "prod-src-1"}],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is not None
        assert result["customer_id"] == "cust-dst-1"

    def test_skips_unmapped_customer(self):
        """Should not include customer_id if not in mapping."""
        sale = {
            "register_id": "reg-src-1",
            "user_id": "user-src-1",
            "customer_id": "unmapped-customer",
            "register_sale_products": [{"product_id": "prod-src-1"}],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is not None
        assert "customer_id" not in result

    def test_maps_tax_on_line_items(self):
        """Should map tax_id on line items."""
        sale = {
            "register_id": "reg-src-1",
            "user_id": "user-src-1",
            "register_sale_products": [
                {"product_id": "prod-src-1", "tax_id": "tax-src-1"}
            ],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is not None
        assert result["register_sale_products"][0]["tax_id"] == "tax-dst-1"

    def test_skips_unmapped_products_in_line_items(self):
        """Should skip line items with unmapped products."""
        sale = {
            "register_id": "reg-src-1",
            "user_id": "user-src-1",
            "register_sale_products": [
                {"product_id": "prod-src-1", "quantity": 1},
                {"product_id": "unmapped-product", "quantity": 2},
                {"product_id": "prod-src-2", "quantity": 3},
            ],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is not None
        assert len(result["register_sale_products"]) == 2
        product_ids = [p["product_id"] for p in result["register_sale_products"]]
        assert "prod-dst-1" in product_ids
        assert "prod-dst-2" in product_ids

    def test_skips_unmapped_payment_types(self):
        """Should skip payments with unmapped payment types."""
        sale = {
            "register_id": "reg-src-1",
            "user_id": "user-src-1",
            "register_sale_products": [{"product_id": "prod-src-1"}],
            "register_sale_payments": [
                {"payment_type_id": "pay-src-1", "amount": 50},
                {"payment_type_id": "unmapped-payment", "amount": 10},
            ],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is not None
        assert len(result["register_sale_payments"]) == 1
        assert result["register_sale_payments"][0]["payment_type_id"] == "pay-dst-1"

    def test_copies_optional_fields(self):
        """Should copy optional fields like note and total_price."""
        sale = {
            "register_id": "reg-src-1",
            "user_id": "user-src-1",
            "note": "Test sale",
            "total_price": 99.99,
            "total_tax": 9.99,
            "register_sale_products": [{"product_id": "prod-src-1"}],
        }

        result = transform_sale_for_creation(
            sale,
            self.product_mapping,
            self.customer_mapping,
            self.register_mapping,
            self.user_mapping,
            self.tax_mapping,
            self.payment_type_mapping,
        )

        assert result is not None
        assert result["note"] == "Test sale"
        assert result["total_price"] == 99.99
        assert result["total_tax"] == 9.99
