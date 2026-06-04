import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AffiliateLink, Product


def ensure_link(db: Session, product_id: int, partner_id: str = "default-partner") -> AffiliateLink:
    product = db.get(Product, product_id)
    if not product:
        raise ValueError("Unknown product")

    existing = db.scalar(
        select(AffiliateLink).where(
            AffiliateLink.product_id == product_id,
            AffiliateLink.partner_id == partner_id,
        )
    )
    if existing:
        return existing

    code = uuid.uuid4().hex[:12]
    url = f"https://affiliate.example.com/{partner_id}?ref={code}&product={product.product_id}"
    link = AffiliateLink(product_id=product_id, partner_id=partner_id, tracking_code=code, url=url)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
