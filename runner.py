import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from models import db, Submission
from grader import check_all_issues, run_submission_tests, TEST_MAP


def create_app():
    """Create a minimal Flask app for DB access."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///submissions.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def check_redmine(app):
    """Check Redmine for updated issues and register pending submissions."""
    with app.app_context():
        try:
            registered = check_all_issues()
            if registered:
                print(f"Registered {len(registered)} new/updated submissions")
        except Exception as e:
            print(f"Error checking Redmine: {e}")


def run_pending_tests(app, max_workers):
    """Run tests for all pending submissions in parallel."""
    with app.app_context():
        pending = Submission.query.filter_by(status="pending").all()
        testable = [s for s in pending if s.type_id in TEST_MAP]

    if not testable:
        return

    print(f"Running tests for {len(testable)} submissions (max_workers={max_workers})")

    def _run_one(submission_id):
        with app.app_context():
            sub = Submission.query.get(submission_id)
            if sub is None:
                return
            try:
                run_submission_tests(sub)
            except Exception as e:
                print(f"Error running tests for submission {submission_id}: {e}")
                sub.status = "error"
                sub.other_info = str(e)
                db.session.commit()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_one, s.id): s.id for s in testable}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Unexpected error for submission {sid}: {e}")


def main():
    app = create_app()
    interval = int(os.getenv("RUNNER_INTERVAL_SECONDS", "300"))
    max_workers = int(os.getenv("MAX_PARALLEL_TESTS", "2"))

    with app.app_context():
        db.create_all()

    print(f"Runner started (interval={interval}s, max_workers={max_workers})")

    while True:
        print("--- Checking Redmine ---")
        check_redmine(app)
        print("--- Running pending tests ---")
        run_pending_tests(app, max_workers)
        print(f"--- Sleeping {interval}s ---")
        time.sleep(interval)


if __name__ == "__main__":
    main()
