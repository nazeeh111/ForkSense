"""Fetch three selected SWE-bench Lite cases without saving a reference solution.

Artifacts and test patches live in the supplied external directory. The agent's
repository contains only the exact upstream base commit, never the test patch.
This is a lightweight issue reproduction, not the official Docker harness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

DATASET = "princeton-nlp/SWE-bench_Lite"
CASES = {
    "pallets__flask-4045": "d8c37f43724cd9fb0870f77877b7c4c7e38a19e0",
    "pallets__flask-4992": "4c288bc97ea371817199908d0d9b12de9dae327e",
    "pallets__flask-5063": "182ce3dd15dfa3537391c3efaf9c3ff407d134d4",
}
ISSUES = {"pallets__flask-4045": "4041", "pallets__flask-4992": "4989", "pallets__flask-5063": "5004"}
DEPS = {
    "2.0": ["Werkzeug==2.0.3", "Jinja2==3.0.3", "itsdangerous==2.0.1", "click==8.0.4", "MarkupSafe==3.0.3", "pytest==8.4.2"],
    "2.3": ["Werkzeug==2.3.8", "Jinja2==3.1.6", "itsdangerous==2.2.0", "click==8.1.8", "blinker==1.9.0", "MarkupSafe==3.0.3", "pytest==8.4.2", "python-dotenv==1.0.1", "asgiref==3.8.1"],
}


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory outside every agent repository")
    parser.add_argument("--case", choices=CASES, action="append")
    parser.add_argument("--install", action="store_true", help="Create per-case venv with pinned compatibility dependencies")
    parser.add_argument("--python", default=sys.executable, help="Interpreter for compatibility venvs; Python 3.12 recommended")
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        parser.error("output must be fresh; prior evidence is never replaced")
    out.mkdir(parents=True)
    selected = set(args.case or CASES)
    frozen = {case["instance_id"]: case for case in json.loads(Path(__file__).with_name("manifest.json").read_text())}
    url = "https://datasets-server.huggingface.co/rows?dataset=" + DATASET + "&config=default&split=test&offset=100&length=100"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    found = set()
    for item in payload["rows"]:
        row = item["row"]
        case = row["instance_id"]
        if case not in selected:
            continue
        if row["base_commit"] != CASES[case]:
            raise RuntimeError("dataset base changed: " + case)
        if hashlib.sha256(row["test_patch"].encode()).hexdigest() != frozen[case]["test_patch_sha256"]:
            raise RuntimeError("dataset test patch changed: " + case)
        if hashlib.sha256(row["problem_statement"].encode()).hexdigest() != frozen[case]["problem_statement_sha256"]:
            raise RuntimeError("dataset problem statement changed: " + case)
        found.add(case)
        folder = out / case
        folder.mkdir()
        # Deliberately use an allowlist. Never save row['patch'] or hints_text.
        fields = ("instance_id", "repo", "base_commit", "problem_statement", "version", "created_at", "environment_setup_commit")
        metadata = {key: row[key] for key in fields if key in row}
        metadata.update({"dataset": DATASET, "split": "test", "row_idx": item["row_idx"], "source_url": url,
                         "original_issue_url": "https://github.com/" + row["repo"] + "/issues/" + ISSUES[case],
                         "dataset_pull_request_url": "https://github.com/" + row["repo"] + "/pull/" + case.rsplit("-", 1)[1],
                         "test_patch_sha256": hashlib.sha256(row["test_patch"].encode()).hexdigest(),
                         "FAIL_TO_PASS": json.loads(row["FAIL_TO_PASS"]), "PASS_TO_PASS": json.loads(row["PASS_TO_PASS"]),
                         "compatibility_dependencies": DEPS[row["version"]],
                         "evaluation_kind": "selected SWE-bench Lite issue reproduction; not official Docker evaluation"})
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        (folder / "problem.txt").write_text(row["problem_statement"])
        (folder / "test.patch").write_text(row["test_patch"])
        repo = folder / "repo"
        repo.mkdir()
        run("git", "init", "--quiet", str(repo))
        run("git", "-C", str(repo), "fetch", "--quiet", "--depth=1", "https://github.com/" + row["repo"] + ".git", row["base_commit"])
        run("git", "-C", str(repo), "checkout", "--quiet", "--detach", "FETCH_HEAD")
        if args.install:
            env = folder / "venv"
            run(args.python, "-m", "venv", str(env))
            python = str(env / "bin" / "python")
            run(python, "-m", "pip", "install", "--disable-pip-version-check", *DEPS[row["version"]])
        print(case, "prepared at", folder, flush=True)
    if found != selected:
        raise RuntimeError("missing dataset rows: " + str(selected - found))


if __name__ == "__main__":
    main()
