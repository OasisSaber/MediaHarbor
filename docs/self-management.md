# Untitled 自管手册（Self-Management）

> 本文件是 Untitled 工作区的运维交接与自管说明，2026-08-16 由 DSH 接管时建立，
> 与 TTS / Ollama / AirLLM / WSL 工作区同范式：README.md（项目手册）+
> AGENTS.md（治理规则）+ manage 脚本（日常运维）。
> 本文件是辅助材料，**不覆盖** 根 `AGENTS.md`、`core/`、`profiles/`、`adapters/`
> 的权威规则，也不覆盖 `README.md` 与 `AGENT_READ_ME_FIRST.md` 的内容。

## 一、这是什么

- 项目：**Untitled**（远端 OasisSaber/Untitled，2026-08-12 由 MediaHarbor 改名）。
- 定位：本地、单用户、Windows x64 优先的 Agent Skill 源码仓库 —— 根据已有文案
  检索、下载、验证、整理视频素材（mediaharbor 工作流）。
- 技术栈：Python 3.11+（`untitled.py` 是稳定 Agent 入口）、外部下载工具 CLI、
  FFmpeg/ffprobe、JSON/JSONL、Markdown。无构建/安装步骤，克隆即用。
- 验证入口：`bash scripts/validate.sh`（权威）与 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate.ps1`（Windows 等价入口）。
- 发布候选另需 `scripts/cold_start_smoke.ps1`（干净 Windows x64 冷启动）。

## 二、日常运维（manage.ps1）

统一入口：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/manage.ps1 <command>`

| 命令 | 作用 |
|---|---|
| `status` | git 分支/工作树/远端 + 工具就绪摘要 |
| `validate` | 跑权威验证 `scripts/validate.ps1`（Ruff format/lint + pytest + 冒烟） |
| `check-tools` | `python untitled.py check-tools` 工具就绪明细 |
| `projects` | 列出 `output/` 下项目，区分真实项目与测试残留 |
| `disk` | 仓库磁盘占用摘要（output / migration-backups / download-tools / .venv） |
| `help` | 用法 |

脚本输出为 ASCII（防 GBK 乱码），PS 5.1 兼容。任何 push / PR 前必须跑
`manage.ps1 validate`（即权威验证），失败时修正重跑，不得把失败表述为成功。

## 三、治理与协作（必须遵守）

- 工作流来源：**TheMasterplan**（GitHub Flow）。当前 `main` 为 v3.0.0 采用集；
  PR #70 将同步到 v4.0.0（新增治理所有权预检、PR CI 通过门、薄 Harness 边界），
  合并后以 v4.0.0 为准。采用集为根 `AGENTS.md` 与 `core/`、`profiles/`、
  `adapters/`。规则权威顺序见根 `AGENTS.md`。
- VCS：**Git Profile**（`profiles/git.md`），`profiles/jj.md` 未采用（`.jj/`
  目录存在但不用 jj 命令）。
- 合并方式：**只接受人类决定的 Squash Merge**；Agent 不得自行 merge /
  release / 强推 / 删除远端资源。发布走 `core/policy.md` 聚合授权 +
  `profiles/git.md` tag-only 流程（tag → smoke → Release）。
- 任务路径：复杂任务用 GitHub Issue + 任务分支 + PR；小型低风险任务可用
  当前会话明确授权，但 PR 必须记录授权来源与范围（`core/workflow.md` §1）。
- 工作区卫生：不提交密钥/本机绝对路径/缓存/临时文件；`output/`、
  `migration-backups/`、`download-tools/*/`（工具二进制）、`.venv/`、
  `.pytest_cache/` 等已被 `.gitignore` 忽略，不得强行提交。

## 四、工具与素材

- 工具清单：`tools-manifest.json`（发布契约，含 SHA-256）+
  `download-tools/tools.json`（实际配置）+ `download-tools/routing.json`（路由）。
- ZIP 工具：yt-dlp、ffmpeg、N_m3u8DL-RE —— 由 `scripts/fetch_tools.py` 从
  GitHub Release 下载校验，已就位在 `download-tools/`（ffmpeg 216MB /
  N_m3u8DL-RE 13MB / yt-dlp 17MB，2026-08-16 核查）。
- pip 工具：yutto 2.2.0、streamlink 8.4.0、gallery-dl 1.32.8 —— 装在系统
  Python（gallery-dl 当前解析到 pythoncore-3.14）或运行解释器。
- **`download-tools/` 下的文件与二进制不得修改**（AGENT_READ_ME_FIRST.md 第 8 条）。
- 工具更新流程见 `docs/tool-update-process.md`（含上游更新检查
  `fetch_tools.py --check-updates`）；发布检查清单见 `docs/release-readiness-plan.md`。

## 五、产物与报告

- 所有素材产物写入 `output/<project-name>/`；报告在
  `output/<project-name>/reports/`（`COVERAGE_REPORT.md`、
  `HUMAN_EDITOR_HANDOFF.md`）。
- `output/` 全部 gitignored；`output/` 下大量 `*-test` / `tmp*` 目录是历史测试
  残留，可清理（用 `manage.ps1 projects` 区分，清理不进入 git）。
- 冷启动冒烟报告默认写入 gitignored 的 `migration-backups/`，不得提交机器相关报告。

## 六、本机环境注意事项（Windows）

- 本机 git https 到 GitHub 可能报 `schannel SEC_E_NO_CREDENTIALS`（与凭据状态
  相关）；失败时改用 `gh` CLI（正常）或检查 credential helper，不要反复重试 git。
- 平台只正式支持 Windows x64；Ubuntu GitHub Actions（`scripts/ci-check.sh`）仅
  表示纯 Python 测试可运行，不是 Linux 支持声明。
- CI 消费者：`.github/workflows/check.yml` 的 `themasterplan-check` job 经
  `OasisSaber/TheMasterplan/.github/workflows/themasterplan-check.yml@v4.0.0`
  调用（`policy-ref: v4.0.0`，固定版本调用，uses 引用版本与 policy-ref 一致），
  `project-check-path` = `scripts/ci-check.sh`。

## 七、接管基线（2026-08-16）

- 当前 `main` = `96f3641`（docs: mark release readiness plan complete，RC approved 2026-08-15）。
- PR #70（docs/adoption-sync-v4 → main）待人类合并：v4.0.0 采用集同步。
- 工具就绪：check-tools 全部存在，yt-dlp/ffmpeg/N_m3u8DL-RE 已下载校验。
- 验证基线：接管时 `scripts/validate.ps1` 全项通过（记录见
  `output/manage-validate-baseline.log`，gitignored）。
