from sqlalchemy import select
from sqlalchemy.orm import Session

from ..integrations.networks import sample_products
from ..models import Product


def scan_market(db: Session) -> list[Product]:
    products = []
    for item in sample_products():
        existing = db.scalar(select(Product).where(Product.product_id == item.product_id))
        if existing:
            products.append(existing)
            continue
        product = Product(
            network=item.network,
            product_id=item.product_id,
            name=item.name,
            price=item.price,
            commission_rate=item.commission_rate,
        )
        db.add(product)
        products.append(product)
    db.commit()
    for product in products:
        db.refresh(product)
    return products
