#!/usr/bin/env python3
"""Minimal agent-facing CLI for Untitled (Windows x64, local single-user).

This is the stable entry point referenced by SKILL.md and README. It only
wraps existing public workflow functions; it does not reimplement routing or
orchestration. All commands output JSON with the fixed top-level fields
``ok``, ``status``, ``data``, ``error``.

Usage:
    python untitled.py check-tools [--json]
    python untitled.py project-create <name> [--json]
    python untitled.py story-node-add <project> <title> [--description <text>] [--json]
    python untitled.py story-node-list <project> [--json]
    python untitled.py candidate-add <project> <url> [--json]
    python untitled.py process <project> [--json]
    python untitled.py status <project> [--json]
    python untitled.py run --project <name> --url <url> [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent / "skill" / "untitled" / "scripts"
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
    from acquisition import preflight_candidate

    try:
        candidate = preflight_candidate(
            args.project,
            args.url,
            search_query=args.search_query,
            node_title=args.node_title,
            override=args.override,
        )
        if candidate is None:
            return _emit(False, "PROJECT_NOT_FOUND", error=f"Project '{args.project}' not found")
        data = {
            "candidate_id": candidate.candidate_id,
            "url": candidate.display_url,
            "state": candidate.state,
            "provenance_score": candidate.provenance_score,
            "provenance_reasons": candidate.provenance_reasons,
            "rejection_reasons": candidate.rejection_reasons,
            "probe_error": candidate.probe_error,
            "title": candidate.title,
            "platform": candidate.platform,
            "overridden": candidate.overridden,
        }
        if candidate.state == "ACCEPTED":
            return _emit(True, "ACCEPTED", data)
        return _emit(False, candidate.state, data)
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
    from acquisition import preflight_candidate
    from orchestrator import process_pending
    from project import create_project, load_project, save_project

    try:
        if load_project(args.project) is None:
            project = create_project(args.project)
            save_project(project)
        candidate = preflight_candidate(
            args.project,
            args.url,
            search_query=args.search_query,
            node_title=args.node_title,
            override=args.override,
        )
        if candidate is None:
            return _emit(False, "PROJECT_NOT_FOUND", error=f"Project '{args.project}' not found")
        if candidate.state != "ACCEPTED":
            return _emit(
                False,
                candidate.state,
                {
                    "rejection_reasons": candidate.rejection_reasons,
                    "probe_error": candidate.probe_error,
                },
            )
        results = process_pending(args.project)
        ok = results["failed"] == 0
        status = "SUCCESS" if ok and results["processed"] else "NO_PENDING"
        if not ok:
            status = "PARTIAL" if results["success"] else "FAILED"
        return _emit(ok, status, results)
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def cmd_story_node_add(args: argparse.Namespace) -> int:
    from acquisition import add_story_node

    try:
        project = add_story_node(args.project, args.title, args.description)
        if project is None:
            return _emit(
                False,
                "PROJECT_NOT_FOUND",
                error=f"Project '{args.project}' not found",
            )
        node = project.story_nodes[-1]
        return _emit(
            True,
            "SUCCESS",
            {"node_id": node.node_id, "title": node.title},
        )
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def cmd_story_node_list(args: argparse.Namespace) -> int:
    from project import load_project

    try:
        project = load_project(args.project)
        if project is None:
            return _emit(
                False,
                "PROJECT_NOT_FOUND",
                error=f"Project '{args.project}' not found",
            )
        nodes = [
            {
                "node_id": n.node_id,
                "title": n.title,
                "description": n.description,
                "search_terms": n.search_terms,
                "candidate_urls": n.candidate_urls,
            }
            for n in project.story_nodes
        ]
        return _emit(True, "SUCCESS", {"nodes": nodes})
    except Exception as error:  # noqa: BLE001 - CLI boundary
        return _emit(False, "ERROR", error=str(error))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untitled",
        description=(
            "Untitled minimal agent-facing workflow CLI (Windows x64, local single-user)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check-tools", help="Check tool availability (READY/DEGRADED)")

    parser_project_create = subparsers.add_parser(
        "project-create", help="Create an acquisition project"
    )
    parser_project_create.add_argument("name", help="Project name (safe name rules apply)")

    parser_candidate_add = subparsers.add_parser(
        "candidate-add", help="Probe a candidate and enqueue it when accepted"
    )
    parser_candidate_add.add_argument("project", help="Project name")
    parser_candidate_add.add_argument("url", help="Candidate URL")
    parser_candidate_add.add_argument(
        "--search-query", default="", help="Original search query or strategy"
    )
    parser_candidate_add.add_argument(
        "--node-title", default="", help="Associated story node title"
    )
    parser_candidate_add.add_argument(
        "--override",
        action="store_true",
        help="Enqueue even when the provenance gate rejects the candidate (auditable)",
    )

    parser_process = subparsers.add_parser("process", help="Process the pending task queue")
    parser_process.add_argument("project", help="Project name")

    parser_story_node_add = subparsers.add_parser(
        "story-node-add", help="Add a story node to a project"
    )
    parser_story_node_add.add_argument("project", help="Project name")
    parser_story_node_add.add_argument("title", help="Story node title")
    parser_story_node_add.add_argument("--description", default="", help="Story node description")

    parser_story_node_list = subparsers.add_parser(
        "story-node-list", help="List story nodes of a project"
    )
    parser_story_node_list.add_argument("project", help="Project name")

    parser_status = subparsers.add_parser("status", help="Show project status")
    parser_status.add_argument("project", help="Project name")

    parser_run = subparsers.add_parser(
        "run", help="Create project (if needed), preflight a candidate, and process the queue"
    )
    parser_run.add_argument("--project", required=True, help="Project name")
    parser_run.add_argument("--url", required=True, help="Candidate URL")
    parser_run.add_argument("--search-query", default="", help="Original search query or strategy")
    parser_run.add_argument("--node-title", default="", help="Associated story node title")
    parser_run.add_argument(
        "--override",
        action="store_true",
        help="Enqueue even when the provenance gate rejects the candidate (auditable)",
    )

    for sub in subparsers.choices.values():
        sub.add_argument(
            "--json", action="store_true", help="Output JSON (default; kept for compatibility)"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    # Force UTF-8 stdio: on non-UTF-8 Windows locales (e.g. en-US cp1252 on
    # CI runners) printing JSON with ensure_ascii=False raises
    # UnicodeEncodeError for CJK titles. The CLI contract is UTF-8 JSON.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
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
    if args.command == "story-node-add":
        return cmd_story_node_add(args)
    if args.command == "story-node-list":
        return cmd_story_node_list(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "run":
        return cmd_run(args)
    parser.error(f"Unknown command: {args.command}")
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
