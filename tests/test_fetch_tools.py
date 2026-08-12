from __future__ import annotations

import contextlib
import functools
import hashlib
import http.server
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import warnings
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FETCH = REPO_ROOT / "scripts" / "fetch_tools.py"

TOOLS_JSON = (
    '{"schema_version": 1, "tools": {"d": {"roles": ["t"], '
    '"platforms": {"windows-x64": "d/d.exe"}}}}'
)


def _setup_workspace(tmp: str) -> Path:
    root = Path(tmp)
    (root / "AGENT_READ_ME_FIRST.md").write_text("", encoding="utf-8")
    (root / "download-tools").mkdir(parents=True, exist_ok=True)
    (root / "download-tools" / "tools.json").write_text(TOOLS_JSON, encoding="utf-8")
    (root / "skill" / "untitled" / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "untitled" / "SKILL.md").write_text(
        "---\ntitle: test\n---\n", encoding="utf-8"
    )
    return root


def _write_manifest(
    root: Path,
    base_url: str,
    archive: str,
    sha256: str,
    provides: list[str],
    *,
    release_required: bool = True,
) -> None:
    manifest = {
        "schema_version": 1,
        "release_required": release_required,
        "release_base_url": base_url,
        "tools": {
            "yt-dlp": {
                "kind": "zip",
                "version": "test-1.0",
                "archive": archive,
                "sha256": sha256,
                "license": "Unlicense",
                "upstream": "https://example.com/upstream",
                "provides": provides,
            },
            "yutto": {
                "kind": "pip",
                "version": "2.2.0",
                "package": "yutto",
                "module": "yutto",
                "license": "GPL-3.0",
                "upstream": "https://github.com/yutto-dev/yutto",
            },
        },
    }
    (root / "tools-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _make_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_checksums(directory: Path, entries: dict[str, str]) -> None:
    text = "".join(f"{digest}  {name}\n" for name, digest in entries.items())
    (directory / "SHA256SUMS.txt").write_text(text, encoding="ascii")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # -S isolates python-module detection from packages installed on the host.
    return subprocess.run(
        [sys.executable, "-S", str(FETCH), "--root", str(root), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
        check=False,
    )


def _load_fetch_module():
    spec = importlib.util.spec_from_file_location("untitled_fetch_tools_test", FETCH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def _serve(directory: Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, _format: str, *_args) -> None:
            return

    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_install_zip_tool():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        source = Path(tmp) / "src"
        source.mkdir()
        _make_zip(source / "tool.zip", {"yt-dlp/yt-dlp.exe": b"fake-binary"})
        sha = hashlib.sha256((source / "tool.zip").read_bytes()).hexdigest()
        _write_manifest(root, source.as_uri(), "tool.zip", sha, ["yt-dlp/yt-dlp.exe"])

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 0, result.stdout + result.stderr
        assert "installed" in result.stdout
        target = root / "download-tools" / "yt-dlp" / "yt-dlp.exe"
        assert target.is_file()
        assert target.read_bytes() == b"fake-binary"


def test_sha256_mismatch_rejected_without_installing():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        source = Path(tmp) / "src"
        source.mkdir()
        _make_zip(source / "tool.zip", {"yt-dlp/yt-dlp.exe": b"fake-binary"})
        _write_manifest(root, source.as_uri(), "tool.zip", "0" * 64, ["yt-dlp/yt-dlp.exe"])

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 1
        assert "sha256 mismatch" in result.stdout
        assert not (root / "download-tools" / "yt-dlp" / "yt-dlp.exe").exists()


def test_zip_slip_member_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        source = Path(tmp) / "src"
        source.mkdir()
        _make_zip(source / "tool.zip", {"../evil.txt": b"evil"})
        sha = hashlib.sha256((source / "tool.zip").read_bytes()).hexdigest()
        _write_manifest(root, source.as_uri(), "tool.zip", sha, ["../evil.txt"])

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 1
        assert "unsafe" in result.stdout
        assert not (Path(tmp) / "evil.txt").exists()


def test_declared_member_missing_from_archive_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        source = Path(tmp) / "src"
        source.mkdir()
        _make_zip(source / "tool.zip", {"other/file.exe": b"wrong"})
        sha = hashlib.sha256((source / "tool.zip").read_bytes()).hexdigest()
        _write_manifest(root, source.as_uri(), "tool.zip", sha, ["yt-dlp/yt-dlp.exe"])

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 1
        assert "declared member missing" in result.stdout
        assert not (root / "download-tools" / "yt-dlp" / "yt-dlp.exe").exists()


def test_installed_tool_is_skipped_without_force():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        tool_dir = root / "download-tools" / "yt-dlp"
        tool_dir.mkdir(parents=True)
        (tool_dir / "yt-dlp.exe").write_bytes(b"existing")
        _write_manifest(
            root,
            "https://invalid.invalid",
            "tool.zip",
            "0" * 64,
            ["yt-dlp/yt-dlp.exe"],
        )

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 0
        assert "already installed" in result.stdout


def test_check_reports_missing_and_ready():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        tool_dir = root / "download-tools" / "yt-dlp"
        tool_dir.mkdir(parents=True)
        (tool_dir / "yt-dlp.exe").write_bytes(b"x")
        _write_manifest(
            root,
            "https://invalid.invalid",
            "tool.zip",
            "0" * 64,
            ["yt-dlp/yt-dlp.exe"],
        )

        result = _run(root, "--check")

        assert result.returncode == 1
        assert "yt-dlp: ready" in result.stdout
        assert "yutto: missing" in result.stdout


def test_pip_tool_prints_active_interpreter_guidance():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        _write_manifest(
            root,
            "https://invalid.invalid",
            "tool.zip",
            "0" * 64,
            ["yt-dlp/yt-dlp.exe"],
        )

        result = _run(root, "--tool", "yutto")

        assert result.returncode == 0
        assert "-m pip install yutto" in result.stdout
        assert "untitled.py check-tools" in result.stdout


def test_unknown_tool_returns_actionable_error():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        _write_manifest(
            root,
            "https://invalid.invalid",
            "tool.zip",
            "0" * 64,
            ["yt-dlp/yt-dlp.exe"],
        )

        result = _run(root, "--tool", "does-not-exist")

        assert result.returncode == 1
        assert "unknown tool" in result.stdout


def test_manifest_requires_explicit_release_required_boolean():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        (root / "tools-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "release_base_url": "https://example.invalid/x",
                    "tools": {
                        "bad": {
                            "kind": "zip",
                            "version": "1",
                            "archive": "a.zip",
                            "sha256": "0" * 64,
                            "license": "X",
                            "upstream": "u",
                            "provides": ["a.exe"],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "release_required" in result.stdout


def test_optional_unpublished_release_skips_remote_verification():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        _write_manifest(
            root,
            "https://invalid.invalid/not-published",
            "tool.zip",
            "0" * 64,
            ["yt-dlp/yt-dlp.exe"],
            release_required=False,
        )

        result = _run(root, "--verify-manifest")

        assert result.returncode == 0, result.stdout
        assert "remote Release and assets were not verified" in result.stdout


def test_required_release_404_fails_instead_of_false_green():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        server_root = Path(tmp) / "server"
        server_root.mkdir()
        with _serve(server_root) as base_url:
            _write_manifest(
                root,
                f"{base_url}/missing-release",
                "tool.zip",
                "0" * 64,
                ["yt-dlp/yt-dlp.exe"],
            )
            result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "checksum file not found" in result.stdout
        assert "404" in result.stdout


def test_required_release_missing_checksum_entry_fails():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        server_root = Path(tmp) / "server"
        server_root.mkdir()
        (server_root / "SHA256SUMS.txt").write_text(f"{'0' * 64}  another.zip\n", encoding="ascii")
        with _serve(server_root) as base_url:
            _write_manifest(
                root,
                base_url,
                "tool.zip",
                "0" * 64,
                ["yt-dlp/yt-dlp.exe"],
            )
            result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "missing from SHA256SUMS" in result.stdout


def test_required_release_missing_archive_fails_even_when_checksum_lists_it():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        server_root = Path(tmp) / "server"
        server_root.mkdir()
        digest = "0" * 64
        _write_checksums(server_root, {"tool.zip": digest})
        with _serve(server_root) as base_url:
            _write_manifest(
                root,
                base_url,
                "tool.zip",
                digest,
                ["yt-dlp/yt-dlp.exe"],
            )
            result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "release asset not found" in result.stdout


def test_required_release_checksum_drift_fails():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        server_root = Path(tmp) / "server"
        server_root.mkdir()
        _make_zip(server_root / "tool.zip", {"yt-dlp/yt-dlp.exe": b"payload"})
        actual = hashlib.sha256((server_root / "tool.zip").read_bytes()).hexdigest()
        _write_checksums(server_root, {"tool.zip": actual})
        with _serve(server_root) as base_url:
            _write_manifest(
                root,
                base_url,
                "tool.zip",
                "0" * 64,
                ["yt-dlp/yt-dlp.exe"],
            )
            result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "sha256 differs" in result.stdout


def test_required_release_valid_checksums_and_asset_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        server_root = Path(tmp) / "server"
        server_root.mkdir()
        _make_zip(server_root / "tool.zip", {"yt-dlp/yt-dlp.exe": b"payload"})
        digest = hashlib.sha256((server_root / "tool.zip").read_bytes()).hexdigest()
        _write_checksums(server_root, {"tool.zip": digest})
        with _serve(server_root) as base_url:
            _write_manifest(
                root,
                base_url,
                "tool.zip",
                digest,
                ["yt-dlp/yt-dlp.exe"],
            )
            result = _run(root, "--verify-manifest")

        assert result.returncode == 0, result.stdout


def test_verify_manifest_rejects_structurally_invalid_sha256():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        (root / "tools-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "release_required": False,
                    "release_base_url": "https://invalid.invalid/x",
                    "tools": {
                        "bad": {
                            "kind": "zip",
                            "version": "1",
                            "archive": "a.zip",
                            "sha256": "not-a-hash",
                            "license": "X",
                            "upstream": "u",
                            "provides": ["a.exe"],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "invalid sha256" in result.stdout


def test_manifest_rejects_backslash_traversal_on_every_host():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        _write_manifest(
            root,
            "https://invalid.invalid/not-published",
            "tool.zip",
            "0" * 64,
            [r"..\evil.exe"],
            release_required=False,
        )

        result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "backslashes are not allowed" in result.stdout


def test_manifest_rejects_duplicate_archive_names():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        manifest = {
            "schema_version": 1,
            "release_required": False,
            "release_base_url": "https://invalid.invalid/not-published",
            "tools": {
                "one": {
                    "kind": "zip",
                    "version": "1",
                    "archive": "shared.zip",
                    "sha256": "0" * 64,
                    "license": "X",
                    "upstream": "u",
                    "provides": ["one/tool.exe"],
                },
                "two": {
                    "kind": "zip",
                    "version": "1",
                    "archive": "shared.zip",
                    "sha256": "1" * 64,
                    "license": "X",
                    "upstream": "u",
                    "provides": ["two/tool.exe"],
                },
            },
        }
        (root / "tools-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "duplicate archive" in result.stdout


def test_manifest_rejects_duplicate_install_destinations():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        manifest = {
            "schema_version": 1,
            "release_required": False,
            "release_base_url": "https://invalid.invalid/not-published",
            "tools": {
                "one": {
                    "kind": "zip",
                    "version": "1",
                    "archive": "one.zip",
                    "sha256": "0" * 64,
                    "license": "X",
                    "upstream": "u",
                    "provides": ["shared/tool.exe"],
                },
                "two": {
                    "kind": "zip",
                    "version": "1",
                    "archive": "two.zip",
                    "sha256": "1" * 64,
                    "license": "X",
                    "upstream": "u",
                    "provides": ["shared/tool.exe"],
                },
            },
        }
        (root / "tools-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "duplicate destination" in result.stdout


def test_duplicate_declared_member_in_zip_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        source = Path(tmp) / "src"
        source.mkdir()
        archive_path = source / "tool.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("yt-dlp/yt-dlp.exe", b"first")
                archive.writestr("yt-dlp/yt-dlp.exe", b"second")
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        _write_manifest(
            root,
            source.as_uri(),
            "tool.zip",
            digest,
            ["yt-dlp/yt-dlp.exe"],
        )

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 1
        assert "appears multiple times" in result.stdout
        assert not (root / "download-tools" / "yt-dlp" / "yt-dlp.exe").exists()


def test_incomplete_rollback_preserves_backup(monkeypatch, tmp_path):
    module = _load_fetch_module()
    staging_root = tmp_path / "staging"
    target_root = tmp_path / "download-tools"
    member = "tool/tool.exe"
    staged = staging_root / member
    existing = target_root / member
    staged.parent.mkdir(parents=True)
    existing.parent.mkdir(parents=True)
    staged.write_bytes(b"new")
    existing.write_bytes(b"old")

    original_move = module.shutil.move

    def flaky_move(source, destination):
        if ".tool-backup-" in str(source):
            raise OSError("restore blocked")
        return original_move(source, destination)

    def fail_replace(_source, _destination):
        raise OSError("install blocked")

    monkeypatch.setattr(module.shutil, "move", flaky_move)
    monkeypatch.setattr(module.os, "replace", fail_replace)

    with pytest.raises(module.FetchError, match="backup preserved"):
        module._install_staged_files(staging_root, target_root, [member])

    backups = list(tmp_path.glob(".tool-backup-*"))
    assert len(backups) == 1
    assert (backups[0] / member).read_bytes() == b"old"


def _run_manifest_provides_rejection(tmp, provides, *, expect_ok=False):
    """Run --verify-manifest against a manifest whose single zip tool declares
    the given provides list; return the subprocess result."""
    root = _setup_workspace(tmp)
    _write_manifest(
        root,
        "https://invalid.invalid/not-published",
        "tool.zip",
        "0" * 64,
        provides,
        release_required=False,
    )
    return _run(root, "--verify-manifest")


def test_rejects_windows_reserved_device_name():
    result = _run_manifest_provides_rejection(tempfile.mkdtemp(), ["CON/tool.exe"])
    assert result.returncode == 1
    assert "Windows reserved device name" in result.stdout


def test_rejects_reserved_name_with_extension():
    result = _run_manifest_provides_rejection(tempfile.mkdtemp(), ["con.txt/tool.exe"])
    assert result.returncode == 1
    assert "Windows reserved device name" in result.stdout


def test_rejects_trailing_dot():
    result = _run_manifest_provides_rejection(tempfile.mkdtemp(), ["tool./tool.exe"])
    assert result.returncode == 1
    assert "trailing dot or space" in result.stdout


def test_rejects_trailing_space():
    result = _run_manifest_provides_rejection(tempfile.mkdtemp(), ["tool /tool.exe"])
    assert result.returncode == 1
    assert "trailing dot or space" in result.stdout


def test_rejects_del_character():
    result = _run_manifest_provides_rejection(tempfile.mkdtemp(), ["tool\x7f/tool.exe"])
    assert result.returncode == 1
    assert "control characters are not allowed" in result.stdout


def test_rejects_case_insensitive_destination_collision():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        manifest = {
            "schema_version": 1,
            "release_required": False,
            "release_base_url": "https://invalid.invalid/not-published",
            "tools": {
                "one": {
                    "kind": "zip",
                    "version": "1",
                    "archive": "one.zip",
                    "sha256": "0" * 64,
                    "license": "X",
                    "upstream": "u",
                    "provides": ["shared/Tool.Exe"],
                },
                "two": {
                    "kind": "zip",
                    "version": "1",
                    "archive": "two.zip",
                    "sha256": "1" * 64,
                    "license": "X",
                    "upstream": "u",
                    "provides": ["shared/tool.exe"],
                },
            },
        }
        (root / "tools-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "duplicate destination" in result.stdout
        assert "case-insensitive" in result.stdout


def test_accepts_distinct_safe_windows_paths():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        manifest = {
            "schema_version": 1,
            "release_required": False,
            "release_base_url": "https://invalid.invalid/not-published",
            "tools": {
                "one": {
                    "kind": "zip",
                    "version": "1",
                    "archive": "one.zip",
                    "sha256": "0" * 64,
                    "license": "X",
                    "upstream": "u",
                    "provides": ["one/Tool.Exe"],
                },
                "two": {
                    "kind": "zip",
                    "version": "1",
                    "archive": "two.zip",
                    "sha256": "1" * 64,
                    "license": "X",
                    "upstream": "u",
                    "provides": ["two/tool.exe"],
                },
            },
        }
        (root / "tools-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = _run(root, "--verify-manifest")

        assert result.returncode == 0
