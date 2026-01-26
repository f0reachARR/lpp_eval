import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

scheduler = BackgroundScheduler()
_app = None


def init_scheduler(app):
    """Initialize the scheduler with the Flask app context."""
    global _app
    _app = app

    interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "5"))

    scheduler.add_job(
        func=_run_grader_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="submission_checker",
        name="Check and process new submissions",
        replace_existing=True,
    )

    scheduler.start()
    print(f"Scheduler started with {interval_minutes} minute interval")


def _run_grader_job():
    """Run the grader job with Flask app context."""
    if _app is None:
        print("Scheduler error: Flask app not initialized")
        return

    with _app.app_context():
        from grader import process_submissions

        print("Running submission check...")
        try:
            processed = process_submissions()
            print(f"Processed {len(processed)} submissions")
        except Exception as e:
            print(f"Scheduler error: {e}")

        # Add next job (in case interval changed)
        interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "5"))

        scheduler.add_job(
            func=_run_grader_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="submission_checker",
            name="Check and process new submissions",
            replace_existing=True,
        )


def trigger_refresh():
    """Trigger an immediate refresh job. Returns job ID."""

    scheduler.add_job(
        func=_run_grader_job,
        trigger=DateTrigger(run_date=datetime.now()),
        id="submission_checker",
        name="Check and process new submissions",
        replace_existing=True,
    )

    return


def get_job_status(job_id: str) -> dict:
    """Get the status of a job by ID."""
    job = scheduler.get_job(job_id)

    if job is None:
        # Job completed and was removed
        return {"status": "completed", "job_id": job_id}

    return {
        "status": "pending",
        "job_id": job_id,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
    }


def trigger_sync_students():
    """Trigger an immediate student sync job. Returns job ID."""
    job_id = f"manual_sync_students_{datetime.now().timestamp()}"

    scheduler.add_job(
        func=_run_sync_students_job,
        trigger=DateTrigger(run_date=datetime.now()),
        id=job_id,
        name="Manual sync students",
        replace_existing=False,
    )

    return job_id


def _run_sync_students_job():
    """Run the student sync job with Flask app context."""
    if _app is None:
        print("Scheduler error: Flask app not initialized")
        return

    with _app.app_context():
        from grader import sync_students

        print("Running student sync...")
        try:
            synced = sync_students()
            print(f"Synced {len(synced)} students")
        except Exception as e:
            print(f"Scheduler error: {e}")


def shutdown_scheduler():
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
