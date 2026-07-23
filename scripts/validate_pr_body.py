#!/usr/bin/env python3
"""Mechanically validate the AgenticWonderwall pull request template."""

import os
import re
import sys
from pathlib import Path

PLACEHOLDERS = ("<number>",)
ISSUE = re.compile(r"#\d+\b")
HEADERS = ("Result", "Changes", "Verification", "Agent self-review")
REQUIRED_REVIEW_ITEMS = (
    "满足 Issue 或明确人类授权",
    "没有扩大任务范围",
    "已阅读完整 diff",
    "必要验证已通过",
    "没有遗留调试代码、临时文件或缓存",
)


def section(body, heading):
    match = re.search(rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", body)
    return match.group(1).strip() if match else None


def validate(body):
    errors = []
    issue = re.search(r"(?m)^- Issue:[ \t]*(.*)$", body)
    source = re.search(r"(?m)^  - Authorization source:[ \t]*(.*)$", body)
    goal = re.search(r"(?m)^  - Goal:[ \t]*(.*)$", body)
    scope = re.search(r"(?m)^  - Scope:[ \t]*(.*)$", body)
    issue_value = issue.group(1).strip() if issue else ""
    authorization = [match.group(1).strip() if match else "" for match in (source, goal, scope)]

    for placeholder in PLACEHOLDERS:
        if placeholder in body:
            errors.append(f"Remove template placeholder text: {placeholder}.")
    has_issue = bool(issue_value)
    has_authorization = any(authorization)
    if has_issue == has_authorization:
        errors.append("Fill exactly one of Issue or explicit human authorization.")
    if has_issue and not ISSUE.search(issue_value):
        errors.append("Issue must contain a valid reference such as #123.")
    if has_authorization:
        for name, value in zip(("Authorization source", "Goal", "Scope"), authorization):
            if not value:
                errors.append(f"Explicit human authorization requires {name}.")

    for heading in HEADERS[:3]:
        content = section(body, heading)
        if not content:
            errors.append(f"{heading} must not be empty.")
    review = section(body, "Agent self-review") or ""
    for item in REQUIRED_REVIEW_ITEMS:
        checked = re.search(rf"(?m)^- \[[xX]\] {re.escape(item)}$", review)
        present = re.search(rf"(?m)^- \[[ xX]\] {re.escape(item)}$", review)
        if not checked:
            errors.append(
                f"Agent self-review item must be checked: {item}."
                if present else f"Agent self-review item is missing: {item}."
            )
    return errors


def main():
    body = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) == 2 else os.environ.get("PR_BODY", sys.stdin.read())
    errors = validate(body)
    if errors:
        print("Pull Request body validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Pull Request body is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())