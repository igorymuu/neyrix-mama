from pathlib import Path
from sqlalchemy import select
from .db import SessionLocal
from .models import AgentConfiguration, KnowledgeDocument
from .security import config
from .knowledge import index_document
from .config import settings


def seed():
    root = Path(__file__).parent.parent / "knowledge"
    with SessionLocal() as db:
        if not db.get(AgentConfiguration, 1):
            db.add(
                AgentConfiguration(
                    id=1,
                    data={
                        **config(db),
                        "system_prompt": (root / "system_prompt.txt").read_text(),
                        "model": settings().llm_model,
                        "fallback_model": "",
                        "vision_model": settings().vision_model,
                    },
                )
            )
            db.commit()
        if not db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.name == "pregnancy_rf_v2.md"
            )
        ):
            doc = KnowledgeDocument(
                name="pregnancy_rf_v2.md",
                content=(root / "pregnancy_rf_v2.md").read_text(),
                metadata_={"version": "2.0", "status": "queued"},
            )
            db.add(doc)
            db.commit()
            index_document(db, doc)
    # Demo profiles live only in frontend/lib.ts. No fake users enter the database.


if __name__ == "__main__":
    seed()
