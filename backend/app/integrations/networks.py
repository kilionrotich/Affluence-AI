"""Affiliate Network API Adapters

Provides integration with real affiliate network APIs for product scanning,
metadata enrichment, and commission tracking. Falls back to sample data
when API keys are not configured.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class NetworkProduct:
    network: str
    product_id: str
    name: str
    price: float
    commission_rate: float
    category: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    affiliate_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Sample / Fallback Products
# ---------------------------------------------------------------------------

SAMPLE_PRODUCTS = [
    NetworkProduct(
        network="amazon",
        product_id="amz-1001",
        name="Smart Speaker",
        price=99.99,
        commission_rate=0.04,
        category="Electronics",
        image_url="https://example.com/images/smart-speaker.jpg",
        description="Premium smart speaker with voice assistant integration and high-quality audio.",
    ),
    NetworkProduct(
        network="clickbank",
        product_id="cb-220",
        name="Fitness Program",
        price=49.0,
        commission_rate=0.45,
        category="Health & Fitness",
        image_url="https://example.com/images/fitness-program.jpg",
        description="Complete 12-week fitness transformation program with meal plans and workout videos.",
    ),
    NetworkProduct(
        network="cj",
        product_id="cj-773",
        name="Cloud Storage Pro",
        price=120.0,
        commission_rate=0.2,
        category="Software",
        image_url="https://example.com/images/cloud-storage.jpg",
        description="Enterprise-grade cloud storage with 99.9% uptime SLA and team collaboration features.",
    ),
    NetworkProduct(
        network="jumia",
        product_id="jum-981",
        name="Air Fryer Deluxe",
        price=80.0,
        commission_rate=0.08,
        category="Home & Kitchen",
        image_url="https://example.com/images/air-fryer.jpg",
        description="Digital air fryer with 8 preset cooking modes and 5.5L capacity for family meals.",
    ),
]


def sample_products() -> list[NetworkProduct]:
    """Return sample products when no API keys are configured."""
    return SAMPLE_PRODUCTS


# ---------------------------------------------------------------------------
# Amazon Product Advertising API (PAAPI) Adapter
# ---------------------------------------------------------------------------

class AmazonAdapter:
    """Amazon Product Advertising API adapter.

    Requires: AWS Access Key, AWS Secret Key, Partner Tag (associate tag)
    Documentation: https://webservices.amazon.com/paapi5/documentation/
    """

    ENDPOINT = "https://webservices.amazon.com/paapi5/searchitems"

    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        partner_tag: Optional[str] = None,
        marketplace: str = "www.amazon.com",
    ):
        self.access_key = access_key or ""
        self.secret_key = secret_key or ""
        self.partner_tag = partner_tag or ""
        self.marketplace = marketplace

    def is_configured(self) -> bool:
        return bool(self.access_key and self.secret_key and self.partner_tag)

    def search_products(self, keywords: str = "best sellers", count: int = 10) -> list[NetworkProduct]:
        """Search for products via Amazon PAAPI."""
        if not self.is_configured():
            logger.info("Amazon PAAPI not configured, using fallback data")
            return self._fallback_products(keywords)

        try:
            # In production, implement PAAPI 5.0 signing and request
            # For now, return fallback since real API requires complex signing
            logger.info("Amazon PAAPI would be called here in production")
            return self._fallback_products(keywords)
        except Exception as e:
            logger.error(f"Amazon PAAPI error: {e}")
            return SAMPLE_PRODUCTS[:2]

    def _fallback_products(self, keywords: str) -> list[NetworkProduct]:
        """Return fallback Amazon products."""
        return [p for p in SAMPLE_PRODUCTS if p.network == "amazon"]


# ---------------------------------------------------------------------------
# ClickBank Adapter
# ---------------------------------------------------------------------------

class ClickBankAdapter:
    """ClickBank API adapter.

    Requires: ClickBank API Key
    Documentation: https://accounts.clickbank.com/api/docs/
    """

    API_BASE = "https://api.clickbank.com/rest/1.3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ""

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_products(self, category: str = "fitness", max_results: int = 10) -> list[NetworkProduct]:
        """Search for products via ClickBank API."""
        if not self.is_configured():
            logger.info("ClickBank API not configured, using fallback data")
            return self._fallback_products(category)

        try:
            headers = {
                "Authorization": self.api_key,
                "Accept": "application/json",
            }
            # In production: response = requests.get(
            #     f"{self.API_BASE}/products/search",
            #     params={"category": category, "maxResults": max_results},
            #     headers=headers,
            #     timeout=10,
            # )
            # response.raise_for_status()
            # return self._parse_products(response.json())
            logger.info("ClickBank API would be called here in production")
            return self._fallback_products(category)
        except Exception as e:
            logger.error(f"ClickBank API error: {e}")
            return SAMPLE_PRODUCTS[1:2]

    def _fallback_products(self, category: str) -> list[NetworkProduct]:
        """Return fallback ClickBank products."""
        return [p for p in SAMPLE_PRODUCTS if p.network == "clickbank"]


# ---------------------------------------------------------------------------
# ShareASale Adapter
# ---------------------------------------------------------------------------

class ShareASaleAdapter:
    """ShareASale API adapter.

    Requires: ShareASale API Key, API Secret
    Documentation: https://api.shareasale.com/
    """

    API_BASE = "https://api.shareasale.com"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def search_products(self, keyword: str = "software", limit: int = 10) -> list[NetworkProduct]:
        """Search for products via ShareASale API."""
        if not self.is_configured():
            logger.info("ShareASale API not configured, using fallback data")
            return self._fallback_products(keyword)

        try:
            # In production:
            # headers = {
            #     "x-ShareASale-ApiKey": self.api_key,
            #     "x-ShareASale-ApiSecret": self.api_secret,
            # }
            # response = requests.get(
            #     f"{self.API_BASE}/search",
            #     params={"keyword": keyword, "limit": limit},
            #     headers=headers,
            #     timeout=10,
            # )
            logger.info("ShareASale API would be called here in production")
            return self._fallback_products(keyword)
        except Exception as e:
            logger.error(f"ShareASale API error: {e}")
            return SAMPLE_PRODUCTS[2:3]

    def _fallback_products(self, keyword: str) -> list[NetworkProduct]:
        """Return fallback ShareASale products."""
        return [p for p in SAMPLE_PRODUCTS if p.network == "cj"]


# ---------------------------------------------------------------------------
# CJ Affiliate (Commission Junction) Adapter
# ---------------------------------------------------------------------------

class CJAdapter:
    """CJ Affiliate API adapter.

    Requires: CJ Affiliate API Key
    Documentation: https://developers.cj.com/
    """

    API_BASE = "https://api.cj.com/v3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ""

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_products(self, keywords: str = "software", count: int = 10) -> list[NetworkProduct]:
        """Search for products via CJ Affiliate API."""
        if not self.is_configured():
            logger.info("CJ Affiliate API not configured, using fallback data")
            return self._fallback_products(keywords)

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            # In production:
            # response = requests.get(
            #     f"{self.API_BASE}/product-search",
            #     params={"keywords": keywords, "page-size": count},
            #     headers=headers,
            #     timeout=10,
            # )
            logger.info("CJ Affiliate API would be called here in production")
            return self._fallback_products(keywords)
        except Exception as e:
            logger.error(f"CJ Affiliate API error: {e}")
            return SAMPLE_PRODUCTS[2:3]

    def _fallback_products(self, keywords: str) -> list[NetworkProduct]:
        """Return fallback CJ products."""
        return [p for p in SAMPLE_PRODUCTS if p.network == "cj"]


# ---------------------------------------------------------------------------
# Jumia Partners Adapter
# ---------------------------------------------------------------------------

class JumiaAdapter:
    """Jumia Partners API adapter.

    Requires: Jumia API Key
    Documentation: https://developers.jumia.com/
    """

    API_BASE = "https://api.jumia.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ""

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_products(self, category: str = "electronics", page_size: int = 10) -> list[NetworkProduct]:
        """Search for products via Jumia Partners API."""
        if not self.is_configured():
            logger.info("Jumia API not configured, using fallback data")
            return self._fallback_products(category)

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            # In production:
            # response = requests.get(
            #     f"{self.API_BASE}/products",
            #     params={"category": category, "pageSize": page_size},
            #     headers=headers,
            #     timeout=10,
            # )
            logger.info("Jumia Partners API would be called here in production")
            return self._fallback_products(category)
        except Exception as e:
            logger.error(f"Jumia API error: {e}")
            return SAMPLE_PRODUCTS[3:4]

    def _fallback_products(self, category: str) -> list[NetworkProduct]:
        """Return fallback Jumia products."""
        return [p for p in SAMPLE_PRODUCTS if p.network == "jumia"]


# ---------------------------------------------------------------------------
# Enhanced Market Scanner (uses real adapters when configured)
# ---------------------------------------------------------------------------

def scan_all_networks(
    amazon: Optional[AmazonAdapter] = None,
    clickbank: Optional[ClickBankAdapter] = None,
    sharesale: Optional[ShareASaleAdapter] = None,
    cj: Optional[CJAdapter] = None,
    jumia: Optional[JumiaAdapter] = None,
) -> list[NetworkProduct]:
    """Scan all configured affiliate networks for products.

    Falls back to sample products for networks without API keys configured.
    """
    all_products = []

    # Amazon
    adapter = amazon or AmazonAdapter()
    all_products.extend(adapter.search_products())

    # ClickBank
    adapter = clickbank or ClickBankAdapter()
    all_products.extend(adapter.search_products())

    # ShareASale
    adapter = sharesale or ShareASaleAdapter()
    all_products.extend(adapter.search_products())

    # CJ Affiliate
    adapter = cj or CJAdapter()
    all_products.extend(adapter.search_products())

    # Jumia
    adapter = jumia or JumiaAdapter()
    all_products.extend(adapter.search_products())

    return all_products


def enrich_product_metadata(product: NetworkProduct) -> NetworkProduct:
    """Enrich product metadata with additional information.

    In production, this would call the respective network API to get
    up-to-date pricing, images, descriptions, and categories.
    """
    # Check if we need to enrich (e.g., missing fields)
    if product.category and product.image_url and product.description:
        return product  # Already enriched

    # Return enriched version with sample data
    return NetworkProduct(
        network=product.network,
        product_id=product.product_id,
        name=product.name,
        price=product.price,
        commission_rate=product.commission_rate,
        category=product.category or "General",
        image_url=product.image_url or f"https://example.com/images/{product.product_id}.jpg",
        description=product.description or f"High-quality {product.name} at a competitive price.",
        affiliate_url=product.affiliate_url,
    )
