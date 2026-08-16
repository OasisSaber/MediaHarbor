# BagItUp Release Readiness Plan

> **状态：全部阶段已完成（2026-08-15）。**
> Phase 1 → #64/#65 合并；Phase 2 → 独立评审（READY TO MERGE）；Phase 3 → 人类决定 Squash Merge；
> Phase 4 → 2026-08-12 仓库改名 OasisSaber/MediaHarbor → OasisSaber/Untitled；Phase 5 → PR #68 direct URL；
> Phase 6 → Release 身份更新（title/body → Untitled，资产/digest 不变）+ post-rename fresh cold-start PASS
> + 真实公开样本 E2E PASS + 最终 RC 聚合 PASS（release_candidate: true）+ 独立评审 APPROVE。
> 本文件保留为流程记录，不再表示进行中的发布状态。

## Purpose

Move Untitled from a source-migrated experimental build to a Windows x64 release candidate without combining code fixes, GitHub repository rename, and Release publication into one irreversible operation.

## Phase 1: Code and Documentation PR

Apply the payload in this asset pack on a feature branch.

Scope:

- Restore `tools-manifest.json` to the current real GitHub repository URL.
- Add explicit `release_required` semantics.
- Make published Release verification fail on 404, network errors, missing checksums, missing assets, or hash drift.
- Stage and install ZIP tool files transactionally.
- Add local Release asset preparation and Windows cold-start scripts.
- Replace stale or corrupted authoritative Skill documentation.
- Update README and tool-release documentation.

Quality gate:

```bash
python -m ruff format --check .
python -m ruff check .
python -m pytest tests/ -q
bash scripts/validate.sh
python scripts/fetch_tools.py --verify-manifest
```

Windows gate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
powershell -ExecutionPolicy Bypass -File scripts/cold_start_smoke.ps1
```

Do not rename the GitHub repository or modify Releases in this phase.

## Phase 2: Independent Review

Run an independent Code Review over the complete diff. Reject the PR if any merge-blocking finding remains in:

- Release availability verification.
- Checksum or ZIP path validation.
- Partial installation rollback.
- Credential or URL leakage.
- Test environment coupling.
- Documentation claims that disagree with code.

## Phase 3: Human Merge Decision

Create a Draft PR by default. The human decides whether and when to Squash Merge. A green CI result is necessary but not sufficient.

## Phase 4: Remote Repository Rename

After Phase 1 is merged and cold-start verification passes, obtain separate authorization to rename:

```text
OasisSaber/MediaHarbor -> OasisSaber/Untitled
```

Record before and after states for:

- Default branch.
- Rulesets and required checks.
- Workflow permissions.
- Merge methods.
- Issues and Pull Requests.
- Releases and assets.
- Repository visibility.

## Phase 5: Direct URL Update

After the remote rename succeeds, update `tools-manifest.json` to the new direct URL. Search for old repository paths and retain them only in migration history.

Do not accept old-URL redirect behavior as the final verification.

## Phase 6: Release Verification

Verify or rebuild `tools-windows-x64-v1` with separately authorized human release actions. Run:

```powershell
python scripts/fetch_tools.py --verify-manifest
python scripts/fetch_tools.py
python bagitup.py check-tools
powershell -ExecutionPolicy Bypass -File scripts/cold_start_smoke.ps1
```

## Completion Definition

BagItUp is a release candidate only when:

- Source, documentation, repository, and Release identity are consistent.
- Strict Manifest verification passes against the direct new URL.
- A clean Windows x64 checkout completes cold start.
- Full tests and CI pass.
- A real public-sample end-to-end acquisition succeeds.
- Independent Code Review returns APPROVE with no merge-blocking findings.

## Additional code-review gates

- Verify path validation behaves identically on Linux CI and Windows runtime.
- Reject duplicate archive names and duplicate installation destinations across tools.
- Reject duplicate declared members inside a ZIP, even when the byte contents match.
- Simulate a failed installation followed by a failed restore and confirm the backup
  directory remains available and is named in the error output.
