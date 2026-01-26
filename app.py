import os
import atexit
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

load_dotenv()

from models import db, Submission, TestCaseResult
from scheduler import init_scheduler, shutdown_scheduler

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///submissions.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()


@app.route("/")
def index():
    """Display all submissions in a table."""
    submissions = Submission.query.order_by(Submission.submitted_at.desc()).all()
    return render_template("index.html", submissions=submissions)


@app.route("/submission/<int:submission_id>")
def detail(submission_id):
    """Display detailed information for a single submission."""
    submission = Submission.query.get_or_404(submission_id)
    test_results = TestCaseResult.query.filter_by(submission_id=submission_id).all()
    return render_template(
        "detail.html", submission=submission, test_results=test_results
    )


@app.route("/api/submissions")
def api_submissions():
    """JSON API to get all submissions."""
    submissions = Submission.query.order_by(Submission.submitted_at.desc()).all()
    return jsonify(
        [
            {
                "id": s.id,
                "project_id": s.project_id,
                "type_id": s.type_id,
                "testcase_id": s.testcase_id,
                "passed": s.passed,
                "total": s.total,
                "failed": s.failed,
                "status": s.status,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "evaluated_at": s.evaluated_at.isoformat() if s.evaluated_at else None,
            }
            for s in submissions
        ]
    )


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Manually trigger submission check."""
    from grader import process_submissions

    try:
        processed = process_submissions()
        return jsonify(
            {"status": "success", "processed": len(processed)}
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    init_scheduler(app)
    atexit.register(shutdown_scheduler)

    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(debug=debug, port=port, use_reloader=False)
