"""Click Tracking Service

Tracks clicks on affiliate links with IP, user-agent, referrer, and geo data.
Tracks conversions and provides link analytics.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AffiliateLink, Click, Purchase


class ClickTracker:
    """Tracks clicks and conversions on affiliate links."""

    def __init__(self, db: Session):
        self.db = db

    def record_click(
        self,
        tracking_code: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referrer: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Click:
        """Record a click on an affiliate link."""
        link = self.db.scalar(
            select(AffiliateLink).where(AffiliateLink.tracking_code == tracking_code)
        )
        if not link:
            raise ValueError(f"Tracking code not found: {tracking_code}")

        click = Click(
            link_id=link.id,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer,
            country=country,
        )
        self.db.add(click)

        # Update click count on link
        link.click_count = (link.click_count or 0) + 1
        self.db.commit()
        self.db.refresh(click)
        return click

    def record_conversion(
        self, click_id: int, purchase_id: int
    ) -> None:
        """Link a purchase to a click (conversion tracking)."""
        purchase = self.db.get(Purchase, purchase_id)
        if purchase:
            purchase.click_id = click_id
            link = self.db.get(AffiliateLink, purchase.link_id)
            if link:
                link.conversion_count = (link.conversion_count or 0) + 1
            self.db.commit()

    def get_link_analytics(self, link_id: int) -> dict:
        """Get analytics for a specific affiliate link."""
        link = self.db.get(AffiliateLink, link_id)
        if not link:
            raise ValueError(f"Link not found: {link_id}")

        total_clicks = self.db.scalar(
            select(func.count(Click.id)).where(Click.link_id == link_id)
        ) or 0
        total_conversions = (
            self.db.scalar(
                select(func.count(Purchase.id)).where(
                    Purchase.link_id == link_id,
                    Purchase.click_id.isnot(None),
                )
            ) or 0
        )

        return {
            "link_id": link.id,
            "url": link.url,
            "tracking_code": link.tracking_code,
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "conversion_rate": round(
                (total_conversions / total_clicks * 100) if total_clicks > 0 else 0, 2
            ),
            "disclosure_label": link.disclosure_label,
        }

    def get_top_performing_links(self, limit: int = 10) -> list:
        """Get top performing affiliate links by conversion rate."""
        links = (
            self.db.execute(
                select(
                    AffiliateLink,
                    func.count(Click.id).label("click_count"),
                    func.count(Purchase.id).label("conversion_count"),
                )
                .outerjoin(Click, Click.link_id == AffiliateLink.id)
                .outerjoin(Purchase, Purchase.link_id == AffiliateLink.id)
                .group_by(AffiliateLink.id)
                .order_by(func.count(Purchase.id).desc())
                .limit(limit)
            )
            .all()
        )

        results = []
        for link, clicks, conversions in links:
            results.append({
                "link_id": link.id,
                "url": link.url,
                "tracking_code": link.tracking_code,
                "product_name": link.product.name if link.product else None,
                "clicks": clicks,
                "conversions": conversions,
                "conversion_rate": round(
                    (conversions / clicks * 100) if clicks > 0 else 0, 2
                ),
            })
        return results

    def get_overall_analytics(self) -> dict:
        """Get overall analytics across all links."""
        total_clicks = self.db.scalar(select(func.count(Click.id))) or 0
        total_conversions = (
            self.db.scalar(
                select(func.count(Purchase.id)).where(
                    Purchase.click_id.isnot(None)
                )
            ) or 0
        )
        total_links = self.db.scalar(select(func.count(AffiliateLink.id))) or 0

        # Get clicks by country
        clicks_by_country = (
            self.db.execute(
                select(Click.country, func.count(Click.id))
                .where(Click.country.isnot(None))
                .group_by(Click.country)
                .order_by(func.count(Click.id).desc())
            )
            .all()
        )

        # Get clicks by referrer
        clicks_by_referrer = (
            self.db.execute(
                select(Click.referrer, func.count(Click.id))
                .where(Click.referrer.isnot(None))
                .group_by(Click.referrer)
                .order_by(func.count(Click.id).desc())
                .limit(10)
            )
            .all()
        )

        return {
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "overall_conversion_rate": round(
                (total_conversions / total_clicks * 100) if total_clicks > 0 else 0, 2
            ),
            "total_links": total_links,
            "clicks_by_country": [
                {"country": c, "count": cnt} for c, cnt in clicks_by_country
            ],
            "top_referrers": [
                {"referrer": r, "count": cnt} for r, cnt in clicks_by_referrer
            ],
        }

