"""Development-only fixture for browser tests. No production login bypass."""
import json,secrets,sys
from datetime import timedelta
from app.config import settings
from app.db import SessionLocal
from app.models import User,Subscription,Session,MedicalDocument,now
from sqlalchemy import select
from app import storage
from app.security import digest
if settings().production or not settings().database_url.startswith('sqlite:'):
    raise SystemExit('Browser fixtures require a disposable SQLite database.')
with SessionLocal() as db:
    if len(sys.argv)>1:
        user=db.get(User,sys.argv[1])
        if user and user.profile.get('name')=='Проверка интерфейса':
            for doc in db.scalars(select(MedicalDocument).where(MedicalDocument.user_id==user.id)):storage.delete(doc.storage_key)
            db.delete(user);db.commit()
    else:
        user=User(profile={'name':'Проверка интерфейса','lmp':'2026-05-11'},consent_at=now(),consent_version='test')
        db.add(user);db.flush()
        token=secrets.token_urlsafe(32)
        db.add(Subscription(user_id=user.id,ends_at=now()+timedelta(days=30)))
        db.add(Session(user_id=user.id,token_hash=digest(token),expires_at=now()+timedelta(hours=1)))
        db.commit()
        print(json.dumps({'id':user.id,'token':token}))
