# BagItUp — Agent 入口

1. 读取 `skill/bagitup/SKILL.md`（唯一权威 Skill 文档）：触发条件、工作流、工具检查、状态码、安全边界与失败处理。
2. 读取 `download-tools/tools.json` 与 `download-tools/routing.json`，了解可用工具及其路由。
3. 首次使用先运行 `python scripts/fetch_tools.py` 从项目 Release 获取已验证工具（sha256 校验后解压到 `download-tools/`）；`--check` 查看状态、`--check-updates` 查询上游新版本。无官方独立 Windows 二进制的工具（yutto / streamlink / gallery-dl）按脚本指引 pip 安装。
4. 使用 `python skill/bagitup/scripts/locate_root.py` 定位 BagItUp 根目录；首次使用脚本会自动创建 `output/`。
5. 使用 `python skill/bagitup/scripts/check_tools.py --json` 检查工具就绪状态（`READY` / `DEGRADED`），缺失必备工具时停止并说明。
6. 所有素材产物写入 `output/<project-name>/`；报告位于 `output/<project-name>/reports/`（`COVERAGE_REPORT.md`、`HUMAN_EDITOR_HANDOFF.md`）。
7. 当前只正式支持 Windows x64；Ubuntu CI 仅表示纯 Python 测试可运行。
8. **不得修改 `download-tools/` 中的任何文件或二进制。**
9. **不得保存凭据** — 不创建或保留 `cookies.txt`、`auth.toml`、`.env` 等文件。
10. **不得绕过 DRM 或访问控制** — 遇到付费、登录或区域限制时停止并返回结构化状态（`DRM_DETECTED` / `AUTH_REQUIRED` / `GEO_RESTRICTED`）。
11. 本地单用户信任模型：默认搜索 Bilibili 和 YouTube 公开页面（非强制域名白名单）；正常支持的公开页面可无人值守下载；人工审核负责素材相关性、质量、版权与最终剪辑。
