from dataclasses import dataclass


@dataclass
class NetworkProduct:
    network: str
    product_id: str
    name: str
    price: float
    commission_rate: float


def sample_products() -> list[NetworkProduct]:
    return [
        NetworkProduct("amazon", "amz-1001", "Smart Speaker", 99.99, 0.04),
        NetworkProduct("clickbank", "cb-220", "Fitness Program", 49.0, 0.45),
        NetworkProduct("cj", "cj-773", "Cloud Storage", 120.0, 0.2),
        NetworkProduct("jumia", "jum-981", "Air Fryer", 80.0, 0.08),
    ]
