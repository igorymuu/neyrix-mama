import hashlib, hmac, json, secrets, time
from datetime import timedelta
from urllib.parse import parse_qsl
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from redis import Redis
from .config import settings
from .db import get_db
from .models import (
    User,
    Session,
    Identity,
    Subscription,
    AgentConfiguration,
    AuditLog,
    now,
)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def audit(db, actor, action, target=None):
    db.add(AuditLog(actor_id=actor, action=action, target=target))


def config(db):
    row = db.get(AgentConfiguration, 1)
    return (
        row.data
        if row
        else {
            "price": 499,
            "trial_days": 30,
            "trial_limit": 5,
            "paid_limit": 20,
            "max_tokens": 1200,
            "temperature": 0.3,
            "timeout": 60,
            "features": {},
        }
    )


def redis_client():
    return Redis.from_url(settings().redis_url)


def rate_limit(key, limit=60, seconds=60):
    try:
        count = redis_client().eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
            1,
            "rate:" + key,
            seconds,
        )
        if count > limit:
            raise HTTPException(
                429,
                "Слишком много запросов. Попробуйте чуть позже.",
                headers={"Retry-After": str(seconds)},
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Сервис временно недоступен. Попробуйте позже.")


def new_user(db, provider, subject, info):
    identity = db.scalar(
        select(Identity).where(
            Identity.provider == provider, Identity.subject == subject
        )
    )
    if identity:
        user = db.get(User, identity.user_id)
        if user.blocked:
            raise HTTPException(403, "Доступ ограничен. Обратитесь в поддержку.")
        identity.info = info
        return user
    user = User(profile={})
    db.add(user)
    db.flush()
    db.add(Identity(user_id=user.id, provider=provider, subject=subject, info=info))
    db.add(
        Subscription(
            user_id=user.id, ends_at=now() + timedelta(days=config(db)["trial_days"])
        )
    )
    return user


def set_session(db, response: Response, user):
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=now() + timedelta(days=7),
        )
    )
    response.set_cookie(
        "mama_session",
        token,
        httponly=True,
        secure=settings().production,
        samesite="lax",
        max_age=604800,
        path="/",
    )
    db.commit()


def current_user(request: Request, db=Depends(get_db)):
    internal = request.headers.get("X-Bot-Secret", "")
    if internal:
        if not hmac.compare_digest(internal, settings().bot_internal_secret):
            raise HTTPException(401, "Войдите в аккаунт.")
        identity = db.scalar(
            select(Identity).where(
                Identity.provider == "telegram",
                Identity.subject == request.headers.get("X-Telegram-Id", ""),
            )
        )
        user = db.get(User, identity.user_id) if identity else None
    else:
        token = request.cookies.get("mama_session", "")
        session = db.get(Session, digest(token)) if token else None
        user = (
            db.get(User, session.user_id)
            if session and session.expires_at > now()
            else None
        )
    if not user:
        raise HTTPException(401, "Войдите в аккаунт.")
    if user.blocked:
        raise HTTPException(403, "Доступ ограничен. Обратитесь в поддержку.")
    return user


def consent_user(user=Depends(current_user)):
    if not user.consent_at:
        raise HTTPException(403, "Сначала ознакомьтесь с условиями обработки данных.")
    return user


def admin_user(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Недостаточно прав.")
    return user


def internal_only(request: Request):
    if not hmac.compare_digest(
        request.headers.get("X-Bot-Secret", ""), settings().bot_internal_secret
    ):
        raise HTTPException(401, "Недостаточно прав.")


def verify_telegram(init_data):
    pairs = parse_qsl(init_data, keep_blank_values=True)
    if len(pairs) != len(dict(pairs)):
        raise HTTPException(401, "Некорректная авторизация Telegram.")
    data = dict(pairs)
    signature = data.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(
        b"WebAppData", settings().telegram_bot_token.encode(), hashlib.sha256
    ).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    try:
        age = time.time() - int(data.get("auth_date", "0"))
        identity = json.loads(data["user"])
    except (ValueError, KeyError):
        raise HTTPException(401, "Некорректная авторизация Telegram.")
    if (
        not settings().telegram_bot_token
        or not hmac.compare_digest(signature, expected)
        or not -30 <= age <= 300
        or not isinstance(identity.get("id"), int)
    ):
        raise HTTPException(
            401, "Ссылка Telegram устарела. Откройте приложение из бота ещё раз."
        )
    return identity
