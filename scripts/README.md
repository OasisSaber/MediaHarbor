# Validation

`scripts/validate.sh` 只执行四项技术检查：

1. Markdown 内部链接；
2. Shell 脚本提交模式；
3. YAML 语法；
4. Shell 语法。`validate_pr_body.py` 仅使用 Python 标准库校验 Pull Request 正文的固定模板字段；CI 仅在 Pull Request 事件中运行它。

运行环境需要 Bash、Git、Python 和 PyYAML。持续集成使用 Python 3.12.7 与 PyYAML 6.0.3。

```bash
bash scripts/validate.sh
```

缺少 Python 或 PyYAML 时，验证会明确失败。
