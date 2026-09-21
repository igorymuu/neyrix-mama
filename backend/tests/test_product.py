import hashlib, hmac, json, time
from datetime import date, timedelta
from urllib.parse import urlencode
from sqlalchemy import select, func, text
from app.models import *
from app.security import digest, verify_telegram
from app.services import gestation, usage
from app.config import settings
from app.storage import validate
from app.jobs import process_task
from app.payments import reconcile
from fastapi import HTTPException
import pytest
from .conftest import make_user


def test_gestation_anchors_and_dates():
    assert gestation({"lmp": "2026-05-11"}, date(2026, 9, 18))["total_days"] == 130
    assert (
        gestation(
            {"doctor_weeks": 13, "doctor_days": 4, "doctor_date": "2026-09-10"},
            date(2026, 9, 18),
        )["total_days"]
        == 103
    )
    assert gestation({}) is None


def telegram_data(age=0, **extra):
    data = {
        "auth_date": str(int(time.time()) - age),
        "user": json.dumps({"id": 12345, "first_name": "Test"}),
        **extra,
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(
        b"WebAppData", settings().telegram_bot_token.encode(), hashlib.sha256
    ).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_telegram_signature_expiration_tamper():
    assert verify_telegram(telegram_data())["id"] == 12345
    for bad in [
        telegram_data(600),
        telegram_data(-120),
        telegram_data().replace("12345", "54321"),
        telegram_data() + "&auth_date=123",
    ]:
        with pytest.raises(HTTPException):
            verify_telegram(bad)


def test_telegram_first_web_same_identity(client, db):
    r = client.post(
        "/api/internal/telegram/register",
        headers={"X-Bot-Secret": settings().bot_internal_secret},
        json={"id": 12345, "name": "Мама"},
    )
    assert r.status_code == 200
    r = client.post("/api/auth/telegram", json={"init_data": telegram_data()})
    assert r.status_code == 200
    assert db.scalar(select(func.count()).select_from(User)) == 1
    assert client.get("/api/me").json()["identities"][0]["provider"] == "telegram"


def test_google_verifies_nonce_and_uses_subject(client, db, monkeypatch):
    challenge = client.get("/api/auth/challenge").json()["nonce"]
    claims = {
        "sub": "google-stable-id",
        "email": "a@example.test",
        "email_verified": True,
        "nonce": challenge,
    }
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_oauth2_token", lambda *a, **k: claims
    )
    assert (
        client.post("/api/auth/google", json={"credential": "signed-token"}).status_code
        == 200
    )
    assert client.get("/api/me").status_code == 200
    assert db.scalar(select(Identity)).subject == "google-stable-id"
    assert (
        client.post("/api/auth/google", json={"credential": "signed-token"}).status_code
        == 401
    )


def test_web_link_requires_two_confirmations_and_single_use(client, db, user):
    link = client.post("/api/link/telegram").json()["url"].split("link_")[1]
    r = client.post(
        "/api/internal/telegram/link",
        headers={"X-Bot-Secret": settings().bot_internal_secret},
        json={"token": link, "telegram_id": 7654},
    )
    assert r.status_code == 200
    assert db.scalar(select(Identity).where(Identity.provider == "telegram")) is None
    assert (
        client.post(
            "/api/link/telegram/confirm", json={"telegram_id": "7654"}
        ).status_code
        == 200
    )
    assert (
        db.scalar(select(Identity).where(Identity.provider == "telegram")).user_id
        == user.id
    )
    assert (
        client.post(
            "/api/link/telegram/confirm", json={"telegram_id": "7654"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/internal/telegram/link",
            headers={"X-Bot-Secret": settings().bot_internal_secret},
            json={"token": link, "telegram_id": 7654},
        ).status_code
        == 400
    )


def test_does_not_merge_existing_accounts(client, db, user):
    other = make_user(db, "bob", provider="telegram", subject="7654")
    link = client.post("/api/link/telegram").json()["url"].split("link_")[1]
    r = client.post(
        "/api/internal/telegram/link",
        headers={"X-Bot-Secret": settings().bot_internal_secret},
        json={"token": link, "telegram_id": 7654},
    )
    assert r.status_code == 409
    assert (
        db.scalar(select(Identity).where(Identity.subject == "7654")).user_id
        == other.id
    )


def test_csrf_rbac_and_ownership(client, db, user):
    assert client.get("/api/admin/config").status_code == 403
    assert (
        client.post(
            "/api/support",
            headers={"origin": "https://evil.test"},
            json={"category": "Другое", "text": "abc"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/me", headers={"X-Bot-Secret": "forged", "X-Telegram-Id": "12345"}
        ).status_code
        == 401
    )
    other = make_user(db, "bob")
    doc = MedicalDocument(
        user_id=other.id, storage_key="not-there", details={"name": "private.pdf"}
    )
    db.add(doc)
    db.commit()
    assert client.get("/api/documents/" + doc.id + "/download").status_code == 404
    assert (
        client.post(
            "/api/documents/" + doc.id + "/confirm", json={"records": []}
        ).status_code
        == 404
    )


def test_no_demo_data_and_encrypted_profile(client, db, user):
    assert client.get("/api/records").json() == []
    assert client.get("/api/documents").json() == []
    assert (
        client.put(
            "/api/profile", json={"name": "Секретное имя", "lmp": "2026-05-11"}
        ).status_code
        == 200
    )
    raw = db.execute(
        text("SELECT profile FROM users WHERE id=:id"), {"id": user.id}
    ).scalar()
    assert "Секретное" not in raw
    assert len(list(db.scalars(select(ProfileChange)))) == 1


def test_reject_future_measurements_and_impossible_bp(client, db, user):
    bad = {
        "kind": "blood_pressure",
        "value": 80,
        "secondary": 120,
        "recorded_at": now().isoformat(),
    }
    assert client.post("/api/records", json=bad).status_code == 422
    future = {
        "kind": "weight",
        "value": 60,
        "recorded_at": (now() + timedelta(days=2)).isoformat(),
    }
    assert client.post("/api/records", json=future).status_code == 422


def test_document_validation_and_confirmation_idempotency(client, db, user):
    assert (
        client.post(
            "/api/documents", files={"file": ("bad.png", b"<script>", "image/png")}
        ).status_code
        == 422
    )
    r = client.post(
        "/api/documents",
        files={"file": ("lab.txt", "Гемоглобин: 118 г/л".encode(), "text/plain")},
    )
    assert r.status_code == 200
    doc = db.get(MedicalDocument, r.json()["id"])
    doc.status = "review"
    doc.extraction = {"confidence": 0.9, "gestation_proposal": {"weeks": 20}}
    db.commit()
    old = dict(user.profile)
    body = {
        "records": [
            {
                "kind": "lab",
                "title": "Гемоглобин",
                "value": 118,
                "unit": "г/л",
                "recorded_at": now().isoformat(),
            }
        ]
    }
    for _ in range(2):
        assert (
            client.post("/api/documents/" + doc.id + "/confirm", json=body).status_code
            == 200
        )
    assert db.scalar(select(func.count()).select_from(Record)) == 1
    db.refresh(user)
    assert user.profile == old
    record = db.scalar(select(Record))
    assert record.provenance["confirmed_by"] == user.id
    from app import storage

    raw = storage.path_for(doc.storage_key).read_bytes()
    assert b"118" not in raw
    assert client.get("/api/documents/" + doc.id + "/download").status_code == 200


def test_limits_only_count_successful_or_reserved_user_questions(client, db, user):
    for _ in range(5):
        task = Task(user_id=user.id, kind="chat", status="done", payload={})
        db.add(task)
    db.add(Task(user_id=user.id, kind="chat", status="failed", payload={}))
    db.add(Task(user_id=user.id, kind="document", status="done", payload={}))
    db.commit()
    assert usage(db, user.id)["remaining"] == 0
    assert client.post("/api/chat", json={"text": "Привет"}).status_code == 429
    assert client.get("/api/records").status_code == 200
    assert (
        client.post(
            "/api/support", json={"category": "Другое", "text": "Помогите"}
        ).status_code
        == 200
    )


def test_worker_chat_uses_same_history_and_failure_refunds(db, user, monkeypatch):
    task = Task(
        user_id=user.id, kind="chat", payload={"text": "Как подготовиться к приёму?"}
    )
    db.add(task)
    db.commit()
    monkeypatch.setattr(
        "app.jobs.complete", lambda *a, **k: "Подготовьте список вопросов врачу."
    )
    process_task(task.id)
    db.expire_all()
    assert db.get(Task, task.id).status == "done"
    assert db.scalar(select(func.count()).select_from(ChatMessage)) == 2
    task2 = Task(user_id=user.id, kind="chat", payload={"text": "Ещё вопрос"})
    db.add(task2)
    db.commit()
    monkeypatch.setattr(
        "app.jobs.complete",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("AI не подключён")),
    )
    process_task(task2.id)
    db.expire_all()
    assert db.get(Task, task2.id).status == "failed"
    assert usage(db, user.id)["used"] == 1


def test_emergency_answer_without_provider(db, user, monkeypatch):
    task = Task(
        user_id=user.id, kind="chat", payload={"text": "У меня давление 170/115"}
    )
    db.add(task)
    db.commit()
    monkeypatch.setattr(
        "app.jobs.complete", lambda *a, **k: pytest.fail("Provider must not be called")
    )
    process_task(task.id)
    db.expire_all()
    assert "112/103" in db.get(Task, task.id).result["text"]


def test_payment_verified_idempotent_cancel_preserves_period(
    client, db, user, monkeypatch
):
    payment = Payment(
        user_id=user.id, provider_id="provider-1", amount=499, recurring_consent=True
    )
    db.add(payment)
    db.commit()
    verified = {
        "id": "provider-1",
        "status": "succeeded",
        "paid": True,
        "metadata": {"payment_id": payment.id, "user_id": user.id},
        "amount": {"value": "499.00", "currency": "RUB"},
        "payment_method": {"id": "saved-card", "saved": True},
    }
    monkeypatch.setattr("app.payments.provider.fetch", lambda _: verified)
    for _ in range(2):
        assert (
            client.post(
                "/api/payments/webhook", json={"object": {"id": "provider-1"}}
            ).status_code
            == 200
        )
    sub = db.get(Subscription, user.id)
    end = sub.ends_at
    assert 27 < (end - now()).days < 32
    assert sub.auto_renew
    assert client.post("/api/subscription/cancel").status_code == 200
    assert not sub.auto_renew and sub.ends_at == end
    assert usage(db, user.id)["limit"] == 20


def test_spoofed_payment_amount_never_grants_access(client, db, user, monkeypatch):
    payment = Payment(user_id=user.id, provider_id="provider-1", amount=499)
    db.add(payment)
    db.commit()
    monkeypatch.setattr(
        "app.payments.provider.fetch",
        lambda _: {"id": "provider-1", "amount": {"value": "1.00", "currency": "RUB"}},
    )
    assert (
        client.post(
            "/api/payments/webhook",
            json={"object": {"id": "provider-1", "status": "succeeded"}},
        ).status_code
        == 400
    )
    assert db.get(Subscription, user.id).status == "trialing"


def test_cancel_pending_checkout_cannot_reenable_autorenew(
    client, db, user, monkeypatch
):
    p = Payment(user_id=user.id, provider_id="late", amount=499, recurring_consent=True)
    db.add(p)
    db.commit()
    assert client.post("/api/subscription/cancel").status_code == 200
    monkeypatch.setattr(
        "app.payments.provider.fetch",
        lambda _: {
            "id": "late",
            "status": "succeeded",
            "paid": True,
            "metadata": {"payment_id": p.id, "user_id": user.id},
            "amount": {"value": "499.00", "currency": "RUB"},
            "payment_method": {"id": "card", "saved": True},
        },
    )
    assert (
        client.post(
            "/api/payments/webhook", json={"object": {"id": "late"}}
        ).status_code
        == 200
    )
    assert db.get(Subscription, user.id).auto_renew is False


def test_admin_changes_are_audited(client, db, user):
    user.role = "admin"
    db.commit()
    other = make_user(db, "bob")
    assert (
        client.patch("/api/admin/users/" + other.id, json={"months": 3}).status_code
        == 200
    )
    assert db.get(Subscription, other.id).status == "active"
    assert (
        db.scalar(
            select(AuditLog).where(AuditLog.action == "admin.user.update")
        ).actor_id
        == user.id
    )


def test_account_deletion_cascades_private_data(client, db, user):
    db.add(
        Record(
            user_id=user.id, kind="note", data={"notes": "secret"}, recorded_at=now()
        )
    )
    db.add(ChatMessage(user_id=user.id, role="user", content={"text": "secret"}))
    db.commit()
    assert (
        client.request(
            "DELETE", "/api/account", json={"confirmation": "wrong"}
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE", "/api/account", json={"confirmation": "УДАЛИТЬ"}
        ).status_code
        == 200
    )
    assert db.scalar(select(func.count()).select_from(Record)) == 0
    assert db.scalar(select(func.count()).select_from(ChatMessage)) == 0
    assert client.get("/api/me").status_code == 401


def test_knowledge_excludes_personal_seed():
    from pathlib import Path

    knowledge = (Path(__file__).parents[1] / "knowledge/pregnancy_rf_v2.md").read_text()
    prompt = (Path(__file__).parents[1] / "knowledge/system_prompt.txt").read_text()
    assert "ИСХОДНЫЙ ПЕРСОНАЛЬНЫЙ ПРОФИЛЬ" not in knowledge
    assert "ПЕРСОНАЛЬНАЯ СТРАТЕГИЯ ДЛЯ ЭТОЙ ЖЕНЩИНЫ" not in knowledge
    assert "рост 160 см" not in prompt


def test_document_worker_extracts_without_mutating_profile(db, user, monkeypatch):
    from app import storage

    doc = MedicalDocument(
        user_id=user.id,
        storage_key=user.id + "/fixture",
        details={"name": "lab.txt", "mime": "text/plain"},
        status="queued",
    )
    storage.save(doc.storage_key, "Гемоглобин 118 г/л, 18.09.2026".encode())
    db.add(doc)
    db.commit()
    task = Task(user_id=user.id, kind="document", payload={"document_id": doc.id})
    db.add(task)
    db.commit()
    monkeypatch.setattr(
        "app.jobs.complete",
        lambda *a, **k: {
            "title": "ОАК",
            "date": "2026-09-18",
            "confidence": 0.9,
            "values": [{"title": "Гемоглобин", "value": 118, "unit": "г/л"}],
        },
    )
    process_task(task.id)
    db.expire_all()
    assert db.get(MedicalDocument, doc.id).status == "review"
    assert db.get(MedicalDocument, doc.id).extraction["verified"] is False
    assert db.scalar(select(func.count()).select_from(Record)) == 0


def test_retrieval_respects_disabled_knowledge(db):
    from app.knowledge import index_document, retrieve

    doc = KnowledgeDocument(
        name="fixture",
        content="# Гемоглобин\nГемоглобин оценивается с учётом срока и единиц.",
        metadata_={},
    )
    db.add(doc)
    db.commit()
    index_document(db, doc)
    assert retrieve(db, "Что такое гемоглобин?")[0]["topic"] == "Гемоглобин"
    doc.enabled = False
    db.commit()
    assert retrieve(db, "Гемоглобин") == []


def test_trial_expired_data_still_accessible(client, db, user):
    sub = db.get(Subscription, user.id)
    sub.ends_at = now() - timedelta(days=1)
    db.commit()
    assert client.get("/api/records").status_code == 200
    assert client.get("/api/export").status_code == 200
    assert client.post("/api/chat", json={"text": "Вопрос"}).status_code == 429


def test_recurring_keeps_consented_price(db, user, monkeypatch):
    from app.worker import tick

    sub = db.get(Subscription, user.id)
    sub.status = "active"
    sub.ends_at = now() - timedelta(days=1)
    sub.auto_renew = True
    sub.payment_method = {"id": "card", "price": 499}
    cfg = db.get(AgentConfiguration, 1)
    cfg.data = {**cfg.data, "price": 999}
    db.commit()
    monkeypatch.setattr(settings(), "yookassa_shop_id", "fixture")
    monkeypatch.setattr(settings(), "yookassa_secret", "fixture")
    captured = []

    def create(payment, method):
        captured.append(payment.amount)
        return {"id": "renewal-fixture"}

    monkeypatch.setattr("app.worker.provider.create", create)
    monkeypatch.setattr("app.worker.reconcile", lambda *a: None)
    tick()
    assert captured == [499]
    tick()
    assert captured == [499]  # pending charge prevents another automatic attempt
