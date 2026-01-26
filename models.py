from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Submission(db.Model):
    __tablename__ = "submissions"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(50), nullable=False)
    type_id = db.Column(db.String(50), nullable=False)
    testcase_id = db.Column(db.String(50), nullable=True)
    passed = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    failed = db.Column(db.Text, default="")
    other_info = db.Column(db.Text, default="")
    attachment_id = db.Column(db.String(100), nullable=False, unique=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")
    stdout = db.Column(db.Text, default="")

    test_case_results = db.relationship(
        "TestCaseResult", backref="submission", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Submission {self.project_id}/{self.type_id}>"


class TestCaseResult(db.Model):
    __tablename__ = "test_case_results"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer, db.ForeignKey("submissions.id"), nullable=False
    )
    name = db.Column(db.String(100), nullable=False)
    outcome = db.Column(db.String(20), nullable=False)
    test_output = db.Column(db.Text, default="")

    def __repr__(self):
        return f"<TestCaseResult {self.name}: {self.outcome}>"
