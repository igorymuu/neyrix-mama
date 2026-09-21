import math, re
from sqlalchemy import select, delete, text
from .models import KnowledgeDocument, KnowledgeChunk
from .config import settings


def chunks(content):
    sections = re.split(r"(?=^#{1,3} )", content, flags=re.M)
    for section in sections:
        title = section.split("\n")[0].lstrip("# ").strip()
        for start in range(0, len(section), 2200):
            piece = section[max(0, start - 180) : start + 2200].strip()
            if piece:
                yield (
                    piece,
                    {
                        "topic": title,
                        "jurisdiction": "RF",
                        "dynamic": any(
                            x in section.lower()
                            for x in ("dynamic", "лекарств", "вакцин")
                        ),
                        "source": "База знаний, предоставленная владельцем",
                        "source_date": "2026-09-18",
                        "risk_level": "reference",
                        "gestational_period": title if "недел" in title else "all",
                    },
                )


def index_document(db, document):
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
    for piece, metadata in chunks(document.content):
        db.add(KnowledgeChunk(document_id=document.id, text=piece, metadata_=metadata))
    document.metadata_ = {
        **document.metadata_,
        "status": "indexed",
        "retrieval": "lexical",
    }
    db.commit()
    if settings().embedding_model and settings().llm_api_key:
        from .llm import provider_request

        rows = list(
            db.scalars(
                select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
            )
        )
        for start in range(0, len(rows), 24):
            batch = rows[start : start + 24]
            result = provider_request(
                "embeddings",
                {"model": settings().embedding_model, "input": [x.text for x in batch]},
            )
            for item in result["data"]:
                batch[item["index"]].embedding = item["embedding"]
        document.metadata_ = {**document.metadata_, "retrieval": "hybrid"}
        db.commit()


def retrieve(db, query, top=6):
    rows = list(
        db.scalars(
            select(KnowledgeChunk)
            .join(KnowledgeDocument)
            .where(KnowledgeDocument.enabled.is_(True))
        )
    )
    terms = set(re.findall(r"[а-яёa-z0-9]{3,}", query.lower()))
    terms = {
        x[:6]
        for x in terms
        if x not in {"можно", "какие", "нужно", "меня", "этого", "мне"}
    }
    scores = {
        row.id: sum(min(row.text.lower().count(word), 8) for word in terms)
        / math.sqrt(max(1, len(row.text) / 500))
        for row in rows
    }
    if settings().embedding_model and any(row.embedding for row in rows):
        try:
            from .llm import provider_request

            vector = provider_request(
                "embeddings", {"model": settings().embedding_model, "input": [query]}
            )["data"][0]["embedding"]
            # pgvector query for production; no separate vector database or local model.
            if db.bind.dialect.name == "postgresql":
                ranked = db.execute(
                    text(
                        "SELECT id, 1 - (CAST(embedding::text AS vector) <=> CAST(:v AS vector)) AS similarity FROM knowledge_chunks WHERE embedding IS NOT NULL AND embedding::text <> 'null' ORDER BY CAST(embedding::text AS vector) <=> CAST(:v AS vector) LIMIT 20"
                    ),
                    {"v": str(vector)},
                ).all()
                for id_, similarity in ranked:
                    if id_ in scores:
                        scores[id_] += max(0, similarity) * 12
        except Exception:
            pass  # Explicit lexical fallback keeps retrieval available during embedding outage.
    ranked = sorted(rows, key=lambda x: scores[x.id], reverse=True)
    return [
        {"id": row.id, "text": row.text, **row.metadata_}
        for row in ranked[:top]
        if scores[row.id] > 0
    ]


def weekly_summary(db, profile):
    from .services import gestation

    g = gestation(profile)
    if not g or not 1 <= g["weeks"] <= 42:
        return None
    expected = f"{g['weeks']} неделя"
    for chunk in db.scalars(
        select(KnowledgeChunk)
        .join(KnowledgeDocument)
        .where(KnowledgeDocument.enabled.is_(True))
        .order_by(KnowledgeDocument.created_at.desc())
    ):
        if chunk.metadata_.get("topic") == expected:
            return chunk.text.split("\n", 1)[-1].strip()[:600]
    return None
