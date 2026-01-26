import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from redminelib import Redmine
from redminelib.resources import Issue

from eval import run_extract, run_tests
from models import Submission, TestCaseResult, db

load_dotenv()

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
LIMITED_CASES = os.getenv("LIMITED_CASES", "").split(",")

# Deadline configuration (UTC)
# Format: "type_id": datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
DEADLINE_MAP: Dict[str, datetime] = {
    "program01": datetime(2025, 5, 15, 15, 0, tzinfo=timezone.utc),  # Example: 2025-05-15 15:00 UTC
    "program02": datetime(2025, 6, 15, 15, 0, tzinfo=timezone.utc),
    "program03": datetime(2025, 7, 15, 15, 0, tzinfo=timezone.utc),
    "program04": datetime(2025, 8, 15, 15, 0, tzinfo=timezone.utc),
    "report01": datetime(2025, 5, 22, 15, 0, tzinfo=timezone.utc),
    "report02": datetime(2025, 6, 22, 15, 0, tzinfo=timezone.utc),
    "report03": datetime(2025, 7, 22, 15, 0, tzinfo=timezone.utc),
    "report04": datetime(2025, 8, 22, 15, 0, tzinfo=timezone.utc),
}

SUBJECT_MAP: Dict[str, str] = {
    "01.06 プログラムの提出": "program01",
    "01.07 レポートの提出": "report01",
    "02.06 プログラムの提出": "program02",
    "02.07 レポートの提出": "report02",
    "03.06 プログラムの提出": "program03",
    "03.07 レポートの提出": "report03",
    "04.06 プログラムの提出": "program04",
    "04.07 最終レポートの提出": "report04",
}

EXT_MAP = {
    "program01": ".bin",
    "report01": ".pdf",
    "program02": ".bin",
    "report02": ".pdf",
    "program03": ".bin",
    "report03": ".pdf",
    "program04": ".bin",
    "report04": ".pdf",
}

TEST_MAP: Dict[str, List[str]] = {
    "program01": ["01test", "01test_ex"],
    "program02": ["02test"],
    "program03": ["03test"],
    "program04": ["04test"],
}

REPORT_MAP: Dict[str, str] = {
    "program01": "report01",
    "program02": "report02",
    "program03": "report03",
    "program04": "report04",
}

PROJECT_REGEX = re.compile(r"言語処理プログラミング \((\d+)\)")


def get_redmine_client() -> Redmine:
    return Redmine(REDMINE_URL, key=REDMINE_API_KEY)


def get_attachment_info(
    redmine: Redmine, issue: Issue, report_type: str
) -> Optional[Tuple[str, datetime, datetime]]:
    """Get the latest attachment ID, its creation time, and first attachment time for an issue.

    Returns:
        Tuple of (latest_attachment_id, latest_created_on, first_created_on) or None
    """
    detailed_issue = redmine.issue.get(issue.id, include=["journals"])
    journals = sorted(detailed_issue.journals, key=lambda x: x.created_on)

    latest_attachment_id = None
    latest_created_on = None
    first_created_on = None

    for journal in journals:
        for detail in journal.details:
            is_valid = (
                detail["property"] == "attachment"
                and detail["new_value"] is not None
                and (
                    detail["new_value"].endswith(".zip")
                    if report_type in REPORT_MAP
                    else detail["new_value"].endswith(".pdf")
                )
            )
            if is_valid:
                latest_attachment_id = detail["name"]
                latest_created_on = journal.created_on
                if first_created_on is None:
                    first_created_on = journal.created_on

    if latest_attachment_id is None:
        return None

    return latest_attachment_id, latest_created_on, first_created_on


def calculate_submission_timing(
    type_id: str, submitted_at: datetime, first_submitted_at: datetime
) -> str:
    """Calculate submission timing classification.

    Returns:
        'on_time': 期限内提出
        'resubmission': 期限内提出後の再提出
        'late': 期限後の提出
        'unknown': 期限が設定されていない
    """
    deadline = DEADLINE_MAP.get(type_id)
    if deadline is None:
        return "unknown"

    # Make datetimes timezone-aware if they aren't
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=timezone.utc)
    if first_submitted_at.tzinfo is None:
        first_submitted_at = first_submitted_at.replace(tzinfo=timezone.utc)

    is_current_on_time = submitted_at <= deadline
    is_first_on_time = first_submitted_at <= deadline

    if is_current_on_time:
        return "on_time"
    elif is_first_on_time:
        return "resubmission"
    else:
        return "late"


def process_single_issue(redmine: Redmine, issue: Issue) -> Optional[Submission]:
    """Process a single issue and return a Submission object or None."""
    detailed_issue = redmine.issue.get(issue.id, include=["journals"])
    project_name = detailed_issue.project.name
    match = PROJECT_REGEX.match(project_name)

    if not match:
        print(f"Unknown project format: {project_name}")
        return None

    project_id = match.group(1)
    report_type = SUBJECT_MAP.get(detailed_issue.subject)

    if report_type is None:
        print(f"Unknown report type: {detailed_issue.subject}")
        return None

    attachment_info = get_attachment_info(redmine, issue, report_type)

    if attachment_info is None:
        print(f"No attachment found for {report_type} (project: {project_name})")
        return None

    attachment_id, submitted_at, first_submitted_at = attachment_info

    # Check if already processed
    existing = Submission.query.filter_by(attachment_id=attachment_id).first()
    if existing:
        print(f"Already processed: {project_id}/{report_type} ({attachment_id})")
        return None

    try:
        attachment = redmine.attachment.get(attachment_id)
    except Exception as e:
        print(f"Failed to get attachment: {e}")
        return None

    print(f"Processing: {project_id} {report_type} {attachment.filename}")

    # Calculate submission timing
    submission_timing = calculate_submission_timing(
        report_type, submitted_at, first_submitted_at
    )

    # Create submission record
    submission = Submission(
        project_id=project_id,
        type_id=report_type,
        attachment_id=attachment_id,
        submitted_at=submitted_at,
        first_submitted_at=first_submitted_at,
        submission_timing=submission_timing,
        status="running",
    )
    db.session.add(submission)
    db.session.commit()

    # Download attachment
    file_dir = OUTPUT_DIR / project_id / report_type
    shutil.rmtree(file_dir, ignore_errors=True)
    file_dir.mkdir(parents=True, exist_ok=True)
    file_dir = file_dir.resolve()
    ext = EXT_MAP[report_type]
    attachment.download(savepath=str(file_dir), filename=f"submission{ext}")

    # If not a program submission, mark as completed
    if report_type not in TEST_MAP:
        submission.status = "completed"
        submission.evaluated_at = datetime.utcnow()
        db.session.commit()
        return submission

    # Run tests
    try:
        root = run_extract(file_dir)
    except Exception as e:
        print(f"Failed to extract source code: {e}")
        submission.status = "error"
        submission.other_info = f"Extraction failed: {e}"
        submission.evaluated_at = datetime.utcnow()
        db.session.commit()
        return submission

    test_results_dir = root / "test_results"
    shutil.rmtree(test_results_dir, ignore_errors=True)

    test_names = TEST_MAP[report_type]
    best_result = (None, "", 0, [])
    all_result_info: List[str] = []

    for test_name in test_names:
        try:
            result = run_tests(root, test_name, include_cases=LIMITED_CASES)
            passed_count = len([r for r in result.summary if r[1] == "passed"])
            print(f"{test_name}: {passed_count}/{len(result.summary)}")
            all_result_info.append(
                f"{test_name} ({passed_count}/{len(result.summary)})"
            )

            if passed_count >= best_result[2]:
                best_result = (result, test_name, passed_count, result.summary)
        except Exception as e:
            print(f"Test {test_name} failed: {e}")
            all_result_info.append(f"{test_name} (error)")

    if best_result[0] is None:
        submission.status = "error"
        submission.other_info = "All tests failed"
        submission.evaluated_at = datetime.utcnow()
        db.session.commit()
        return submission

    # Update submission with best results
    submission.testcase_id = best_result[1]
    submission.passed = best_result[2]
    submission.total = len(best_result[3])
    submission.failed = ",".join([s for s, r in best_result[3] if r == "failed"])
    submission.other_info = " | ".join(all_result_info)
    submission.stdout = best_result[0].stdout if best_result[0] else ""
    submission.status = "completed"
    submission.evaluated_at = datetime.utcnow()

    # Save individual test case results
    for case_name, outcome in best_result[3]:
        test_result = TestCaseResult(
            submission_id=submission.id,
            name=case_name,
            outcome=outcome,
            test_output="",
        )
        db.session.add(test_result)

    db.session.commit()
    print(
        f"Completed: {project_id}/{report_type} - {best_result[2]}/{len(best_result[3])}"
    )

    return submission


def process_submissions() -> List[Submission]:
    """Process all pending submissions from Redmine."""
    redmine = get_redmine_client()
    issues: List[Issue] = redmine.issue.filter(tracker_id=15, status_id="*")
    processed: List[Submission] = []

    for issue in issues:
        try:
            submission = process_single_issue(redmine, issue)
            if submission:
                processed.append(submission)
        except Exception as e:
            print(f"Error processing issue {issue.id}: {e}")
            continue

    return processed
