"""Manual question-bank references; no extraction, generation or marking.

The user must compare the referenced pages and numbering with both originals.
Original uploads remain the authoritative source for wording, figures and schedules.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator


class VerifiedQuestion(BaseModel):
    topic_id: int = Field(gt=0)
    standard_number: int = Field(gt=0)
    year: int = Field(ge=1900, le=2100)
    question_number: str = Field(min_length=1, max_length=100, pattern=r"\S")
    paper_resource_id: UUID
    paper_page: int = Field(gt=0)
    schedule_resource_id: UUID
    schedule_page: int = Field(gt=0)
    verified_against_originals: bool

    @model_validator(mode="after")
    def require_verification(self):
        if not self.verified_against_originals:
            raise ValueError("Compare the question and schedule against the originals first")
        if self.paper_resource_id == self.schedule_resource_id:
            raise ValueError("Paper and schedule must be separate resources")
        return self


def create_exam_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS exam_questions (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        topic_id bigint NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
        standard_number integer NOT NULL REFERENCES standards(number) ON DELETE RESTRICT,
        year integer NOT NULL, question_number text NOT NULL,
        paper_resource_id uuid NOT NULL REFERENCES resources(id) ON DELETE RESTRICT,
        paper_page integer NOT NULL CHECK (paper_page > 0),
        schedule_resource_id uuid NOT NULL REFERENCES resources(id) ON DELETE RESTRICT,
        schedule_page integer NOT NULL CHECK (schedule_page > 0),
        verified_at timestamptz NOT NULL DEFAULT now(),
        CHECK (paper_resource_id <> schedule_resource_id)
    )""")


def exam_router(connect, authorised):
    router = APIRouter(dependencies=[Depends(authorised)])

    @router.post("/exam-questions", status_code=201)
    def add_question(body: VerifiedQuestion):
        with connect() as db:
            # Lock referenced rows so deletion cannot race the insert. Page counts and
            # document type cannot be inferred reliably from extracted text.
            linked = db.execute("SELECT 1 FROM topic_standards WHERE topic_id = %s AND standard_number = %s FOR KEY SHARE", (body.topic_id, body.standard_number)).fetchone()
            if not linked:
                raise HTTPException(404, "Topic and standard link not found")
            resources = db.execute("SELECT id FROM resources WHERE topic_id = %s AND status != 'deleting' AND id IN (%s, %s) ORDER BY id FOR KEY SHARE", (body.topic_id, body.paper_resource_id, body.schedule_resource_id)).fetchall()
            if len(resources) != 2:
                raise HTTPException(404, "Both resources must belong to the topic")
            row = db.execute("""INSERT INTO exam_questions
                (topic_id, standard_number, year, question_number, paper_resource_id,
                 paper_page, schedule_resource_id, schedule_page)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, verified_at""",
                (body.topic_id, body.standard_number, body.year, body.question_number.strip(),
                 body.paper_resource_id, body.paper_page, body.schedule_resource_id, body.schedule_page)).fetchone()
        return {"id": row[0], **body.model_dump(exclude={"verified_against_originals"}), "question_number": body.question_number.strip(), "verified_at": row[1]}

    @router.get("/exam-questions")
    def list_questions(topic_id: int = None):
        with connect() as db:
            rows = db.execute("""SELECT id, topic_id, standard_number, year, question_number,
                paper_resource_id, paper_page, schedule_resource_id, schedule_page, verified_at
                FROM exam_questions WHERE (%s::bigint IS NULL OR topic_id = %s)
                ORDER BY id""", (topic_id, topic_id)).fetchall()
        keys = ("id", "topic_id", "standard_number", "year", "question_number", "paper_resource_id", "paper_page", "schedule_resource_id", "schedule_page", "verified_at")
        return [dict(zip(keys, row)) for row in rows]

    return router
