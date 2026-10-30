from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


class ReviewQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=5000, pattern=r"\S")
    due_date: date


class ReviewAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=50000, pattern=r"\S")
    confidence: int = Field(ge=1, le=5)


def create_review_tables(db):
    db.execute("CREATE TABLE IF NOT EXISTS review_questions (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, topic_id bigint NOT NULL REFERENCES topics(id) ON DELETE RESTRICT, question text NOT NULL, due_date date NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS review_answers (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, question_id bigint NOT NULL REFERENCES review_questions(id) ON DELETE RESTRICT, answer text NOT NULL, confidence integer NOT NULL CHECK (confidence BETWEEN 1 AND 5), answered_at timestamptz NOT NULL DEFAULT now())")


def review_router(connect, authorised):
    router = APIRouter(dependencies=[Depends(authorised)])

    @router.post("/topics/{topic_id}/review-questions", status_code=201)
    def create_question(topic_id: int, body: ReviewQuestion):
        with connect() as db:
            row = db.execute("INSERT INTO review_questions (topic_id, question, due_date) SELECT id, %s, %s FROM topics WHERE id = %s RETURNING id", (body.question.strip(), body.due_date, topic_id)).fetchone()
            if row is None:
                raise HTTPException(404, "Topic not found")
        return {"id": row[0], "topic_id": topic_id, "question": body.question.strip(), "due_date": body.due_date}

    @router.get("/review-questions/due")
    def due_questions(as_of: date):
        # ponytail: caller supplies the local date; add a user timezone when accounts exist.
        with connect() as db:
            rows = db.execute("SELECT id, topic_id, question, due_date FROM review_questions WHERE due_date <= %s AND NOT EXISTS (SELECT 1 FROM review_answers WHERE question_id = review_questions.id) ORDER BY due_date, id", (as_of,)).fetchall()
        return [{"id": row[0], "topic_id": row[1], "question": row[2], "due_date": row[3]} for row in rows]

    @router.post("/review-questions/{question_id}/answers", status_code=201)
    def answer_question(question_id: int, body: ReviewAnswer):
        with connect() as db:
            row = db.execute("INSERT INTO review_answers (question_id, answer, confidence) SELECT id, %s, %s FROM review_questions WHERE id = %s RETURNING id, answered_at", (body.answer.strip(), body.confidence, question_id)).fetchone()
            if row is None:
                raise HTTPException(404, "Review question not found")
        return {"id": row[0], "question_id": question_id, "answer": body.answer.strip(), "confidence": body.confidence, "answered_at": row[1]}

    @router.get("/review-questions/{question_id}/answers")
    def question_answers(question_id: int):
        with connect() as db:
            if not db.execute("SELECT 1 FROM review_questions WHERE id = %s", (question_id,)).fetchone():
                raise HTTPException(404, "Review question not found")
            rows = db.execute("SELECT id, answer, confidence, answered_at FROM review_answers WHERE question_id = %s ORDER BY id", (question_id,)).fetchall()
        return [{"id": row[0], "answer": row[1], "confidence": row[2], "answered_at": row[3]} for row in rows]

    return router
