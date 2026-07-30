# MediaHarbor — Agent 入口

1. 读取 `skill/mediaharbor/SKILL.md` 了解能力、边界和触发条件。
2. 读取 `download-tools/tools.json` 了解可用下载工具及其角色。
3. 使用 `python skill/mediaharbor/scripts/locate_root.py` 定位 MediaHarbor 根目录。
4. 首次使用时，脚本会在根目录自动创建 `output/`；所有素材产物写入 `output/<project-name>/`。
5. 使用 `python skill/mediaharbor/scripts/check_tools.py --json` 检查工具就绪状态。
6. 默认搜索 Harness 优先搜索 Bilibili 和 YouTube 的公开页面；这不是下载内核的强制域名白名单。
7. 对正常支持的公开页面，Agent 可以自动提交和下载候选 URL，不要求逐条人工确认。
8. 其他来源只有在 `routing.json`、backend 和本地工具明确支持时才应提交。
9. 人工审核用于判断素材相关性、质量、版权适用性和最终剪辑，不是每次下载前的安全审批门禁。
10. MediaHarbor 仅按本地单用户信任模型运行；不得将其暴露为公共任意 URL 下载 API，也不得接受不可信多用户任务。
11. **不得修改 `download-tools/` 中的任何文件或二进制。**
12. **不得保存凭据** — 不创建或保留 `cookies.txt`、`auth.toml`、`.env` 等文件。
13. **不得绕过 DRM 或访问控制** — 遇到付费、登录或区域限制时停止并返回结构化状态。
