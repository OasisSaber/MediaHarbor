# GitHub 仓库设置

GitHub Template Repository 只复制仓库文件，不能保证这些服务器端设置被复制。每次从模板创建仓库后，必须由人类检查并配置：

- `main` 只能通过 Pull Request 修改，并要求 `Check` 状态检查通过。
- 禁止 force push 和删除 `main`。
- 尽可能禁止管理员、GitHub App 和自动化绕过规则。
- 只启用 Squash Merge，并禁用 auto-merge。
- Agent 凭据不得拥有 admin、merge 或 release 权限。

仓库文件中的规则不能替代 GitHub 服务器端保护；这些设置不由本模板自动配置。