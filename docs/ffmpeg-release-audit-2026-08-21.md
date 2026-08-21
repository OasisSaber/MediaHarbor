# FFmpeg Release 实物核验（2026-08-21）

## 结论

`tools-windows-x64-v1` 中的 FFmpeg 压缩包完整性和可执行文件身份核验通过，
但许可证与可再现来源材料未闭环。因此本次核验状态为：**完整性通过，许可证发布门阻断**。

本记录只描述已发布实物和仓库清单，不授权删除、替换或重新发布 GitHub Release。

## 核验对象

- Release：`tools-windows-x64-v1`
- 资产：`ffmpeg-n8.1.2-win64-lgpl.zip`
- 公开下载地址：<https://github.com/OasisSaber/BagItUp/releases/download/tools-windows-x64-v1/ffmpeg-n8.1.2-win64-lgpl.zip>
- 清单路径：[`tools-manifest.json`](../tools-manifest.json)
- 上游构建仓库：<https://github.com/BtbN/FFmpeg-Builds>

## 实物证据

| 检查项 | 结果 |
|---|---|
| HTTP 下载 | `200 OK`，`96,767,503` bytes |
| ZIP SHA-256 | `411340f90a794dcfdd52e8228f4ecc34c052edc1766d27c84adff1c0446d68bf`；与清单一致 |
| 压缩包成员 | `ffmpeg/ffmpeg.exe`、`ffmpeg/ffprobe.exe`、`ffmpeg/LICENSE.txt` |
| `ffmpeg.exe -version` | `n8.1.2-34-g9b6c8969e0-20260731`，退出码 0 |
| `ffprobe.exe -version` | `n8.1.2-34-g9b6c8969e0-20260731`，退出码 0 |
| 构建配置 | 含 `--enable-version3`，未见 `--enable-gpl` |
| 包内许可证文本 | GNU Lesser General Public License v3，7,651 bytes |

解压后文件 SHA-256：

```text
ffmpeg.exe  6099366f31293cdc6c283ea44ffb32f07e3139cd0caf6d0db652a7d064d089cb
ffprobe.exe 4c2f730969c9551aec21c5ca07eb73f63bb0920204c9cd6c9a6e7be6be0458d2
LICENSE.txt da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768
```

FFmpeg 官方许可证说明指出，`--enable-version3` 会把 FFmpeg 的 (L)GPL
升级到 v3；BtbN 的 `lgpl` 变体只表示排除 GPL-only 库，并不把该实物降回
LGPL 2.1。参见 [FFmpeg License](https://ffmpeg.org/doxygen/7.0/md_LICENSE.html)
和 [BtbN FFmpeg-Builds README](https://github.com/BtbN/FFmpeg-Builds)。

## 缺口与后续门槛

当前 Release 资产只携带二进制和一份许可证文本，没有：

1. 对应 FFmpeg 源码快照或可核验的完整源码链接；
2. BtbN 构建仓库 commit、构建脚本版本或完整构建记录；
3. `SOURCE-OFFER.md` 等源码获取说明；
4. 针对构建中启用组件的逐项许可证/第三方通知。

因此，不能仅凭 SHA 命中就宣称 FFmpeg 的 LGPL 发布材料已经闭环。重新发布前应：

1. 固定并记录 FFmpeg 源码 commit `9b6c8969e05b4f0b29f0f85cd501be6b3e582e6b`，以及对应的 BtbN 构建来源；
2. 在 Release 资产或同一 Release 中提供源码快照/源码获取说明、构建配置和适用通知；
3. 以新资产生成新的 `SHA256SUMS.txt`，重新进行冷下载、解压和版本核验；
4. 由有权限的发布者按仓库发布门重新授权后，再替换或新增 Release 资产。

本地清单和第三方告知已按当前实物证据改为 `LGPL-3.0-or-later`；这不替代上述
源码与构建来源闭环，也不改变既有远程 Release 的内容。

远端 Release 说明仍写着 `LGPL-2.1+`，因此在下一次获得发布授权前，远端说明与
本地清单会暂时不一致；本地修改不能被当作已完成的远端发布修复。

