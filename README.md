# Untitled

Untitled 是一个本地、单用户、Windows x64 优先的 Agent Skill 源码仓库，用于根据已有文案检索、下载、验证和整理视频素材。

## 项目定位

- 当前只正式支持 **Windows x64**。
- 运行要求：**Python 3.11+**，以及 `download-tools/tools.json` 和 `tools-manifest.json` 声明的本地第三方工具。
- 部署方式：克隆完整仓库即可；Untitled 本身不需要构建或安装为 Python 包。
- 信任边界：面向操作者控制的本地单用户工作区，不是公共任意 URL 下载服务。

## 冷启动部署

在干净仓库中依次执行：

```powershell
python scripts/fetch_tools.py --verify-manifest
python scripts/fetch_tools.py
python untitled.py check-tools
```

`--verify-manifest` 是发布门，而不是尽力而为的检查。当 `release_required` 为 `true` 时，以下任一情况都会失败：

- `SHA256SUMS.txt` 不存在。
- GitHub Release 或网络请求失败。
- 声明的 ZIP 资产不存在。
- Published SHA-256 与 Manifest 不一致。

没有官方独立 Windows 二进制的工具，需要显式安装到运行 Untitled 的同一个 Python 解释器：

```powershell
python -m pip install yutto streamlink gallery-dl
python untitled.py check-tools
```

稳定的 Agent 面向入口是：

```powershell
python untitled.py
```

`skill/untitled/scripts/` 下的脚本属于内部实现与兼容入口，不是稳定公共 API。

## Agent 入口

1. 阅读 [`AGENT_READ_ME_FIRST.md`](AGENT_READ_ME_FIRST.md)。
2. 阅读 [`skill/untitled/SKILL.md`](skill/untitled/SKILL.md)，它是权威 Skill 契约。
3. 修改工具或路由行为前，阅读 `download-tools/tools.json` 和 `download-tools/routing.json`。

## 主要命令

- `python untitled.py check-tools`
- `python untitled.py project-create <name>`
- `python untitled.py story-node-add <project> <title>`
- `python untitled.py story-node-list <project>`
- `python untitled.py candidate-add <project> <url>`
- `python untitled.py process <project>`
- `python untitled.py status <project>`
- `python untitled.py run --project <name> --url <url>`

CLI 固定返回顶层 JSON 字段：`ok`、`status`、`data`、`error`。

## 验证

```bash
python -m ruff format --check .
python -m ruff check .
python -m pytest tests/ -q
bash scripts/validate.sh
```

Windows 等价入口：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
```

发布候选还必须通过干净 Windows x64 冷启动：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/cold_start_smoke.ps1
```

默认报告写入已被忽略的 `migration-backups/cold-start-smoke-report.json`，不得提交机器相关报告或下载后的工具文件。

## 主要限制

- Linux 和 macOS 不属于正式支持平台。
- 搜索由 Agent 完成，Untitled 没有内置搜索引擎。
- 视觉污染检查是启发式分析，不是视频语义理解。
- 不保存凭据，不绕过 DRM、付费墙、登录、区域或访问限制。
- 下载成功不代表素材适合剪辑，也不代表具备发布许可。
- 不要让多个写进程并发操作同一个项目。

## 仓库更名状态

源码身份已经是 Untitled。GitHub 仓库名称和 Release 迁移属于单独的人类授权操作。在远端仓库真正改名之前，`tools-manifest.json` 必须指向当前真实存在的仓库，不能提前指向未来地址，也不能把 GitHub 旧地址重定向当作长期配置。

## License

This project is licensed under the [MIT License](LICENSE).

### Release integrity hardening

The release manifest is treated as an installation contract, not only documentation.
The fetcher rejects cross-tool archive or destination collisions, host-dependent path
forms, duplicate ZIP members, missing assets, and checksum drift. Tool installation is
staged and rollback-aware; an incomplete rollback preserves the backup location for
manual recovery.
