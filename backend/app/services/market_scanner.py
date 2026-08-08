from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..integrations.networks import sample_products
from ..models import Product


def scan_market(db: Session) -> list[Product]:
    products = []
    for item in sample_products():
        existing = db.scalar(select(Product).where(Product.product_id == item.product_id))
        if existing:
            # Update existing product metadata
            existing.category = item.category or existing.category
            existing.image_url = item.image_url or existing.image_url
            existing.description = item.description or existing.description
            existing.affiliate_url = item.affiliate_url or existing.affiliate_url
            existing.price = item.price
            existing.commission_rate = item.commission_rate
            existing.last_scanned_at = datetime.utcnow()
            products.append(existing)
            continue
        product = Product(
            network=item.network,
            product_id=item.product_id,
            name=item.name,
            price=item.price,
            commission_rate=item.commission_rate,
            category=item.category,
            image_url=item.image_url,
            description=item.description,
            affiliate_url=item.affiliate_url,
            last_scanned_at=datetime.utcnow(),
        )
        db.add(product)
        products.append(product)
    db.commit()
    for product in products:
        db.refresh(product)
    return products
