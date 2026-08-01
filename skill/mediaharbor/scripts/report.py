from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from _common import ensure_output_dir
from project import MaterialInfo, load_project
from safe_path import resolve_project_dir


def _material_group(material: MaterialInfo) -> str:
    if material.editorial_status == "REJECT":
        return "rejected"
    if material.editorial_status == "ACCEPT":
        return "accepted"
    if material.editorial_status == "REVIEW_REQUIRED":
        return "needs-review"
    return "unassessed"


def _material_lines(material: MaterialInfo) -> list[str]:
    lines = [f"  - {material.local_path} ({material.source_url})"]
    lines.append(
        f"    - technical: {material.technical_status or 'UNKNOWN'}, "
        f"quality: {material.quality_status or 'UNKNOWN'}, "
        f"editorial: {material.editorial_status or 'UNREVIEWED'}"
    )
    if material.technical_reasons:
        lines.append(f"    - technical reasons: {', '.join(material.technical_reasons)}")
    if material.quality_reasons:
        lines.append(f"    - quality reasons: {', '.join(material.quality_reasons)}")
    if material.editorial_reasons:
        lines.append(f"    - editorial reasons: {', '.join(material.editorial_reasons)}")
    if material.override_metadata:
        lines.append(f"    - override: {material.override_metadata}")
    return lines


def generate_coverage_report(project_name: str) -> str | None:
    project = load_project(project_name)
    if project is None:
        return None

    lines = [f"# Coverage Report: {project.name}", ""]
    total = len(project.tasks)
    completed = sum(1 for t in project.tasks if t.status == "COMPLETED")
    failed = sum(1 for t in project.tasks if t.status == "FAILED")
    pending = sum(1 for t in project.tasks if t.status == "PENDING")

    lines.append(f"**Total URLs:** {total}")
    lines.append(f"**Completed:** {completed}")
    lines.append(f"**Failed:** {failed}")
    lines.append(f"**Pending:** {pending}")
    lines.append("")

    if project.story_nodes:
        lines.append("## Story Nodes")
        for node in project.story_nodes:
            lines.append("")
            lines.append(f"### {node.title}")
            lines.append(f"{node.description}")
            if node.search_terms:
                lines.append(f"  - Search terms: {', '.join(node.search_terms)}")
            if node.candidate_urls:
                for url in node.candidate_urls:
                    task = next((t for t in project.tasks if t.url == url), None)
                    status = task.status if task else "NOT_QUEUED"
                    lines.append(f"  - [{status}] {url}")

    lines.append("")
    lines.append("## Materials")
    if not project.materials:
        lines.append("  - (none)")
    else:
        groups: dict[str, list[MaterialInfo]] = {}
        for material in project.materials:
            groups.setdefault(_material_group(material), []).append(material)
        for group in ("accepted", "needs-review", "rejected", "unassessed"):
            members = groups.get(group, [])
            lines.append("")
            lines.append(f"### {group.replace('-', ' ')}")
            for material in members:
                lines.extend(_material_lines(material))

    return "\n".join(lines)


def generate_handoff(project_name: str) -> str | None:
    project = load_project(project_name)
    if project is None:
        return None

    lines = [
        f"# Human Editor Handoff: {project.name}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Materials Collected",
        "",
    ]

    for m in project.materials:
        lines.append(f"- {m.local_path}")
        lines.append(f"  - Source: {m.source_url}")
        if m.duration:
            lines.append(f"  - Duration: {m.duration}s")
        if m.width and m.height:
            lines.append(f"  - Resolution: {m.width}x{m.height}")
        lines.append(
            f"  - Technical: {m.technical_status or 'UNKNOWN'} | "
            f"Quality: {m.quality_status or 'UNKNOWN'} | "
            f"Editorial: {m.editorial_status or 'UNREVIEWED'}"
        )
        if m.technical_reasons:
            lines.append(f"  - Technical reasons: {', '.join(m.technical_reasons)}")
        if m.quality_reasons:
            lines.append(f"  - Quality reasons: {', '.join(m.quality_reasons)}")
        if m.editorial_reasons:
            lines.append(f"  - Editorial reasons: {', '.join(m.editorial_reasons)}")
        if m.override_metadata:
            lines.append(f"  - Override: {m.override_metadata}")
        lines.append("")

    lines.append("## Story Notes")
    if project.story_nodes:
        for node in project.story_nodes:
            lines.append("")
            lines.append(f"### {node.title}")
            if node.description:
                lines.append(node.description)
            if node.search_terms:
                lines.append(f"  - Search terms: {', '.join(node.search_terms)}")
            if node.candidate_urls:
                for url in node.candidate_urls:
                    material = next((m for m in project.materials if m.source_url == url), None)
                    if material:
                        lines.append(f"  - Material: {material.local_path} ({url})")
                    else:
                        lines.append(f"  - No material collected yet: {url}")
    if project.script:
        lines.append("")
        lines.append("### Original Script")
        lines.append(project.script)
        lines.append("")

    lines.append("")
    lines.append("## Important Notes")
    lines.append("")
    lines.append("- **Download success does not guarantee the material is suitable for editing.**")
    lines.append("- Human review is required for clip selection, timing, and narrative fit.")
    lines.append("- Verify copyright and licensing before use in final production.")
    lines.append("- Redistributable assets may require permission or attribution.")
    lines.append("")
    lines.append("---")
    lines.append("*This handoff was automatically generated by MediaHarbor.*")

    return "\n".join(lines)


def save_report(project_name: str) -> Path | None:
    report = generate_coverage_report(project_name)
    if report is None:
        return None
    root = ensure_output_dir()
    pdir = resolve_project_dir(root, project_name) / "reports"
    pdir.mkdir(parents=True, exist_ok=True)
    path = pdir / "COVERAGE_REPORT.md"
    path.write_text(report, encoding="utf-8")
    return path


def save_handoff(project_name: str) -> Path | None:
    handoff = generate_handoff(project_name)
    if handoff is None:
        return None
    root = ensure_output_dir()
    pdir = resolve_project_dir(root, project_name) / "reports"
    pdir.mkdir(parents=True, exist_ok=True)
    path = pdir / "HUMAN_EDITOR_HANDOFF.md"
    path.write_text(handoff, encoding="utf-8")
    return path
