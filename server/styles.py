from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


class StyleProfile(BaseModel):
    content: str = Field(max_length=50000)


def create_style_tables(db):
    db.execute("CREATE TABLE IF NOT EXISTS style_profiles (subject_id bigint PRIMARY KEY REFERENCES subjects(id) ON DELETE CASCADE, content text NOT NULL)")


def style_router(connect, authorised):
    router = APIRouter(dependencies=[Depends(authorised)])

    @router.get("/subjects/{subject_id}/style-profile")
    def get_profile(subject_id: int):
        with connect() as db:
            row = db.execute("SELECT COALESCE(p.content, '') FROM subjects s LEFT JOIN style_profiles p ON p.subject_id = s.id WHERE s.id = %s", (subject_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Subject not found")
        return {"subject_id": subject_id, "content": row[0]}

    @router.put("/subjects/{subject_id}/style-profile")
    def put_profile(subject_id: int, body: StyleProfile):
        with connect() as db:
            row = db.execute("INSERT INTO style_profiles (subject_id, content) SELECT id, %s FROM subjects WHERE id = %s ON CONFLICT (subject_id) DO UPDATE SET content = EXCLUDED.content RETURNING content", (body.content, subject_id)).fetchone()
            if row is None:
                raise HTTPException(404, "Subject not found")
        return {"subject_id": subject_id, "content": row[0]}

    return router
