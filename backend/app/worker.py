import os, time
from datetime import timedelta
import httpx
from rq import Worker, Queue
from sqlalchemy import select, delete
from .security import redis_client, config
from .config import settings
from .db import SessionLocal
from .models import *
from .services import gestation, enqueue
from .payments import provider, reconcile


def tick():
    with SessionLocal() as db:
        db.execute(delete(Session).where(Session.expires_at < now()))
        db.execute(delete(LinkToken).where(LinkToken.expires_at < now()))
        for task in db.scalars(
            select(Task).where(
                Task.status.in_(["queued", "processing"]),
                Task.created_at < now() - timedelta(minutes=10),
            )
        ):
            task.status = "failed"
            task.result = {
                "error": "Обработка прервалась. Повторите запрос.",
                "diagnostic_id": task.id,
            }
            if task.kind == "document":
                doc = db.get(MedicalDocument, task.payload["document_id"])
                if doc:
                    doc.status = "failed"
        db.commit()
        # Periodic notifications, with a unique key to prevent duplicates.
        for user in db.scalars(select(User).where(User.blocked.is_(False))):
            if user.preferences.get("weekly"):
                g = gestation(user.profile)
                key = f"week:{g['weeks']}" if g and g["days"] == 0 else ""
                if key and not db.scalar(
                    select(Notification).where(
                        Notification.user_id == user.id, Notification.event_key == key
                    )
                ):
                    db.add(
                        Notification(
                            user_id=user.id,
                            event_key=key,
                            due_at=now(),
                            data={
                                "text": f"Началась новая неделя вашей беременности. Подробности в Neyrix Mama."
                            },
                        )
                    )
        db.commit()
        pending = list(
            db.scalars(
                select(Notification)
                .where(Notification.status == "pending", Notification.due_at <= now())
                .limit(30)
            )
        )
        for note in pending:
            user = db.get(User, note.user_id)
            pref = "weekly" if note.event_key.startswith("week:") else "reminders"
            if not user.preferences.get(pref) or user.blocked:
                note.status = "in_app"
                continue
            identity = db.scalar(
                select(Identity).where(
                    Identity.user_id == user.id, Identity.provider == "telegram"
                )
            )
            if not identity:
                note.status = "in_app"
                continue
            try:
                response = httpx.post(
                    os.getenv("BOT_INTERNAL_URL", "http://bot:8001")
                    + "/internal/notify",
                    headers={"X-Bot-Secret": settings().bot_internal_secret},
                    json={"chat_id": identity.subject, "text": note.data["text"]},
                    timeout=10,
                )
                response.raise_for_status()
                note.status = "sent"
            except Exception:
                note.status = "in_app"  # Avoid repeated unsolicited retries; user can read it in Web.
        db.commit()
        # Reconcile pending payments to recover missed provider webhooks.
        for payment in db.scalars(
            select(Payment)
            .where(Payment.status == "pending", Payment.provider_id.is_not(None))
            .limit(20)
        ):
            try:
                reconcile(db, payment)
            except Exception:
                db.rollback()
        if settings().yookassa_shop_id and settings().yookassa_secret:
            for sub in db.scalars(
                select(Subscription).where(
                    Subscription.auto_renew.is_(True),
                    Subscription.ends_at <= now(),
                    Subscription.status.in_(["active", "past_due"]),
                )
            ):
                db.refresh(sub, with_for_update=True)
                if not sub.auto_renew or not sub.payment_method.get("id"):
                    continue
                recent = db.scalar(
                    select(Payment).where(
                        Payment.user_id == sub.user_id,
                        (Payment.created_at > now() - timedelta(days=1))
                        | (Payment.status == "pending"),
                    )
                )
                if recent:
                    continue
                payment = Payment(
                    user_id=sub.user_id,
                    amount=sub.payment_method.get("price", config(db)["price"]),
                    recurring_consent=True,
                    data={"renewal": True},
                )
                db.add(payment)
                db.commit()
                try:
                    db.refresh(sub, with_for_update=True)
                    if not sub.auto_renew or not sub.payment_method.get("id"):
                        payment.status = "canceled"
                        db.commit()
                        continue
                    result = provider.create(payment, sub.payment_method["id"])
                    payment.provider_id = result["id"]
                    db.commit()
                    reconcile(db, payment)
                except Exception:
                    db.rollback()
                    sub = db.get(Subscription, sub.user_id)
                    sub.status = "past_due"
                    db.commit()


def main():
    connection = redis_client()
    queue = Queue("mama", connection=connection)
    last_tick = 0
    # One short-lived work burst; RQ forks each heavy job, containing parser memory.
    while True:
        connection.set("mama:worker:heartbeat", str(time.time()), ex=600)
        if time.time() - last_tick > 60:
            try:
                tick()
            except Exception:
                pass
            last_tick = time.time()
        if queue.count:
            Worker([queue], connection=connection).work(
                burst=True, max_jobs=1, logging_level="WARNING"
            )
        time.sleep(1)


if __name__ == "__main__":
    main()
