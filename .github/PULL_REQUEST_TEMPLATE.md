## Linked Issue

- Issue:

## Scope

-

## Acceptance Criteria

- [ ]

## Local Validation

```text
# Backend
.venv/bin/pytest -q
.venv/bin/ruff check server worker shared tests alembic
.venv/bin/mypy server worker shared tests
git diff --check

# Frontend, when touched
npm run lint
npm run typecheck
npm run test
npm run build
```

## Review Notes

-

## Gemini Review Focus

- 请判断该 PR 是否完成 Linked Issue。
- 请重点检查正确性、安全性、数据一致性、API 契约、测试质量和架构边界。
- 请指出做得好的地方，也请明确批改需要修复的问题。
