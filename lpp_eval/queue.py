from huey import SqliteHuey
from .runner import process_submission

huey = SqliteHuey()


@huey.task()
def process_submission_task(project_id: str, report_type: str) -> None:
    process_submission(project_id, report_type)
