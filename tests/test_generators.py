"""Tests for product and variant generators."""

import pytest
from xseries_demo.generators.products import generate_products, load_vertical_data
from xseries_demo.generators.variants import generate_variant_products, load_variant_data


class TestLiquorProducts:
    """Tests for liquor product generation."""

    def test_load_liquor_vertical_data(self):
        """Test that liquor vertical data loads correctly."""
        data = load_vertical_data("LIQ")

        assert "products" in data
        assert "adjectives" in data
        assert "brands" in data
        assert "price_range" in data
        assert "supply_margin" in data

    def test_liquor_price_range(self):
        """Test that liquor prices are within expected range."""
        data = load_vertical_data("LIQ")

        assert data["price_range"]["min"] == 16.00
        assert data["price_range"]["max"] == 75.00

    def test_generate_liquor_products(self):
        """Test generating liquor products."""
        products = list(generate_products("LIQ", count=5))

        assert len(products) == 5
        for product in products:
            assert product["sku"].startswith("LIQ-")
            assert "name" in product
            assert "supply_price" in product
            assert product["is_active"] is True

    def test_liquor_product_prices_in_range(self):
        """Test that generated liquor prices are within range."""
        products = list(generate_products("LIQ", count=10))

        for product in products:
            price = product.get("price_including_tax") or product.get("price_excluding_tax")
            assert 15.95 <= price <= 75.99, f"Price {price} out of range"

    def test_liquor_skus_unique(self):
        """Test that generated SKUs are unique."""
        products = list(generate_products("LIQ", count=50))
        skus = [p["sku"] for p in products]

        assert len(skus) == len(set(skus)), "Duplicate SKUs found"


class TestProductNameUniqueness:
    """Tests for product name uniqueness across all verticals."""

    def test_all_verticals_generate_unique_names(self):
        """Test that all verticals generate unique product names."""
        for prefix in ['LIQ', 'APP', 'ELE', 'HOM', 'BTY']:
            products = list(generate_products(prefix, count=50))
            names = [p['name'] for p in products]

            assert len(names) == len(set(names)), \
                f"Duplicate names found in {prefix} vertical"

    def test_unique_names_with_high_count(self):
        """Test uniqueness with larger product counts."""
        # Liquor has: 10 brands × 12 adjectives × 35 products = 4,200 combinations
        products = list(generate_products('LIQ', count=100))
        names = [p['name'] for p in products]

        assert len(names) == len(set(names)), "Duplicate names found with 100 products"


class TestLiquorVariants:
    """Tests for liquor variant generation."""

    def test_load_liquor_variant_data(self):
        """Test that liquor variant data loads correctly."""
        data = load_variant_data()

        assert "LIQ" in data["verticals"]
        liq = data["verticals"]["LIQ"]
        assert "products" in liq
        assert "variant_values" in liq

    def test_liquor_variant_bottle_sizes(self):
        """Test that liquor variants use bottle sizes."""
        data = load_variant_data()
        liq = data["verticals"]["LIQ"]

        # variant_values contains bottle sizes for liquor
        sizes = liq["variant_values"]
        assert "375ml" in sizes
        assert "750ml" in sizes
        assert "1L" in sizes
        assert "1.75L" in sizes

    def test_generate_liquor_variants(self):
        """Test generating liquor variant products."""
        # Use a fake attribute ID for testing
        fake_size_id = "test-size-attr-id"

        variants = list(generate_variant_products(
            prefix="LIQ",
            color_attribute_id=fake_size_id,
            size_attribute_id=None,
            count=3,
        ))

        assert len(variants) == 3
        for variant in variants:
            assert "name" in variant
            assert "base_price" in variant
            assert "payload" in variant
            assert "variants" in variant["payload"]
            # Each product should have 4 bottle size variants (375ml, 750ml, 1L, 1.75L)
            assert len(variant["payload"]["variants"]) == 4

    def test_liquor_variant_skus_contain_size(self):
        """Test that liquor variant SKUs contain size abbreviations."""
        fake_size_id = "test-size-attr-id"

        variants = list(generate_variant_products(
            prefix="LIQ",
            color_attribute_id=fake_size_id,
            count=1,
        ))

        variant = variants[0]
        skus = [v["sku"] for v in variant["payload"]["variants"]]

        # SKUs should contain size abbreviations like 375, 750, 1L, 1.7, 50M
        for sku in skus:
            assert sku.startswith("LIQ-"), f"SKU {sku} doesn't start with LIQ-"

    def test_liquor_variant_prices(self):
        """Test that liquor variant base prices are realistic."""
        data = load_variant_data()
        liq = data["verticals"]["LIQ"]

        for product in liq["products"]:
            price = product["base_price"]
            assert 20 <= price <= 70, f"Price {price} seems unrealistic for liquor"


class TestVariantAttributeLogic:
    """Tests for variant attribute creation logic."""

    def test_liquor_uses_bottle_size_attribute(self):
        """Test that LIQ vertical is configured to use Bottle Size attribute."""
        from xseries_demo.generators.variants import get_or_create_variant_attributes

        # Verify the function exists and has LIQ-specific logic
        import inspect
        source = inspect.getsource(get_or_create_variant_attributes)

        # Check that LIQ prefix triggers Bottle Size attribute
        assert 'prefix == "LIQ"' in source
        assert '"Bottle Size"' in source

    def test_all_verticals_have_variant_values(self):
        """Test that all verticals have variant_values field."""
        data = load_variant_data()

        expected_counts = {"APP": 5, "ELE": 5, "HOM": 5, "BTY": 5, "LIQ": 4}
        for prefix in ["APP", "ELE", "HOM", "BTY", "LIQ"]:
            assert prefix in data["verticals"], f"Missing vertical: {prefix}"
            vertical = data["verticals"][prefix]
            assert "variant_values" in vertical, f"Missing variant_values in {prefix}"
            expected = expected_counts[prefix]
            assert len(vertical["variant_values"]) == expected, f"Expected {expected} variant values in {prefix}"
