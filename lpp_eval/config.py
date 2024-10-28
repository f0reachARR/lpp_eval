import os
from pathlib import Path
from typing import Dict, List

# Submission collector
REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")

# Submission reporter
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
LIMITED_CASES = os.getenv("LIMITED_CASES", "").split(",")

# Test runner
TEST_MAP: Dict[str, List[str]] = {
    "program01": ["01test", "01test_ex"],
}
TEST_DOCKER_IMAGE = os.getenv(
    "TEST_DOCKER_IMAGE", "ghcr.io/f0reacharr/lpp_test_eval:latest"
)
TEST_TEMP_DIR = Path(os.getenv("TEST_TEMP_DIR", "./tmp")).resolve()
BUILD_OUT_MAP = {"01": "tc", "02": "pp", "03": "cr", "04": "mpplc"}
