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
    # Submission timing classification
    # on_time: 期限内提出
    # resubmission: 期限内提出後の再提出
    # late: 期限後の提出
    # submission_timing = db.Column(db.String(20), default="unknown")
    # First submission timestamp for this project/type (to detect resubmission)
    first_submitted_at = db.Column(db.DateTime, nullable=True)

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


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    redmine_user_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Student {self.project_id}: {self.name}>"

    @staticmethod
    def get_by_project_id(project_id: str):
        """Get student by project_id."""
        return Student.query.filter_by(project_id=project_id).first()

    @staticmethod
    def get_all_students() -> dict:
        """Get all students as a dictionary {project_id: name}."""
        students = Student.query.all()
        return {s.project_id: s.name for s in students}

    @staticmethod
    def get_all_project_ids() -> list:
        """Get all project IDs."""
        students = Student.query.order_by(Student.project_id).all()
        return [s.project_id for s in students]


class Deadline(db.Model):
    __tablename__ = "deadlines"

    id = db.Column(db.Integer, primary_key=True)
    type_id = db.Column(db.String(50), nullable=False, unique=True)
    deadline = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Deadline {self.type_id}: {self.deadline}>"

    @staticmethod
    def get_deadline(type_id: str):
        """Get deadline for a type_id."""
        deadline = Deadline.query.filter_by(type_id=type_id).first()
        return deadline.deadline if deadline else None

    @staticmethod
    def get_all_deadlines() -> dict:
        """Get all deadlines as a dictionary."""
        deadlines = Deadline.query.all()
        return {d.type_id: d.deadline for d in deadlines}


def calculate_submission_timing(submission, deadline: datetime = None) -> str:
    """Calculate submission timing at display time.

    Args:
        submission: Submission object with submitted_at and first_submitted_at
        deadline: Optional deadline datetime. If None, fetched from DB.

    Returns:
        'on_time': 期限内提出
        'resubmission': 期限内提出後の再提出
        'late': 期限後の提出
        'unknown': 期限が設定されていない
    """
    if deadline is None:
        deadline = Deadline.get_deadline(submission.type_id)

    if deadline is None:
        return "unknown"

    submitted_at = submission.submitted_at
    first_submitted_at = submission.first_submitted_at

    if submitted_at is None:
        return "unknown"

    # Use submitted_at as first if first_submitted_at is not set
    if first_submitted_at is None:
        first_submitted_at = submitted_at

    # Make timezone-naive for comparison (assume all times are UTC)
    if hasattr(deadline, "tzinfo") and deadline.tzinfo is not None:
        deadline = deadline.replace(tzinfo=None)
    if hasattr(submitted_at, "tzinfo") and submitted_at.tzinfo is not None:
        submitted_at = submitted_at.replace(tzinfo=None)
    if hasattr(first_submitted_at, "tzinfo") and first_submitted_at.tzinfo is not None:
        first_submitted_at = first_submitted_at.replace(tzinfo=None)

    is_current_on_time = submitted_at <= deadline
    is_first_on_time = first_submitted_at <= deadline

    if is_current_on_time:
        return "on_time"
    elif is_first_on_time:
        return "resubmission"
    else:
        return "late"
