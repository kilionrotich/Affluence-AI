from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..integrations.networks import sample_products
from ..models import Product
from .audit_logger import AuditLogger


def scan_market(db: Session) -> list[Product]:
    """Scan the market for products, logging every action persistently."""
    logger = AuditLogger(db)
    products = []
    new_count = 0
    updated_count = 0
    per_network = Counter()
    new_products = []

    for item in sample_products():
        per_network[item.network] += 1
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
            updated_count += 1
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
        new_products.append(product)
        new_count += 1

    db.commit()
    for product in products:
        db.refresh(product)

    # ── Persistent audit logging ───────────────────────────────────
    # Log each newly discovered product
    for product in new_products:
        logger.log_new_product(product.id, product.network, product.name)

    # Log per-network scan results
    for network, count in per_network.items():
        logger.log_ai_scan(network, count, 0, count)

    # Overall scan log
    logger.log_scan(len(products))

    return products
