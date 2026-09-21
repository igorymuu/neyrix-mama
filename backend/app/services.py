from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from fastapi import HTTPException
from rq import Queue
from .models import *
from .security import config, redis_client, audit
from .config import settings


def gestation(profile, today=None):
    today = today or date.today()
    due = None
    source = None
    if profile.get("doctor_weeks") is not None and profile.get("doctor_date"):
        anchor = date.fromisoformat(profile["doctor_date"])
        days = (
            int(profile["doctor_weeks"]) * 7
            + int(profile.get("doctor_days") or 0)
            + (today - anchor).days
        )
        due, source = today + timedelta(days=280 - days), "Срок, установленный врачом"
    elif profile.get("due_date"):
        due, source = date.fromisoformat(profile["due_date"]), "ПДР из профиля"
        days = 280 - (due - today).days
    elif profile.get("lmp"):
        days = (today - date.fromisoformat(profile["lmp"])).days
        due, source = today + timedelta(days=280 - days), "Дата последней менструации"
    else:
        return None
    if days < 0:
        return None
    return {
        "weeks": days // 7,
        "days": days % 7,
        "total_days": days,
        "due_date": due.isoformat(),
        "remaining": max(0, (due - today).days),
        "source": source,
    }


def usage(db, user_id):
    sub = db.get(Subscription, user_id)
    c = config(db)
    status = (
        sub.status
        if sub.ends_at > now()
        else ("expired" if sub.status != "past_due" else "past_due")
    )
    limit = (
        sub.daily_limit
        if sub.daily_limit is not None
        else c["trial_limit"]
        if status == "trialing"
        else c["paid_limit"]
        if status in ("active", "cancelled")
        else 0
    )
    moscow = datetime.now(ZoneInfo("Europe/Moscow"))
    start = (
        moscow.replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    used = (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == user_id,
                Task.kind == "chat",
                Task.created_at >= start,
                Task.status != "failed",
            )
        )
        or 0
    )
    return {
        "status": status,
        "ends_at": sub.ends_at.isoformat() + "Z",
        "auto_renew": sub.auto_renew,
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "resets_at": (start + timedelta(days=1)).isoformat() + "Z",
        "price": c["price"],
    }


def enqueue(task):
    Queue("mama", connection=redis_client()).enqueue(
        "app.jobs.process_task",
        task.id,
        job_id=task.id,
        job_timeout=240,
        result_ttl=0,
        failure_ttl=86400,
    )


def submit(db, user_id, kind, payload):
    task = Task(user_id=user_id, kind=kind, payload=payload)
    db.add(task)
    db.commit()
    try:
        enqueue(task)
    except Exception:
        task.status = "failed"
        task.result = {
            "error": "Не получилось поставить задачу в очередь. Попробуйте ещё раз."
        }
        db.commit()
        raise HTTPException(503, task.result["error"])
    return {"task_id": task.id, "status": task.status}


def save_profile(db, user, profile, source="user"):
    new = profile.model_dump(mode="json") if hasattr(profile, "model_dump") else profile
    db.add(
        ProfileChange(
            user_id=user.id,
            data={
                "before": user.profile,
                "after": new,
                "source": source,
                "confirmed_by": user.id,
            },
        )
    )
    user.profile = new
    audit(db, user.id, "profile.update")


def add_record(db, user, record, document=None, confidence=None):
    data = record.model_dump(mode="json")
    when = record.recorded_at
    if when.tzinfo:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    row = Record(
        user_id=user.id,
        kind=record.kind,
        data=data,
        recorded_at=when,
        document_id=document,
        provenance={
            "source": "document" if document else "user",
            "document_id": document,
            "confidence": confidence,
            "confirmed": True,
            "confirmed_by": user.id,
            "confirmed_at": now().isoformat(),
        },
    )
    db.add(row)
    db.flush()
    if record.kind == "event":
        db.add(
            Notification(
                user_id=user.id,
                event_key="event:" + row.id,
                due_at=when - timedelta(days=1),
                data={
                    "title": record.title,
                    "text": "Напоминание о вашем событии. Подробности доступны в приложении.",
                },
            )
        )
    return row


def serialize_record(row):
    return {
        "id": row.id,
        **row.data,
        "kind": row.kind,
        "recorded_at": row.recorded_at.isoformat() + "Z",
        "provenance": row.provenance,
        "document_id": row.document_id,
    }


def serialize_doc(row):
    return {
        "id": row.id,
        **row.details,
        "status": row.status,
        "extraction": row.extraction,
        "created_at": row.created_at.isoformat() + "Z",
    }
