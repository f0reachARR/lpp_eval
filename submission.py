from dotenv import load_dotenv

load_dotenv()

import os
from pathlib import Path
import re
import shutil
from typing import Dict, List
from redminelib import Redmine
from redminelib.resources import Issue
from eval import run_extract, run_tests


REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))

redmine = Redmine(REDMINE_URL, key=REDMINE_API_KEY)

# 1: 新規, 2: 進行中, 3: 審査合格, 4: 審査待ち, 5: 終了, 6: 却下, 13: 受理, 16: 解決済み, 15: 一次確認, 14: 差し戻し
# トラッカーID 15: 提出

SUBJECT_MAP: Dict[str, str] = {
    "01.06 プログラムの提出": "program01",
    "01.07 レポートの提出": "report01",
}
TEST_MAP: Dict[str, List[str]] = {
    "program01": ["01test", "01test_ex"],
}
PROJECT_REGEX = re.compile(r"言語処理プログラミング \((\d+)\)")

if __name__ == "__main__":
    issues: List[Issue] = redmine.issue.filter(status_id=4, tracker_id=15)
    for issue in issues:
        detailed_issue: Issue = redmine.issue.get(issue.id, include=["journals"])
        project_name: str = detailed_issue.project.name
        project_id = PROJECT_REGEX.match(project_name).group(1)

        report_type = SUBJECT_MAP.get(detailed_issue.subject)

        if report_type is None:
            print(
                f"Unknown report type: {detailed_issue.subject} (project: {detailed_issue.project.name})"
            )
            continue

        # 最後の添付ファイルを取得
        latest_attachment_id = None
        for journal in detailed_issue.journals:
            for detail in journal.details:
                if detail["property"] == "attachment":
                    latest_attachment_id = detail["name"]

        if latest_attachment_id is None:
            print(
                f"No attachment found for {report_type} (project: {detailed_issue.project.name})"
            )
            continue

        latest_attachment = redmine.attachment.get(latest_attachment_id)
        print(f"{report_type} {latest_attachment.filename}")

        file_dir = OUTPUT_DIR / project_id / report_type
        shutil.rmtree(file_dir, ignore_errors=True)
        file_dir.mkdir(parents=True, exist_ok=True)
        file_dir = file_dir.resolve()
        latest_attachment.download(savepath=str(file_dir), filename="submission.bin")

        if report_type in TEST_MAP:
            test_names = TEST_MAP[report_type]
            # Extract source code
            root = run_extract(file_dir)
            print(f"Root: {root}")
            best_result = (None, 0)
            for test_name in test_names:
                result = run_tests(root, test_name)
                passed_count = len([r for r in result if r[1] == "passed"])
                print(f"{test_name}: {passed_count}/{len(result)}")
                if passed_count > best_result[1]:
                    best_result = (test_name, passed_count)

            print(f"Best test: {best_result[0]} ({best_result[1]}/{len(result)})")
