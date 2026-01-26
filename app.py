import os
import atexit
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

load_dotenv()

from models import db, Submission, TestCaseResult
from scheduler import init_scheduler, shutdown_scheduler, trigger_refresh, get_job_status

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


@app.route("/grading")
def grading():
    """Display grading table selector."""
    # Get available types from grader
    from grader import TEST_MAP
    available_types = list(TEST_MAP.keys())
    return render_template("grading.html", available_types=available_types)


@app.route("/grading/<type_id>")
def grading_table(type_id):
    """Display grading table for a specific type."""
    from grader import TEST_MAP

    if type_id not in TEST_MAP:
        return "Invalid type", 404

    # Get all submissions for this type
    submissions = (
        Submission.query.filter_by(type_id=type_id, status="completed")
        .order_by(Submission.project_id)
        .all()
    )

    # Collect all unique test case names across all submissions
    all_testcases = set()
    submission_results = {}

    for sub in submissions:
        test_results = TestCaseResult.query.filter_by(submission_id=sub.id).all()
        results_dict = {tr.name: tr.outcome for tr in test_results}
        submission_results[sub.project_id] = {
            "submission": sub,
            "results": results_dict,
        }
        all_testcases.update(results_dict.keys())

    # Sort test case names
    testcase_list = sorted(all_testcases)

    # Get all project IDs (including those without submissions)
    project_ids = sorted(submission_results.keys())

    return render_template(
        "grading_table.html",
        type_id=type_id,
        testcase_list=testcase_list,
        project_ids=project_ids,
        submission_results=submission_results,
    )


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Queue a submission check job (non-blocking)."""
    try:
        job_id = trigger_refresh()
        return jsonify({"status": "queued", "job_id": job_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/refresh/<job_id>", methods=["GET"])
def api_refresh_status(job_id):
    """Check the status of a refresh job."""
    status = get_job_status(job_id)
    return jsonify(status)


if __name__ == "__main__":
    init_scheduler(app)
    atexit.register(shutdown_scheduler)

    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(debug=debug, port=port, use_reloader=False)
