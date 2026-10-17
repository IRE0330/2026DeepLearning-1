"""Check publishable files/index blobs without displaying secret values."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private_key": rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    "github_token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "api_token": rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}",
    "aws_access_key": rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "url_credentials": rb"https?://[^/\s@:]+:[^/@\s]+@",
}
EXCLUDED_PROBES = [
    "북쪽_화장실_cctv.mp4", "nested/sample.MOV", "nested/data/micc/RGB/0001.png",
    "nested/models/yolo11n.pt", "nested/.venv/Lib/site-packages/x.py", "nested/__pycache__/x.pyc",
    "outputs/nested/report.csv", "inspections/nested/report.json", "nested/.env.production",
    "nested/private.pem", "nested/.ssh/id_ed25519", "nested/credentials.json",
    "nested/micc.zip", "configs/north.preview.jpg",
    "nested/.venv-cctv/pyvenv.cfg", "dist/package.whl",
    "cctv-analysis/dist/package.whl", "cctv-analysis/build/lib/cctv/core.py",
    "cctv-analysis/src/cctv/data/outputs/report.json",
    "cctv-analysis/src/cctv/data/configs/.env",
    "cctv-analysis/src/cctv/data/configs/credentials.json",
    "cctv-analysis/src/cctv/data/ground_truth/north/token.json",
]
INCLUDED_PROBES = ["configs/north.json", "configs/south.json", "configs/east.json",
                   "configs/profiles/demo.json", "configs/video_registry.json",
                   "ground_truth/north/events.csv", "ground_truth/example_only/events.csv",
                   "docs/HANDOFF.md", "cctv/__init__.py", "tests/test_record_intervals.py",
                   "cctv-analysis/pyproject.toml", "cctv-analysis/src/cctv/core.py",
                   "cctv-analysis/src/cctv/data/configs/north.json",
                   "cctv-analysis/src/cctv/data/configs/profiles/demo.json",
                   "cctv-analysis/src/cctv/data/ground_truth/north/events.csv"]


def git(*args, input_data=None):
    return subprocess.run(["git", *args], cwd=ROOT, input=input_data,
                          capture_output=True, check=True).stdout


def findings(data):
    return [name for name, pattern in PATTERNS.items() if re.search(pattern, data)]


def check(staged=False):
    paths = set(git("ls-files", "-z").decode("utf-8").split("\0")) - {""}
    if not staged:
        paths.update(set(git("ls-files", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")) - {""})
    issues, sizes = [], []
    for path in sorted(paths):
        data = git("show", ":" + path) if staged else (ROOT / path).read_bytes()
        sizes.append({"path": path, "bytes": len(data)})
        for category in findings(data):
            issues.append({"path": path, "reason": category})
        if len(data) > 10 * 1024 * 1024:
            issues.append({"path": path, "reason": "over_10_MiB_review_required"})
        if re.search(rb"(?:[A-Za-z]:[\\/]+Users[\\/]|/(?:Users|home)/[A-Za-z0-9_.-]+/)", data):
            issues.append({"path": path, "reason": "personal_absolute_path"})
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", path], cwd=ROOT)
        if ignored.returncode == 0:
            issues.append({"path": path, "reason": "excluded_file_already_tracked"})
        elif ignored.returncode != 1:
            issues.append({"path": path, "reason": "ignore_check_error"})
    ignore_checks = []
    for path, expected in [(p, True) for p in EXCLUDED_PROBES] + [(p, False) for p in INCLUDED_PROBES]:
        result = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", path], cwd=ROOT)
        ok = result.returncode == (0 if expected else 1)
        ignore_checks.append({"path": path, "should_ignore": expected, "passed": ok})
        if not ok:
            issues.append({"path": path, "reason": "ignore_rule_mismatch"})
    history_blobs = {}
    for line in git("rev-list", "--objects", "origin/main").decode("utf-8").splitlines():
        oid, _, path = line.partition(" ")
        if git("cat-file", "-t", oid).strip() == b"blob":
            categories = findings(git("cat-file", "blob", oid))
            history_blobs[oid] = {"path": path, "secret_pattern_matches": categories}
            if categories:
                issues.append({"path": path, "object": oid, "reason": "remote_history_secret_pattern"})
    return {"scope": "index_blobs" if staged else "publishable_working_files",
            "branch": git("branch", "--show-current").decode().strip(),
            "remote_main_base": git("rev-parse", "origin/main").decode().strip(),
            "file_count": len(paths), "total_bytes": sum(s["bytes"] for s in sizes),
            "largest_files": sorted(sizes, key=lambda s: s["bytes"], reverse=True)[:8],
            "ignore_checks": ignore_checks, "remote_history_blobs": history_blobs,
            "issues": issues, "passed": not issues,
            "limitation": "Pattern scan and explicit review; not a guarantee of every possible secret format."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--report", help="Optional JSON report path, relative to the project")
    args = parser.parse_args()
    report = check(args.staged)
    if args.report:
        (ROOT / args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Checked {report['file_count']} files / {report['total_bytes']} bytes; pass={report['passed']}")
    for issue in report["issues"]:
        print(json.dumps(issue, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)
