#!/usr/bin/env python3
"""Minimal agent-facing CLI for MediaHarbor (Windows x64, local single-user).

This is the stable entry point referenced by SKILL.md and README. It only
wraps existing public workflow functions; it does not reimplement routing or
orchestration. All commands output JSON with the fixed top-level fields
``ok``, ``status``, ``data``, ``error``.

Usage:
    python mediaharbor.py check-tools [--json]
    python mediaharbor.py project-create <name> [--json]
    python mediaharbor.py candidate-add <project> <url> [--json]
    python mediaharbor.py process <project> [--json]
    python mediaharbor.py status <project> [--json]
    python mediaharbor.py run --project <name> --url <url> [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent / "skill" / "mediaharbor" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

EXIT_OK = 0
EXIT_FAIL = 1


def _emit(ok: bool, status: str, data: dict | None = None, error: str | None = None) -> int:
    payload = {
        "ok": ok,
        "status": status,
        "data": data or {},
        "error": error,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_FAIL


def cmd_check_tools(_args: argparse.Namespace) -> int:
    from _common import check_tools, load_registry

    try:
        registry = load_registry()
        result = check_tools(registry)
        data = {
            "tools": {
                name: {
                    "path": tool.path,
                    "exists": tool.exists,
                    "required": tool.required,
                    "roles": tool.roles,
                }
                for name, tool in result.tools.items()
            }
        }
        return _emit(True, result.status, data)
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def cmd_project_create(args: argparse.Namespace) -> int:
    from project import create_project, save_project

    try:
        project = create_project(args.name)
        save_project(project)
        return _emit(
            True,
            "SUCCESS",
            {"name": project.name, "project_id": project.project_id},
        )
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def cmd_candidate_add(args: argparse.Namespace) -> int:
    from acquisition import add_candidate

    try:
        project = add_candidate(args.project, args.url)
        if project is None:
            return _emit(False, "PROJECT_NOT_FOUND", error=f"Project '{args.project}' not found")
        task = project.tasks[-1]
        return _emit(
            True,
            "SUCCESS",
            {"url": task.url, "task_id": task.task_id, "status": task.status},
        )
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def cmd_process(args: argparse.Namespace) -> int:
    from orchestrator import process_pending

    try:
        results = process_pending(args.project)
        ok = results["failed"] == 0
        status = "SUCCESS" if ok and results["processed"] else "NO_PENDING"
        if not ok:
            status = "PARTIAL" if results["success"] else "FAILED"
        return _emit(ok, status, results)
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def cmd_status(args: argparse.Namespace) -> int:
    from project import load_project

    try:
        project = load_project(args.project)
        if project is None:
            return _emit(False, "PROJECT_NOT_FOUND", error=f"Project '{args.project}' not found")
        data = {
            "name": project.name,
            "project_id": project.project_id,
            "script": project.script,
            "tasks": [
                {
                    "url": task.url,
                    "task_id": task.task_id,
                    "status": task.status,
                    "backend": task.backend,
                    "error": task.error,
                }
                for task in project.tasks
            ],
            "materials": [
                {
                    "local_path": material.local_path,
                    "source_url": material.source_url,
                    "file_hash": material.file_hash,
                    "verified": material.verified,
                }
                for material in project.materials
            ],
        }
        return _emit(True, "SUCCESS", data)
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def cmd_run(args: argparse.Namespace) -> int:
    from acquisition import add_candidate
    from orchestrator import process_pending
    from project import create_project, load_project, save_project

    try:
        if load_project(args.project) is None:
            project = create_project(args.project)
            save_project(project)
        added = add_candidate(args.project, args.url)
        if added is None:
            return _emit(False, "PROJECT_NOT_FOUND", error=f"Project '{args.project}' not found")
        results = process_pending(args.project)
        ok = results["failed"] == 0
        status = "SUCCESS" if ok and results["processed"] else "NO_PENDING"
        if not ok:
            status = "PARTIAL" if results["success"] else "FAILED"
        return _emit(ok, status, results)
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mediaharbor",
        description=(
            "MediaHarbor minimal agent-facing workflow CLI (Windows x64, local single-user)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check-tools", help="Check tool availability (READY/DEGRADED)")

    parser_project_create = subparsers.add_parser(
        "project-create", help="Create an acquisition project"
    )
    parser_project_create.add_argument("name", help="Project name (safe name rules apply)")

    parser_candidate_add = subparsers.add_parser(
        "candidate-add", help="Add a candidate URL to a project"
    )
    parser_candidate_add.add_argument("project", help="Project name")
    parser_candidate_add.add_argument("url", help="Candidate URL")

    parser_process = subparsers.add_parser("process", help="Process the pending task queue")
    parser_process.add_argument("project", help="Project name")

    parser_status = subparsers.add_parser("status", help="Show project status")
    parser_status.add_argument("project", help="Project name")

    parser_run = subparsers.add_parser(
        "run", help="Create project (if needed), add candidate, and process the queue"
    )
    parser_run.add_argument("--project", required=True, help="Project name")
    parser_run.add_argument("--url", required=True, help="Candidate URL")

    for sub in subparsers.choices.values():
        sub.add_argument(
            "--json", action="store_true", help="Output JSON (default; kept for compatibility)"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check-tools":
        return cmd_check_tools(args)
    if args.command == "project-create":
        return cmd_project_create(args)
    if args.command == "candidate-add":
        return cmd_candidate_add(args)
    if args.command == "process":
        return cmd_process(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "run":
        return cmd_run(args)
    parser.error(f"Unknown command: {args.command}")
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
