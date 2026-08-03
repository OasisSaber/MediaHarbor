#!/usr/bin/env bash
# CI 专用验证入口（供 .github/workflows/check.yml 的 aw-check job 使用）：
# 中央可重用工作流不负责安装调用方项目依赖（见 TheMasterplan
# docs/actions-interface.md 职责边界），因此先在 CI runner 上安装本项目
# 验证依赖（pytest、ruff），再调用权威验证入口 scripts/validate.sh。
#
# 本地开发直接运行 `bash scripts/validate.sh`（本地环境已具备依赖）。
set -euo pipefail

python -m pip install --disable-pip-version-check --quiet pytest ruff

bash scripts/validate.sh
