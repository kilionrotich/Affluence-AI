from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, engine, get_db
from .models import ApiCredential
from .schemas import (
    CredentialPayload,
    PayoutRequest,
    PayoutResponse,
    PurchaseRequest,
    PurchaseResponse,
    ReportResponse,
    ScanResponse,
    ValidateResponse,
)
from .security import EncryptionManager, require_role
from .services import commission_validator, link_generator, market_scanner, purchase_tracker, reporting, withdrawal_handler
from .services.alerts import send_threshold_alert
from .services.payout_monitor import balances

scheduler = BackgroundScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(_scheduled_validate, "interval", minutes=30, id="validate", replace_existing=True)
    scheduler.add_job(_scheduled_threshold_check, "interval", minutes=15, id="threshold_check", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Affiliate Commission Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _scheduled_validate() -> None:
    db = next(get_db())
    try:
        commission_validator.validate_commissions(db)
    finally:
        db.close()


def _scheduled_threshold_check() -> None:
    db = next(get_db())
    try:
        _, confirmed = balances(db)
        settings = get_settings()
        if confirmed >= settings.payout_threshold:
            send_threshold_alert(confirmed)
    finally:
        db.close()


@app.middleware("http")
async def enforce_https(request: Request, call_next):
    if get_settings().require_https and request.url.scheme != "https":
        raise HTTPException(status_code=400, detail="HTTPS is required")
    return await call_next(request)


@app.post("/scan", response_model=ScanResponse)
def scan(db: Session = Depends(get_db), _: str = Depends(require_role({"admin"}))):
    products = market_scanner.scan_market(db)
    links = [link_generator.ensure_link(db, p.id) for p in products]
    return {
        "inserted": len(products),
        "products": [
            {
                "id": p.id,
                "network": p.network,
                "product_id": p.product_id,
                "name": p.name,
                "price": p.price,
                "commission_rate": p.commission_rate,
                "link": links[idx].url,
                "tracking_code": links[idx].tracking_code,
            }
            for idx, p in enumerate(products)
        ],
    }


@app.post("/purchase", response_model=PurchaseResponse)
def purchase(payload: PurchaseRequest, db: Session = Depends(get_db), _: str = Depends(require_role({"admin"}))):
    settings = get_settings()
    try:
        purchase_row, commission = purchase_tracker.record_purchase(
            db,
            payload.tracking_code,
            payload.amount,
            settings.refund_period_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "purchase_id": purchase_row.id,
        "commission_id": commission.id,
        "commission_amount": commission.amount,
    }


@app.post("/validate", response_model=ValidateResponse)
def validate(db: Session = Depends(get_db), _: str = Depends(require_role({"admin"}))):
    return {"confirmed": commission_validator.validate_commissions(db)}


@app.post("/payout", response_model=PayoutResponse)
def payout(payload: PayoutRequest, db: Session = Depends(get_db), _: str = Depends(require_role({"admin"}))):
    settings = get_settings()
    try:
        result = withdrawal_handler.trigger_payout(db, payload.method, settings.payout_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "payout_id": result.id,
        "amount": result.amount,
        "method": result.method,
        "transaction_ref": result.transaction_ref,
    }


@app.get("/report", response_model=ReportResponse)
def report(db: Session = Depends(get_db), _: str = Depends(require_role({"admin", "viewer"}))):
    return reporting.generate_report(db)


@app.post("/credentials")
def save_credential(payload: CredentialPayload, db: Session = Depends(get_db), _: str = Depends(require_role({"admin"}))):
    enc = EncryptionManager()
    existing = db.query(ApiCredential).filter(ApiCredential.provider == payload.provider).first()
    if existing:
        existing.encrypted_key = enc.encrypt(payload.api_key)
    else:
        db.add(ApiCredential(provider=payload.provider, encrypted_key=enc.encrypt(payload.api_key)))
    db.commit()
    return {"status": "stored"}
