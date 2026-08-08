"""Tests for Affiliate Network API Adapters."""

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_networks.db"
os.environ["ADMIN_TOKEN"] = "admin-token"
os.environ["VIEWER_TOKEN"] = "viewer-token"

from app.integrations.networks import (
    AmazonAdapter,
    ClickBankAdapter,
    ShareASaleAdapter,
    CJAdapter,
    JumiaAdapter,
    scan_all_networks,
    enrich_product_metadata,
    NetworkProduct,
)


def test_amazon_adapter_fallback() -> None:
    """Test Amazon adapter returns fallback data without API keys."""
    adapter = AmazonAdapter()
    assert adapter.is_configured() is False
    products = adapter.search_products()
    assert len(products) >= 1
    assert all(p.network == "amazon" for p in products)
    assert all(p.name for p in products)
    assert all(p.price > 0 for p in products)


def test_clickbank_adapter_fallback() -> None:
    """Test ClickBank adapter returns fallback data without API keys."""
    adapter = ClickBankAdapter()
    assert adapter.is_configured() is False
    products = adapter.search_products()
    assert len(products) >= 1
    assert all(p.network == "clickbank" for p in products)


def test_sharesale_adapter_fallback() -> None:
    """Test ShareASale adapter returns fallback data."""
    adapter = ShareASaleAdapter()
    assert adapter.is_configured() is False
    products = adapter.search_products()
    assert len(products) >= 1


def test_cj_adapter_fallback() -> None:
    """Test CJ Affiliate adapter returns fallback data."""
    adapter = CJAdapter()
    assert adapter.is_configured() is False
    products = adapter.search_products()
    assert len(products) >= 1


def test_jumia_adapter_fallback() -> None:
    """Test Jumia adapter returns fallback data."""
    adapter = JumiaAdapter()
    assert adapter.is_configured() is False
    products = adapter.search_products()
    assert len(products) >= 1


def test_scan_all_networks() -> None:
    """Test scanning all networks returns products."""
    products = scan_all_networks()
    assert len(products) >= 4  # At least 4 sample products
    networks = set(p.network for p in products)
    assert "amazon" in networks
    assert "clickbank" in networks
    assert "cj" in networks
    assert "jumia" in networks


def test_enrich_product_metadata() -> None:
    """Test product metadata enrichment."""
    product = NetworkProduct(
        network="amazon",
        product_id="test-enrich",
        name="Test Enrich Product",
        price=99.99,
        commission_rate=0.1,
        category=None,
        image_url=None,
        description=None,
    )

    enriched = enrich_product_metadata(product)
    assert enriched.category is not None
    assert enriched.image_url is not None
    assert enriched.description is not None
    assert enriched.price == 99.99


def test_amazon_adapter_configured_check() -> None:
    """Test Amazon adapter configured status."""
    adapter = AmazonAdapter(access_key="test", secret_key="test", partner_tag="test")
    assert adapter.is_configured() is True

    adapter2 = AmazonAdapter()
    assert adapter2.is_configured() is False


def test_clickbank_adapter_configured_check() -> None:
    """Test ClickBank adapter configured status."""
    adapter = ClickBankAdapter(api_key="test")
    assert adapter.is_configured() is True

    adapter2 = ClickBankAdapter()
    assert adapter2.is_configured() is False


def test_network_product_dataclass() -> None:
    """Test NetworkProduct dataclass fields."""
    product = NetworkProduct(
        network="amazon",
        product_id="test-123",
        name="Test",
        price=49.99,
        commission_rate=0.05,
        category="Books",
        image_url="https://example.com/img.jpg",
        description="A test product",
        affiliate_url="https://example.com/aff",
    )
    assert product.network == "amazon"
    assert product.price == 49.99
    assert product.commission_rate == 0.05
    assert product.category == "Books"


def test_scan_filters_by_network() -> None:
    """Test that filtered search returns correct network products."""
    adapter = AmazonAdapter()
    amazon_products = adapter.search_products()
    assert all(p.network == "amazon" for p in amazon_products)

    adapter = ClickBankAdapter()
    cb_products = adapter.search_products()
    assert all(p.network == "clickbank" for p in cb_products)

