"""Manual question-bank references; no extraction, generation or marking.

The user must compare the referenced pages and numbering with both originals.
Original uploads remain the authoritative source for wording, figures and schedules.
"""
from uuid import UUID

import json

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
    marks: int = Field(default=0, ge=0, le=100)
    parts: list[dict] = Field(default_factory=list, max_length=30)
    question_text: str = Field(default="", max_length=50000)
    schedule_text: str = Field(default="", max_length=100000)
    figure_pages: list[int] = Field(default_factory=list, max_length=30)
    verified_against_originals: bool

    @model_validator(mode="after")
    def require_verification(self):
        if not self.verified_against_originals:
            raise ValueError("Compare the question and schedule against the originals first")
        if self.paper_resource_id == self.schedule_resource_id:
            raise ValueError("Paper and schedule must be separate resources")
        return self


class ExamAssembly(BaseModel):
    question_ids: list[int] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_questions(self):
        if any(question_id <= 0 for question_id in self.question_ids) or len(set(self.question_ids)) != len(self.question_ids):
            raise ValueError("Question IDs must be positive and unique")
        return self


class MonthlyExam(BaseModel):
    subject_id: int = Field(gt=0)
    question_count: int = Field(gt=0, le=100)


class ExamAnswer(BaseModel):
    answer: str = Field(max_length=100000)


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
        marks integer NOT NULL DEFAULT 0,
        parts jsonb NOT NULL DEFAULT '[]'::jsonb,
        question_text text NOT NULL DEFAULT '',
        schedule_text text NOT NULL DEFAULT '',
        figure_pages jsonb NOT NULL DEFAULT '[]'::jsonb,
        source text NOT NULL DEFAULT 'manual',
        verified_at timestamptz NOT NULL DEFAULT now(),
        CHECK (paper_resource_id <> schedule_resource_id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS exams (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        subject_id bigint REFERENCES subjects(id) ON DELETE SET NULL,
        kind text NOT NULL DEFAULT 'manual',
        total_marks integer NOT NULL DEFAULT 0,
        created_at timestamptz NOT NULL DEFAULT now()
    )""")
    db.execute("ALTER TABLE exams ADD COLUMN IF NOT EXISTS subject_id bigint REFERENCES subjects(id) ON DELETE SET NULL")
    db.execute("ALTER TABLE exams ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'manual'")
    db.execute("ALTER TABLE exams ADD COLUMN IF NOT EXISTS total_marks integer NOT NULL DEFAULT 0")
    db.execute("""CREATE TABLE IF NOT EXISTS exam_items (
        exam_id bigint NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
        question_id bigint NOT NULL REFERENCES exam_questions(id) ON DELETE RESTRICT,
        position integer NOT NULL CHECK (position > 0),
        answer text,
        PRIMARY KEY (exam_id, question_id), UNIQUE (exam_id, position)
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
                 paper_page, schedule_resource_id, schedule_page, marks, parts,
                 question_text, schedule_text, figure_pages, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, 'manual')
                RETURNING id, verified_at""",
                (body.topic_id, body.standard_number, body.year, body.question_number.strip(),
                 body.paper_resource_id, body.paper_page, body.schedule_resource_id, body.schedule_page,
                 body.marks, json.dumps(body.parts), body.question_text, body.schedule_text,
                 json.dumps(body.figure_pages))).fetchone()
        return {"id": row[0], **body.model_dump(exclude={"verified_against_originals"}), "question_number": body.question_number.strip(), "verified_at": row[1]}

    @router.get("/exam-questions")
    def list_questions(topic_id: int = None):
        with connect() as db:
            rows = db.execute("""SELECT id, topic_id, standard_number, year, question_number,
                paper_resource_id, paper_page, schedule_resource_id, schedule_page, verified_at,
                marks, parts, question_text, schedule_text, figure_pages, source
                FROM exam_questions WHERE (%s::bigint IS NULL OR topic_id = %s)
                ORDER BY id""", (topic_id, topic_id)).fetchall()
        keys = ("id", "topic_id", "standard_number", "year", "question_number", "paper_resource_id", "paper_page", "schedule_resource_id", "schedule_page", "verified_at", "marks", "parts", "question_text", "schedule_text", "figure_pages", "source")
        return [dict(zip(keys, row)) for row in rows]

    @router.get("/exams")
    def list_exams():
        with connect() as db:
            rows = db.execute("""SELECT e.id, e.created_at, COUNT(i.question_id), e.subject_id, e.kind, e.total_marks
                FROM exams e LEFT JOIN exam_items i ON i.exam_id = e.id
                GROUP BY e.id ORDER BY e.id""").fetchall()
        return [dict(zip(("id", "created_at", "question_count", "subject_id", "kind", "total_marks"), row)) for row in rows]

    @router.post("/exams", status_code=201)
    def assemble_exam(body: ExamAssembly):
        with connect() as db:
            db.execute("LOCK TABLE exam_items IN SHARE ROW EXCLUSIVE MODE")
            rows = db.execute("SELECT id, marks FROM exam_questions WHERE id = ANY(%s) ORDER BY id FOR KEY SHARE", (body.question_ids,)).fetchall()
            if len(rows) != len(body.question_ids):
                raise HTTPException(404, "One or more verified questions not found")
            total_marks = sum(row[1] for row in rows)
            exam = db.execute("INSERT INTO exams (kind, total_marks) VALUES ('manual', %s) RETURNING id, created_at", (total_marks,)).fetchone()
            for position, question_id in enumerate(body.question_ids, 1):
                db.execute("INSERT INTO exam_items (exam_id, question_id, position) VALUES (%s, %s, %s)", (exam[0], question_id, position))
        return {"id": exam[0], "created_at": exam[1], "question_ids": body.question_ids, "total_marks": total_marks}

    @router.post("/exams/monthly", status_code=201)
    def assemble_monthly_exam(body: MonthlyExam):
        with connect() as db:
            # Serialise selection with all exam assembly, including manual exams.
            db.execute("LOCK TABLE exam_items IN SHARE ROW EXCLUSIVE MODE")
            if not db.execute("SELECT 1 FROM subjects WHERE id = %s FOR KEY SHARE", (body.subject_id,)).fetchone():
                raise HTTPException(404, "Subject not found")
            rows = db.execute("""SELECT q.id, q.standard_number, q.marks,
                COALESCE(MAX(i.exam_id), 0) AS last_used
                FROM exam_questions q
                JOIN topics t ON t.id = q.topic_id
                LEFT JOIN exam_items i ON i.question_id = q.id
                WHERE t.subject_id = %s AND q.verified_at IS NOT NULL
                GROUP BY q.id
                ORDER BY last_used ASC, q.id
                FOR KEY SHARE OF q""", (body.subject_id,)).fetchall()
            if len(rows) < body.question_count:
                raise HTTPException(409, detail={"message": "Insufficient verified questions", "requested": body.question_count, "available": len(rows)})
            groups = {}
            for question_id, standard, marks, last_used in rows:
                groups.setdefault(standard, []).append((question_id, marks, last_used))
            # Round-robin across standards so a monthly paper covers every standard
            # that has a verified question, while preferring least-used questions.
            standards = sorted(groups, key=lambda standard: (min(item[2] for item in groups[standard]), standard))
            selected = []
            cursor = {standard: 0 for standard in standards}
            while len(selected) < body.question_count:
                progressed = False
                for standard in standards:
                    if len(selected) >= body.question_count:
                        break
                    index = cursor[standard]
                    if index < len(groups[standard]):
                        selected.append((*groups[standard][index], standard))
                        cursor[standard] += 1
                        progressed = True
                if not progressed:
                    break
            question_ids = [item[0] for item in selected]
            total_marks = sum(item[1] for item in selected)
            exam = db.execute("INSERT INTO exams (subject_id, kind, total_marks) VALUES (%s, 'monthly', %s) RETURNING id, created_at", (body.subject_id, total_marks)).fetchone()
            for position, question_id in enumerate(question_ids, 1):
                db.execute("INSERT INTO exam_items (exam_id, question_id, position) VALUES (%s, %s, %s)", (exam[0], question_id, position))
        return {"id": exam[0], "created_at": exam[1], "subject_id": body.subject_id,
                "question_ids": question_ids, "total_marks": total_marks,
                "standards": sorted({item[3] for item in selected})}

    @router.put("/exams/{exam_id}/answers/{question_id}")
    def answer_question(exam_id: int, question_id: int, body: ExamAnswer):
        with connect() as db:
            row = db.execute("UPDATE exam_items SET answer = %s WHERE exam_id = %s AND question_id = %s RETURNING question_id", (body.answer, exam_id, question_id)).fetchone()
            if not row:
                raise HTTPException(404, "Exam question not found")
        return {"exam_id": exam_id, "question_id": question_id, "answer": body.answer}

    @router.get("/exams/{exam_id}")
    def view_exam(exam_id: int):
        with connect() as db:
            exam = db.execute("SELECT id, created_at, subject_id, kind, total_marks FROM exams WHERE id = %s", (exam_id,)).fetchone()
            if not exam:
                raise HTTPException(404, "Exam not found")
            rows = db.execute("""SELECT q.id, q.topic_id, q.standard_number, q.year, q.question_number,
                q.paper_resource_id, q.paper_page, q.schedule_resource_id, q.schedule_page,
                q.verified_at, i.position, i.answer, q.marks, q.parts, q.question_text,
                q.schedule_text, q.figure_pages
                FROM exam_items i JOIN exam_questions q ON q.id = i.question_id
                WHERE i.exam_id = %s ORDER BY i.position""", (exam_id,)).fetchall()
        keys = ("id", "topic_id", "standard_number", "year", "question_number", "paper_resource_id", "paper_page", "schedule_resource_id", "schedule_page", "verified_at", "position", "answer", "marks", "parts", "question_text", "schedule_text", "figure_pages")
        return {"id": exam[0], "created_at": exam[1], "subject_id": exam[2], "kind": exam[3],
                "total_marks": exam[4], "questions": [dict(zip(keys, row)) for row in rows]}

    return router
