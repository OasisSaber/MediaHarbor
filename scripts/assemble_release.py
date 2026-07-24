#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

RELEASE_ITEMS = ["AGENT_READ_ME_FIRST.md", "skill", "LICENSE"]
TOOLS_JSON = "download-tools/tools.json"
TOOLS_README = "download-tools/README.md"
ROUTING_JSON = "download-tools/routing.json"
THIRD_PARTY_NOTICES = "download-tools/THIRD_PARTY_NOTICES.md"
TOOL_METADATA_JSON = "download-tools/tool-metadata.json"
RELEASE_MARKER = "download-tools/.mediaharbor-release"


def _compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_tool_metadata(root: Path) -> dict[str, dict]:
    meta_path = root / TOOL_METADATA_JSON
    if not meta_path.is_file():
        return {}
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    result = {}
    for name, entry in data.get("tools", {}).items():
        info = {}
        if "name" in entry:
            info["name"] = entry["name"]
        if "upstream" in entry:
            info["source"] = entry["upstream"]
        if "license" in entry:
            info["license"] = entry["license"]
        if "build_license" in entry:
            info["build_license"] = entry["build_license"]
        if "build_source" in entry:
            info["build_source"] = entry["build_source"]
        if "platforms" in entry:
            info["platforms"] = entry["platforms"]
        info["name"] = entry.get("name", name)
        result[name] = info
    return result


def find_root() -> Path:
    script = Path(__file__).resolve()
    for parent in [script] + list(script.parents):
        if (parent / "AGENT_READ_ME_FIRST.md").is_file():
            return parent
    raise RuntimeError("Cannot find MediaHarbor root")


def _validate_target(root: Path, output_dir: Path, target: Path):
    try:
        target.resolve().relative_to(output_dir.resolve())
    except ValueError:
        raise ValueError(f"Target {target} is not inside output directory {output_dir}")
    if target.resolve() == root.resolve():
        raise ValueError("Cannot overwrite source repository")
    if root.resolve() in target.resolve().parents:
        raise ValueError("Target inside source repository")
    if target.is_symlink() or str(target) != str(target.resolve()):
        raise ValueError("Symlinks/junctions not allowed as target")


def _safe_copy_tools(root: Path, release_root: Path, tool_source: Path | None) -> bool:
    tools_dst = release_root / "download-tools"
    tools_dst.mkdir(parents=True, exist_ok=True)

    for json_file in [TOOLS_JSON, ROUTING_JSON, TOOLS_README, THIRD_PARTY_NOTICES]:
        src = root / json_file
        if src.is_file():
            shutil.copy2(src, tools_dst / src.name)

    if not tool_source:
        return False

    tool_source = tool_source.resolve()
    if not tool_source.is_dir():
        raise ValueError(f"Tool source not a directory: {tool_source}")

    tools_path = root / TOOLS_JSON
    if not tools_path.is_file():
        raise RuntimeError("tools.json not found")
    data = json.loads(tools_path.read_text(encoding="utf-8"))
    metadata = _load_tool_metadata(root)
    has_tools = False

    manifest = {"tools": {}}
    for name, entry in data.get("tools", {}).items():
        raw = entry.get("platforms", {}).get("windows-x64", "")
        if not raw and entry.get("path_windows"):
            raw = entry["path_windows"]
        if not raw:
            if entry.get("required"):
                raise RuntimeError(f"Required tool '{name}' has no platform path")
            manifest["tools"][name] = {"status": "optional-missing-path"}
            continue
        src_file = tool_source / raw
        if not src_file.is_file():
            if entry.get("required"):
                raise RuntimeError(f"Required tool '{name}' not found at {src_file}")
            manifest["tools"][name] = {"status": "optional-not-found"}
            continue
        dst_file = tools_dst / raw
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        tool_entry = {
            "status": "copied",
            "path": raw,
            "sha256": _compute_sha256(dst_file),
            "version": "UNVERIFIED",
            "platform": "windows-x64",
            "binary_source": str(src_file.resolve()),
        }
        if name in metadata:
            tool_entry.update(metadata[name])
        manifest["tools"][name] = tool_entry
        has_tools = True

    manifest_path = tools_dst / "tool-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return has_tools


def validate_release_marker(target: Path):
    marker = target / RELEASE_MARKER
    if not marker.is_file():
        raise ValueError(f"No release marker at {marker}")
    if marker.is_symlink():
        raise ValueError("Marker is a symlink, refusing")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Marker is not valid JSON")
    if data.get("marker") != "mediaharbor-release":
        raise ValueError(f"Unknown marker type: {data.get('marker')}")
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported marker schema: {data.get('schema_version')}")
    required = ["AGENT_READ_ME_FIRST.md", "skill/mediaharbor/SKILL.md", "download-tools/tools.json"]
    for r in required:
        if not (target / r).exists():
            raise ValueError(f"Release missing required file: {r}")
    for p in [target] + list(target.parents):
        if p.is_symlink():
            raise ValueError(f"Parent path is symlink: {p}")
    resolved_target = target.resolve()
    if resolved_target != target:
        raise ValueError("Target path involves symlinks")


def assemble(output_dir: Path, force: bool = False, tool_source: Path | None = None) -> Path:
    root = find_root()
    target = output_dir / "MediaHarbor"

    _validate_target(root, output_dir, target)

    if target.exists():
        if not force:
            raise RuntimeError(f"Target exists: {target}. Use --force to overwrite.")
        validate_release_marker(target)
        shutil.rmtree(target)

    target.mkdir(parents=True)

    for item in RELEASE_ITEMS:
        src = root / item
        dst = target / item
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif src.is_file():
            shutil.copy2(src, dst)

    has_tools = _safe_copy_tools(root, target, tool_source)

    marker_path = target / RELEASE_MARKER
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "marker": "mediaharbor-release",
        "schema_version": 1,
        "package_type": "full" if has_tools else "shell",
    }
    marker_path.write_text(json.dumps(marker_data))

    return target


def main():
    parser = argparse.ArgumentParser(description="Assemble MediaHarbor Release")
    parser.add_argument("--output-dir", default=".", type=Path, help="Output directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing release")
    parser.add_argument("--tool-source", type=Path, help="Directory with binaries to copy")
    args = parser.parse_args()
    release_path = assemble(
        Path(args.output_dir).resolve(), force=args.force, tool_source=args.tool_source
    )
    print(f"Release assembled: {release_path}")


if __name__ == "__main__":
    main()
