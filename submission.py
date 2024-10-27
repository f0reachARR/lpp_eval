import os
from typing import Dict, List, Literal
from redminelib import Redmine
from redminelib.resources import Issue
from pprint import pprint

REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")

redmine = Redmine(REDMINE_URL, key=REDMINE_API_KEY)

# 1: 新規, 2: 進行中, 3: 審査合格, 4: 審査待ち, 5: 終了, 6: 却下, 13: 受理, 16: 解決済み, 15: 一次確認, 14: 差し戻し
# トラッカーID 15: 提出

SUBJECT_MAP: Dict[str, Literal["program"] | Literal["report"]] = {
    "01.06 プログラムの提出": "program",
    "01.07 レポートの提出": "report",
}

if __name__ == "__main__":
    issues: List[Issue] = redmine.issue.filter(status_id=4, tracker_id=15)
    for issue in issues:
        detailed_issue: Issue = redmine.issue.get(issue.id, include=["journals"])

        report_type = SUBJECT_MAP.get(detailed_issue.subject)

        if report_type is None:
            print(
                f"Unknown report type: {detailed_issue.subject} (project: {detailed_issue.project.name})"
            )
            continue

        # 最後の添付ファイルを取得
        for journal in detailed_issue.journals:
            for detail in journal.details:
                if detail["property"] == "attachment":
                    latest_attachment = redmine.attachment.get(detail["name"])
                    print(f"{report_type} {latest_attachment.filename}")
                    # attachment.download(f"downloads/{attachment.filename}")
                    # break
