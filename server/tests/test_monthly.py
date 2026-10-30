import unittest
from contextlib import contextmanager

from fastapi import HTTPException

from exams import MonthlyExam, exam_router


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Database:
    def __init__(self):
        self.questions = {1: [1, 2, 3], 2: [4]}
        self.exams = []

    def execute(self, sql, params=()):
        if sql.startswith("LOCK TABLE"):
            return Result([])
        if "FROM subjects" in sql:
            return Result([(1,)] if params[0] in self.questions else [])
        if "FROM exam_questions q" in sql:
            used = {q: index for index, exam in enumerate(self.exams, 1) for q in exam}
            return Result([(q,) for q in sorted(self.questions[params[0]], key=lambda q: (used.get(q, 0), q))])
        if sql.startswith("INSERT INTO exams"):
            self.exams.append([])
            return Result([(len(self.exams), "now")])
        if sql.startswith("INSERT INTO exam_items"):
            self.exams[params[0] - 1].append(params[1])
            return Result([])
        raise AssertionError(sql)


class MonthlyExamTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()

        @contextmanager
        def connect():
            yield self.db

        router = exam_router(connect, lambda: None)
        self.create = next(route.endpoint for route in router.routes if route.path == "/exams/monthly")

    def test_selection_and_shortage(self):
        request = MonthlyExam(subject_id=1, question_count=2)
        self.assertEqual(self.create(request)["question_ids"], [1, 2])
        self.assertEqual(self.create(request)["question_ids"], [3, 1])
        self.assertEqual(self.create(MonthlyExam(subject_id=2, question_count=1))["question_ids"], [4])
        with self.assertRaises(HTTPException) as error:
            self.create(MonthlyExam(subject_id=1, question_count=4))
        self.assertEqual(error.exception.detail["available"], 3)
        self.assertEqual(len(self.db.exams), 3)
        with self.assertRaises(HTTPException) as error:
            self.create(MonthlyExam(subject_id=99, question_count=1))
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
