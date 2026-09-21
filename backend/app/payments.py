from calendar import monthrange
from datetime import timedelta
from typing import Protocol
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from .models import Payment, Subscription, now
from .config import settings


class PaymentProvider(Protocol):
    def create(self, payment: Payment, saved_method: str | None = None) -> dict: ...
    def fetch(self, provider_id: str) -> dict: ...
    def refund(self, payment: Payment) -> dict: ...


class YooKassa:
    def request(self, method, path, body=None, key=None):
        s = settings()
        if not s.yookassa_shop_id or not s.yookassa_secret:
            raise HTTPException(
                503, "Оплата пока не подключена. Ваши данные остаются доступны."
            )
        response = httpx.request(
            method,
            "https://api.yookassa.ru/v3/" + path,
            auth=(s.yookassa_shop_id, s.yookassa_secret),
            headers={"Idempotence-Key": key} if key else {},
            json=body,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def create(self, payment, saved_method=None):
        data = {
            "amount": {"value": f"{payment.amount}.00", "currency": "RUB"},
            "capture": True,
            "description": "Neyrix Mama — подписка на месяц",
            "metadata": {"payment_id": payment.id, "user_id": payment.user_id},
        }
        if saved_method:
            data["payment_method_id"] = saved_method
        else:
            data["confirmation"] = {
                "type": "redirect",
                "return_url": settings().app_url + "/subscription",
            }
            data["save_payment_method"] = payment.recurring_consent
        return self.request("POST", "payments", data, payment.id)

    def fetch(self, provider_id):
        from urllib.parse import quote

        return self.request("GET", "payments/" + quote(provider_id, safe=""))

    def refund(self, payment):
        return self.request(
            "POST",
            "refunds",
            {
                "payment_id": payment.provider_id,
                "amount": {"value": f"{payment.amount}.00", "currency": "RUB"},
            },
            "refund-" + payment.id,
        )


provider: PaymentProvider = YooKassa()


def add_months(value, months=1):
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return value.replace(
        year=year, month=month, day=min(value.day, monthrange(year, month)[1])
    )


def reconcile(db, payment):
    # All payment transitions lock subscription before payment to avoid lock inversion.
    sub = db.scalar(
        select(Subscription)
        .where(Subscription.user_id == payment.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not payment or payment.status in ("succeeded", "refunded"):
        return
    result = provider.fetch(payment.provider_id)
    if (
        result.get("id") != payment.provider_id
        or result.get("metadata", {}).get("payment_id") != payment.id
        or result.get("metadata", {}).get("user_id") != payment.user_id
        or result.get("amount") != {"value": f"{payment.amount}.00", "currency": "RUB"}
    ):
        raise HTTPException(400, "Платёж не прошёл проверку.")
    if payment.status in ("succeeded", "refunded"):
        return
    if result.get("status") == "succeeded" and result.get("paid") is True:
        sub = db.scalar(
            select(Subscription)
            .where(Subscription.user_id == payment.user_id)
            .with_for_update()
        )
        payment.status = "succeeded"
        start = (
            max(now(), sub.ends_at) if sub.status in ("active", "cancelled") else now()
        )
        sub.ends_at = add_months(start)
        sub.status = "active"
        method = result.get("payment_method", {})
        # Cancellation always wins over a previously started recurring charge.
        if (
            payment.recurring_consent
            and method.get("saved")
            and not payment.data.get("renewal")
        ):
            sub.payment_method = {
                "id": method["id"],
                "price": payment.amount,
                "consent_at": payment.created_at.isoformat(),
            }
            sub.auto_renew = True
        db.commit()
    elif result.get("status") == "canceled":
        payment.status = "canceled"
        sub = db.get(Subscription, payment.user_id)
        if payment.data.get("renewal"):
            sub.status = "past_due"
        db.commit()
