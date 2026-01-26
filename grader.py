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
from models import Submission, TestCaseResult, Student, db

load_dotenv()

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
LIMITED_CASES = os.getenv("LIMITED_CASES", "").split(",")

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
STUDENT_ROLE_NAME = os.getenv("STUDENT_ROLE_NAME", "学生")


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
    if existing and existing.status == "completed":
        print(f"Already processed: {project_id}/{report_type} ({attachment_id})")
        return None

    try:
        attachment = redmine.attachment.get(attachment_id)
    except Exception as e:
        print(f"Failed to get attachment: {e}")
        return None

    print(f"Processing: {project_id} {report_type} {attachment.filename}")

    # Create submission record (submission_timing is calculated at display time)
    submission = (
        Submission(
            project_id=project_id,
            type_id=report_type,
            attachment_id=attachment_id,
            submitted_at=submitted_at,
            first_submitted_at=first_submitted_at,
            status="running",
        )
        if existing is None
        else existing
    )
    submission.status = "running"
    if existing is None:
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


def sync_students() -> List[Student]:
    """Sync students from Redmine projects.

    Fetches all projects matching the pattern and extracts student users.
    """
    redmine = get_redmine_client()
    synced: List[Student] = []

    # Get all projects
    try:
        projects = redmine.project.all()
    except Exception as e:
        print(f"Failed to fetch projects: {e}")
        return synced

    for project in projects:
        match = PROJECT_REGEX.match(project.name)
        if not match:
            continue

        project_id = match.group(1)

        # Check if student already exists
        existing = Student.get_by_project_id(project_id)
        if existing:
            continue

        # Get project memberships
        try:
            memberships = redmine.project_membership.filter(project_id=project.id)
        except Exception as e:
            print(f"Failed to fetch memberships for {project.name}: {e}")
            continue

        # Find student role member
        student_name = None
        student_user_id = None

        for membership in memberships:
            # Check if this member has the student role
            roles = getattr(membership, "roles", [])
            for role in roles:
                if role.name == STUDENT_ROLE_NAME:
                    user = getattr(membership, "user", None)
                    if user:
                        student_name = user.name
                        student_user_id = user.id
                        break
            if student_name:
                break

        if student_name:
            student = Student(
                project_id=project_id,
                name=student_name,
                redmine_user_id=student_user_id,
            )
            db.session.add(student)
            db.session.commit()
            synced.append(student)
            print(f"Synced student: {project_id} - {student_name}")

    return synced


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


def get_submission_path(project_id: str, type_id: str) -> Path:
    """Get the file path for a submission."""
    ext = EXT_MAP.get(type_id, "")
    return OUTPUT_DIR / project_id / type_id / f"submission{ext}"
