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
        self.questions = {
            1: [(1, "91171", 5), (2, "91171", 5), (3, "91170", 5), (4, "91173", 5)],
            2: [(5, "91164", 5)],
        }
        self.exams = []

    def execute(self, sql, params=()):
        if sql.startswith("LOCK TABLE"):
            return Result([])
        if "FROM subjects" in sql:
            return Result([(1,)] if params[0] in self.questions else [])
        if "FROM exam_questions q" in sql:
            used = {q: index for index, exam in enumerate(self.exams, 1) for q in exam}
            rows = [(q, standard, marks, used.get(q, 0))
                    for q, standard, marks in self.questions[params[0]]]
            rows.sort(key=lambda row: (row[3], row[0]))
            return Result(rows)
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

    def test_selection_covers_standards_and_avoids_repeats(self):
        first = self.create(MonthlyExam(subject_id=1, question_count=2))
        self.assertEqual(len(first["question_ids"]), 2)
        self.assertEqual(len(first["standards"]), 2)
        self.assertEqual(first["total_marks"], 10)

        second = self.create(MonthlyExam(subject_id=1, question_count=2))
        self.assertEqual(len(second["question_ids"]), 2)
        self.assertFalse(set(first["question_ids"]) & set(second["question_ids"]))

        single = self.create(MonthlyExam(subject_id=2, question_count=1))
        self.assertEqual(single["question_ids"], [5])

        with self.assertRaises(HTTPException) as error:
            self.create(MonthlyExam(subject_id=1, question_count=5))
        self.assertEqual(error.exception.detail["available"], 4)

        with self.assertRaises(HTTPException) as error:
            self.create(MonthlyExam(subject_id=99, question_count=1))
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
