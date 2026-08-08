"""Link Validation Service

Validates affiliate links for correctness, expiration, and compliance.
"""
import re
from datetime import datetime
from typing import Optional, Tuple

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AffiliateLink, Product
from ..config import get_settings


class LinkValidator:
    """Validates affiliate links for correctness and expiry."""

    # Known affiliate URL patterns for major networks
    AFFILIATE_PATTERNS = {
        "amazon": [
            r"https?://(?:www\.)?amazon\..*/dp/[A-Z0-9]{10}(?:/.*)?\?(?:.*&)?tag=",
            r"https?://(?:www\.)?amazon\..*/gp/product/[A-Z0-9]{10}(?:/.*)?\?(?:.*&)?tag=",
        ],
        "clickbank": [
            r"https?://[\w.-]+\.hop\.clickbank\.net/",
            r"https?://[\w.-]+\.pay\.clickbank\.net/",
        ],
        "cj": [
            r"https?://www\.anrdoezrs\.net/",
            r"https?://www\.kqzyfj\.com/",
            r"https?://www\.dpbolvw\.net/",
            r"https?://www\.tkqlhce\.com/",
        ],
        "sharesale": [
            r"https?://[\w.-]+\.shareasale\.com/",
            r"https?://www\.shareasale\.com/",
        ],
        "jumia": [
            r"https?://[\w.-]*\.jumia\..*/.*ref=",
        ],
    }

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def validate_link(self, link_id: int) -> dict:
        """Validate an affiliate link by checking its structure and expiration."""
        link = self.db.get(AffiliateLink, link_id)
        if not link:
            return {"valid": False, "message": "Link not found"}

        product = link.product
        if not product:
            return {"valid": False, "message": "Associated product not found"}

        issues = []

        # 1. Check if link URL is well-formed
        if not link.url or not link.url.startswith(("http://", "https://")):
            issues.append("Invalid URL format")

        # 2. Check if link matches expected pattern for the network
        network = product.network
        if network in self.AFFILIATE_PATTERNS:
            patterns = self.AFFILIATE_PATTERNS[network]
            if not any(re.match(pattern, link.url) for pattern in patterns):
                issues.append(
                    f"URL does not match expected pattern for {network}"
                )

        # 3. Check for affiliate tracking parameters
        if "ref=" not in link.url and "tag=" not in link.url and "aff_" not in link.url:
            issues.append("Missing affiliate tracking parameter")

        # 4. Check expiration
        is_expired = False
        if product.link_expires_at:
            is_expired = datetime.utcnow() > product.link_expires_at
            if is_expired:
                issues.append("Link has expired")

        # 5. Verify link responds (optional HTTP check)
        http_valid = None
        try:
            response = requests.head(
                link.url, timeout=5, allow_redirects=True
            )
            if response.status_code >= 400:
                http_valid = False
                issues.append(f"Link returns HTTP {response.status_code}")
            else:
                http_valid = True
        except requests.RequestException:
            http_valid = False
            issues.append("Link is unreachable")

        # Update product link validity status
        is_valid = len(issues) == 0
        product.is_link_valid = is_valid
        product.last_scanned_at = datetime.utcnow()
        if is_expired:
            product.link_expires_at = datetime.utcnow()

        self.db.commit()

        return {
            "valid": is_valid,
            "link_id": link.id,
            "url": link.url,
            "network": network,
            "product_name": product.name,
            "expires_at": product.link_expires_at,
            "http_valid": http_valid,
            "issues": issues,
            "message": "Link is valid" if is_valid else f"Issues found: {'; '.join(issues)}",
        }

    def validate_all_links(self) -> list:
        """Validate all affiliate links in the database."""
        links = self.db.scalars(select(AffiliateLink)).all()
        results = []
        for link in links:
            result = self.validate_link(link.id)
            results.append(result)
        return results

    def check_expired_links(self) -> list:
        """Find all expired links that need renewal."""
        expired = self.db.scalars(
            select(AffiliateLink)
            .join(Product)
            .where(
                Product.link_expires_at.isnot(None),
                Product.link_expires_at <= datetime.utcnow(),
            )
        ).all()

        return [
            {
                "link_id": link.id,
                "url": link.url,
                "product_name": link.product.name if link.product else None,
                "expired_at": link.product.link_expires_at if link.product else None,
            }
            for link in expired
        ]

    def add_disclosure_label(self, link: AffiliateLink, label: Optional[str] = None) -> AffiliateLink:
        """Add or update disclosure label on a link."""
        if label:
            link.disclosure_label = label
        else:
            # Auto-assign based on network
            network_labels = {
                "amazon": "As an Amazon Associate, I earn from qualifying purchases",
                "clickbank": "ClickBank affiliate link",
                "cj": "CJ Affiliate link",
                "sharesale": "ShareASale affiliate link",
                "jumia": "Jumia Partners affiliate link",
            }
            link.disclosure_label = network_labels.get(
                link.product.network if link.product else "", "Affiliate link"
            )
        self.db.commit()
        self.db.refresh(link)
        return link

    def check_approved_channel(self, link: AffiliateLink) -> bool:
        """Check if the link is being used in an approved channel."""
        # This would check against ApprovedChannel table
        from ..models import ApprovedChannel

        channels = self.db.scalars(
            select(ApprovedChannel).where(ApprovedChannel.is_active == True)
        ).all()

        if not channels:
            return True  # No restrictions defined

        # In a full implementation, this would check the context where the link is used
        return link.is_approved_channel

