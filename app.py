from testcases import shorten_testcase
from score import program01score, program02score, program03score, program04score
import os
import atexit
import csv
import io
from flask import Flask, render_template, jsonify, request, Response
from dotenv import load_dotenv

load_dotenv()

from models import (
    db,
    Submission,
    TestCaseResult,
    Deadline,
    Student,
    calculate_submission_timing,
)
from scheduler import (
    init_scheduler,
    shutdown_scheduler,
    trigger_refresh,
)
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///submissions.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# Custom Jinja2 filter for JST datetime formatting
@app.template_filter("jst")
def jst_filter(dt, fmt="%Y-%m-%d %H:%M"):
    """Convert UTC datetime to JST and format it."""
    if dt is None:
        return "-"
    # Assume dt is naive UTC, convert to JST
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    jst_dt = dt.astimezone(JST)
    return jst_dt.strftime(fmt)


# Make calculate_submission_timing available in templates
@app.context_processor
def utility_processor():
    return {"calculate_timing": calculate_submission_timing}


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
    deadline = Deadline.get_deadline(submission.type_id)
    return render_template(
        "detail.html",
        submission=submission,
        test_results=test_results,
        deadline=deadline,
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


# Mapping of type_id to scoring function
SCORE_FUNCTIONS = {
    "program01": program01score,
    "program02": program02score,
    "program03": program03score,
    "program04": program04score,
}


@app.route("/grading/<type_id>")
def grading_table(type_id):
    """Display grading table for a specific type."""
    from grader import TEST_MAP

    if type_id not in TEST_MAP:
        return "Invalid type", 404

    # Get scoring function for this type
    score_func = SCORE_FUNCTIONS.get(type_id)

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
        results_dict = {shorten_testcase(tr.name): tr.outcome for tr in test_results}
        if (
            sub.project_id in submission_results
            and sub.passed < submission_results[sub.project_id]["submission"].passed
        ):
            # If multiple submissions exist for the same project_id,
            # keep the one with the highest passed count
            continue

        # Calculate score if scoring function exists
        score = None
        if score_func:
            # Convert results to bool dict for scoring function
            input_data = {tr.name: tr.outcome == "passed" for tr in test_results}
            score = score_func(input_data, sub)

        submission_results[sub.project_id] = {
            "submission": sub,
            "results": results_dict,
            "score": score,
        }
        all_testcases.update(results_dict.keys())

    # Sort test case names
    testcase_list = sorted(all_testcases)

    # Get all students from DB (including those without submissions)
    all_students = Student.get_all_students()  # {project_id: name}
    all_project_ids = Student.get_all_project_ids()

    # Merge with submitted project IDs (in case there are submissions without student records)
    project_ids_with_submissions = set(submission_results.keys())
    all_project_ids_set = set(all_project_ids) | project_ids_with_submissions
    project_ids = sorted(all_project_ids_set)

    # Get deadline for this type
    deadline = Deadline.get_deadline(type_id)

    return render_template(
        "grading_table.html",
        type_id=type_id,
        testcase_list=testcase_list,
        project_ids=project_ids,
        submission_results=submission_results,
        student_names=all_students,
        deadline=deadline,
    )


@app.route("/grading/all/csv")
def grading_all_csv():
    """Export grading data as CSV for all types combined."""
    from grader import TEST_MAP

    available_types = sorted(TEST_MAP.keys())

    # Get all students
    all_students = Student.get_all_students()
    all_project_ids = set(Student.get_all_project_ids())

    # Get deadlines for all types
    all_deadlines = Deadline.get_all_deadlines()

    # Timing labels
    timing_labels = {
        "on_time": "期限内",
        "resubmission": "再提出",
        "late": "遅延",
        "unknown": "不明",
    }

    # Build results for each type
    all_results = {}  # {type_id: {project_id: {submission, score}}}
    for type_id in available_types:
        score_func = SCORE_FUNCTIONS.get(type_id)
        submissions = (
            Submission.query.filter_by(type_id=type_id, status="completed")
            .order_by(Submission.project_id)
            .all()
        )

        submission_results = {}
        for sub in submissions:
            test_results = TestCaseResult.query.filter_by(submission_id=sub.id).all()
            if (
                sub.project_id in submission_results
                and sub.passed < submission_results[sub.project_id]["submission"].passed
            ):
                continue

            score = None
            if score_func:
                input_data = {tr.name: tr.outcome == "passed" for tr in test_results}
                score = score_func(input_data, sub)

            submission_results[sub.project_id] = {
                "submission": sub,
                "score": score,
            }
            all_project_ids.add(sub.project_id)

        all_results[type_id] = submission_results

    project_ids = sorted(all_project_ids)

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header: project_id, 氏名, then for each type: スコア, 提出状況
    header = ["project_id", "氏名"]
    for type_id in available_types:
        header.append(f"{type_id}_スコア")
        header.append(f"{type_id}_提出状況")
    writer.writerow(header)

    # Write data rows
    for project_id in project_ids:
        row = [project_id, all_students.get(project_id, "")]

        for type_id in available_types:
            deadline = all_deadlines.get(type_id)
            sub_results = all_results[type_id]

            if project_id in sub_results:
                sub_data = sub_results[project_id]
                score = sub_data["score"] if sub_data["score"] is not None else ""
                timing = calculate_submission_timing(sub_data["submission"], deadline)
                timing_label = timing_labels.get(timing, timing)
            else:
                score = ""
                timing_label = "未提出"

            row.append(score)
            row.append(timing_label)

        writer.writerow(row)

    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=all_grades.csv"},
    )


@app.route("/grading/<type_id>/csv")
def grading_csv(type_id):
    """Export grading data as CSV for a specific type (same content as grading_table)."""
    from grader import TEST_MAP

    if type_id not in TEST_MAP:
        return "Invalid type", 404

    # Get scoring function for this type
    score_func = SCORE_FUNCTIONS.get(type_id)

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
        results_dict = {shorten_testcase(tr.name): tr.outcome for tr in test_results}
        if (
            sub.project_id in submission_results
            and sub.passed < submission_results[sub.project_id]["submission"].passed
        ):
            # If multiple submissions exist for the same project_id,
            # keep the one with the highest passed count
            continue

        # Calculate score if scoring function exists
        score = None
        if score_func:
            input_data = {tr.name: tr.outcome == "passed" for tr in test_results}
            score = score_func(input_data, sub)

        submission_results[sub.project_id] = {
            "submission": sub,
            "results": results_dict,
            "score": score,
        }
        all_testcases.update(results_dict.keys())

    # Sort test case names
    testcase_list = sorted(all_testcases)

    # Get all students and deadline
    all_students = Student.get_all_students()
    all_project_ids = Student.get_all_project_ids()
    deadline = Deadline.get_deadline(type_id)

    # Merge project IDs
    project_ids_with_submissions = set(submission_results.keys())
    all_project_ids_set = set(all_project_ids) | project_ids_with_submissions
    project_ids = sorted(all_project_ids_set)

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header (same columns as grading_table.html)
    header = ["project_id", "氏名", "提出状況", "スコア", "Total"] + testcase_list
    writer.writerow(header)

    # Write data rows
    for project_id in project_ids:
        name = all_students.get(project_id, "")

        if project_id in submission_results:
            sub_data = submission_results[project_id]
            sub = sub_data["submission"]
            score = f"{sub_data['score']:.1f}" if sub_data["score"] is not None else "-"
            timing = calculate_submission_timing(sub, deadline)
            # Convert timing to Japanese labels
            timing_labels = {
                "on_time": "期限内",
                "resubmission": "再提出",
                "late": "期限後",
                "unknown": "-",
            }
            timing_label = timing_labels.get(timing, timing)
            total = f"{sub.passed}/{sub.total}"

            # Build test case results
            testcase_results = []
            for tc in testcase_list:
                outcome = sub_data["results"].get(tc)
                if outcome == "passed":
                    testcase_results.append("○")
                elif outcome == "failed":
                    testcase_results.append("×")
                else:
                    testcase_results.append("-")
        else:
            score = "-"
            timing_label = "未提出"
            total = "-"
            testcase_results = ["-"] * len(testcase_list)

        row = [project_id, name, timing_label, score, total] + testcase_results
        writer.writerow(row)

    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={type_id}_grades.csv"
        },
    )


@app.route("/deadlines")
def deadlines():
    """Display deadline management page."""
    from grader import TEST_MAP, SUBJECT_MAP

    # Get all type IDs (programs + reports)
    all_types = list(TEST_MAP.keys()) + [
        v for v in SUBJECT_MAP.values() if v.startswith("report")
    ]
    all_types = sorted(set(all_types))

    # Get current deadlines
    current_deadlines = Deadline.get_all_deadlines()

    return render_template(
        "deadlines.html",
        all_types=all_types,
        current_deadlines=current_deadlines,
    )


@app.route("/api/deadlines", methods=["GET"])
def api_get_deadlines():
    """Get all deadlines."""
    deadlines = Deadline.query.all()
    return jsonify(
        [
            {
                "type_id": d.type_id,
                "deadline": d.deadline.isoformat() if d.deadline else None,
            }
            for d in deadlines
        ]
    )


@app.route("/api/deadlines/<type_id>", methods=["PUT"])
def api_set_deadline(type_id):
    """Set or update a deadline for a type."""
    data = request.get_json()
    if not data or "deadline" not in data:
        return jsonify({"status": "error", "message": "deadline is required"}), 400

    try:
        deadline_str = data["deadline"]
        # Parse ISO format datetime
        deadline_dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        # Store as naive UTC
        if deadline_dt.tzinfo is not None:
            deadline_dt = deadline_dt.replace(tzinfo=None)

        # Upsert deadline
        existing = Deadline.query.filter_by(type_id=type_id).first()
        if existing:
            existing.deadline = deadline_dt
        else:
            new_deadline = Deadline(type_id=type_id, deadline=deadline_dt)
            db.session.add(new_deadline)

        db.session.commit()
        return jsonify(
            {
                "status": "success",
                "type_id": type_id,
                "deadline": deadline_dt.isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/deadlines/<type_id>", methods=["DELETE"])
def api_delete_deadline(type_id):
    """Delete a deadline for a type."""
    existing = Deadline.query.filter_by(type_id=type_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify(
            {"status": "success", "message": f"Deadline for {type_id} deleted"}
        )
    return jsonify({"status": "error", "message": "Deadline not found"}), 404


@app.route("/students")
def students():
    """Display student list page."""
    all_students = Student.query.order_by(Student.project_id).all()
    return render_template("students.html", students=all_students)


@app.route("/api/students", methods=["GET"])
def api_get_students():
    """Get all students."""
    students = Student.query.order_by(Student.project_id).all()
    return jsonify(
        [
            {
                "project_id": s.project_id,
                "name": s.name,
                "redmine_user_id": s.redmine_user_id,
            }
            for s in students
        ]
    )


@app.route("/api/students/sync", methods=["POST"])
def api_sync_students():
    """Sync students from Redmine."""
    from scheduler import trigger_sync_students

    try:
        trigger_sync_students()
        return jsonify({"status": "queued"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Queue a submission check job (non-blocking)."""
    try:
        trigger_refresh()
        return jsonify({"status": "queued"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/submission/<int:submission_id>/attachment", methods=["GET"])
def api_get_submission_attachment(submission_id):
    """Get the attachment file for a submission."""
    submission = Submission.query.get_or_404(submission_id)
    from grader import get_submission_path

    file_path = get_submission_path(submission.project_id, submission.type_id)
    if not file_path.exists():
        return jsonify({"status": "error", "message": "Attachment not found"}), 404

    # Send the file as an attachment
    from flask import send_file

    return send_file(str(file_path), download_name=file_path.name)


@app.route("/api/submission/<int:submission_id>/rerun", methods=["POST"])
def api_rerun_submission(submission_id):
    """Force re-run evaluation for a submission by setting status to pending."""
    submission = Submission.query.get_or_404(submission_id)

    # Delete existing test case results
    TestCaseResult.query.filter_by(submission_id=submission_id).delete()

    # Reset submission status to pending
    submission.status = "pending"
    submission.passed = 0
    submission.total = 0
    submission.failed = ""
    submission.stdout = ""
    submission.other_info = ""
    db.session.commit()

    # Trigger refresh to process immediately
    trigger_refresh()

    return jsonify({
        "status": "success",
        "message": f"Submission {submission_id} queued for re-evaluation",
        "submission_id": submission_id,
    })


if __name__ == "__main__":
    init_scheduler(app)
    atexit.register(shutdown_scheduler)

    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(debug=debug, port=port, use_reloader=False, host="0.0.0.0")
