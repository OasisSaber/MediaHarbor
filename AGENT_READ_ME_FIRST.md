# MediaHarbor — Agent 入口

1. 读取 `skill/mediaharbor/SKILL.md` 了解能力、边界和触发条件。
2. 读取 `download-tools/tools.json` 了解可用下载工具及其角色。
3. 使用 `python skill/mediaharbor/scripts/locate_root.py` 定位 MediaHarbor 根目录。
4. 首次使用时，脚本会在根目录自动创建 `output/`；所有素材产物写入 `output/<project-name>/`。
5. 使用 `python skill/mediaharbor/scripts/check_tools.py --json` 检查工具就绪状态。
6. **不得修改 `download-tools/` 中的任何文件或二进制。**
7. **不得保存凭据** — 不创建或保留 `cookies.txt`、`auth.toml`、`.env` 等文件。
8. **不得绕过 DRM 或访问控制** — 遇到付费、登录或区域限制时停止并返回结构化状态。
