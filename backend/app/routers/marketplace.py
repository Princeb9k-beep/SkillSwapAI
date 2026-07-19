"""
Marketplace (spec §3.7) — paid tutoring / coaching / courses / templates.

Sellers create listings; buyers book them, which creates an order and computes the
platform commission. **Payment capture is intentionally NOT implemented here** — that
requires a Stripe (or similar) integration with server-side secrets and a webhook to
flip `order.paid`. Orders are recorded as `requested`; the seller confirms/completes
fulfillment. Commission is real and computed on booking.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import MarketplaceListing, MarketplaceOrder, User
from ..responses import error, ok
from ..schemas import ListingCreate, OrderStatusUpdate

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

COMMISSION_RATE = 0.15  # platform take

# Who may move an order to a given status.
_SELLER_TRANSITIONS = {"confirmed", "completed"}
_BUYER_TRANSITIONS = {"cancelled"}


def _listing_dict(listing: MarketplaceListing, seller_name: str) -> dict:
    return {
        "id": listing.id,
        "seller_id": listing.seller_id,
        "seller_name": seller_name,
        "title": listing.title,
        "kind": listing.kind,
        "description": listing.description,
        "price_cents": listing.price_cents,
        "currency": listing.currency,
    }


def _order_dict(o: MarketplaceOrder, title: str, counterparty: str) -> dict:
    return {
        "id": o.id,
        "listing_title": title,
        "counterparty": counterparty,
        "price_cents": o.price_cents,
        "commission_cents": o.commission_cents,
        "seller_net_cents": o.price_cents - o.commission_cents,
        "status": o.status,
        "paid": o.paid,
    }


@router.get("/listings")
async def list_listings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Browse active listings from other sellers."""
    rows = await session.execute(
        select(MarketplaceListing, User.name)
        .join(User, User.id == MarketplaceListing.seller_id)
        .where(MarketplaceListing.active.is_(True), MarketplaceListing.seller_id != user.id)
        .order_by(MarketplaceListing.created_at.desc())
    )
    data = [_listing_dict(l, name or f"Learner #{l.seller_id}") for l, name in rows.all()]
    return ok(data=data, meta={"commission_rate": COMMISSION_RATE})


@router.get("/listings/mine")
async def my_listings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    rows = await session.execute(
        select(MarketplaceListing)
        .where(MarketplaceListing.seller_id == user.id)
        .order_by(MarketplaceListing.created_at.desc())
    )
    return ok(data=[_listing_dict(l, user.name or f"Learner #{user.id}") for l in rows.scalars().all()])


@router.post("/listings")
async def create_listing(
    payload: ListingCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    listing = MarketplaceListing(
        seller_id=user.id,
        title=payload.title.strip(),
        kind=payload.kind,
        description=payload.description,
        price_cents=payload.price_cents,
    )
    session.add(listing)
    await session.commit()
    return ok(
        data=_listing_dict(listing, user.name or f"Learner #{user.id}"),
        message="Listing published",
        status_code=201,
    )


@router.post("/listings/{listing_id}/book")
async def book(
    listing_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Book a listing — records an order + commission (payment handled later)."""
    listing = await session.get(MarketplaceListing, listing_id)
    if listing is None or not listing.active:
        return error("Listing not found.", status_code=404, code="not_found")
    if listing.seller_id == user.id:
        return error("You can't book your own listing.", status_code=403, code="forbidden")

    commission = round(listing.price_cents * COMMISSION_RATE)
    order = MarketplaceOrder(
        listing_id=listing.id,
        buyer_id=user.id,
        seller_id=listing.seller_id,
        price_cents=listing.price_cents,
        commission_cents=commission,
        status="requested",
        paid=False,
    )
    session.add(order)
    await session.commit()
    return ok(
        data=_order_dict(order, listing.title, "seller"),
        message="Booked — payment is not yet enabled; the seller will confirm.",
        status_code=201,
    )


@router.get("/orders")
async def my_orders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """My orders as a buyer and as a seller."""
    rows = await session.execute(
        select(MarketplaceOrder, MarketplaceListing.title)
        .join(MarketplaceListing, MarketplaceListing.id == MarketplaceOrder.listing_id)
        .where(or_(MarketplaceOrder.buyer_id == user.id, MarketplaceOrder.seller_id == user.id))
        .order_by(MarketplaceOrder.created_at.desc())
    )
    as_buyer, as_seller = [], []
    for o, title in rows.all():
        if o.buyer_id == user.id:
            as_buyer.append(_order_dict(o, title, "seller"))
        if o.seller_id == user.id:
            as_seller.append(_order_dict(o, title, "buyer"))
    return ok(data={"as_buyer": as_buyer, "as_seller": as_seller})


@router.patch("/orders/{order_id}")
async def update_order(
    order_id: int,
    payload: OrderStatusUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Seller confirms/completes; buyer may cancel a still-requested order."""
    order = await session.get(MarketplaceOrder, order_id)
    if order is None:
        return error("Order not found.", status_code=404, code="not_found")

    is_seller = order.seller_id == user.id
    is_buyer = order.buyer_id == user.id
    allowed = (is_seller and payload.status in _SELLER_TRANSITIONS) or (
        is_buyer and payload.status in _BUYER_TRANSITIONS
    )
    if not allowed:
        return error("You can't make that change.", status_code=403, code="forbidden")
    if payload.status == "cancelled" and order.status != "requested":
        return error("Only a requested order can be cancelled.", status_code=409, code="conflict")

    order.status = payload.status
    await session.commit()
    return ok(data=_order_dict(order, "", "counterparty"), message="Order updated")
