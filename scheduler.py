import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Initialize the scheduler with the Flask app context."""
    interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "5"))

    def run_grader():
        with app.app_context():
            from grader import process_submissions

            print("Running scheduled submission check...")
            try:
                processed = process_submissions()
                print(f"Processed {len(processed)} submissions")
            except Exception as e:
                print(f"Scheduler error: {e}")

    scheduler.add_job(
        func=run_grader,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="submission_checker",
        name="Check and process new submissions",
        replace_existing=True,
    )

    scheduler.start()
    print(f"Scheduler started with {interval_minutes} minute interval")


def shutdown_scheduler():
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
