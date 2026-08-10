# Smart Commit Backend

团队代码提交记录与成员工作量管理后端服务。

## 📹 演示视频

### API 功能演示

[<img src="https://cdn.loom.com/sessions/thumbnails/c3a45b73ab5b47c3a5944cc103d3cc39-with-play.gif" width="600">](https://www.loom.com/share/c3a45b73ab5b47c3a5944cc103d3cc39)

### 阶段 E 功能演示

[<img src="https://cdn.loom.com/sessions/thumbnails/653628f29c7641a3aa463a2c539f1b79-with-play.gif" width="600">](https://www.loom.com/share/653628f29c7641a3aa463a2c539f1b79)

### MCP 直连数据库演示（S8）

演示 AI 通过 MCP 只读账号直连 PostgreSQL，用自然语言回答三个数据问题：

1. **每个团队有多少成员？** — 关联 `teams` 和 `team_members` 表
2. **谁的提交最多？** — 关联 `commits` 和 `users` 表，按提交数降序排列
3. **每个仓库有多少条提交？** — 关联 `repos` 和 `commits` 表

运行演示脚本（使用 MCP 只读账号 `sch_ro`）：

```bash
# 确保只读账号已配置
python scripts/setup_readonly.py

# 运行三个演示查询
python scripts/demo_queries.py

# 验证只读账号无法写入
python scripts/test_readonly.py
```

预期输出：

```
=== Q1: 每个团队有多少成员？ ===
  Davis and Sons: 10 人
  Doyle Ltd: 7 人
  Mcclain, Miller and Henderson: 5 人
  Rodriguez, Figueroa and Sanchez: 8 人

=== Q2: 谁的提交最多？（Top 5） ===
  Rhonda Lee (@dshields): 5 条提交
  Tracie Nelson (@marcus31): 5 条提交
  Gregory Jones (@cheryl80): 5 条提交
  Melissa Marshall (@jcontreras): 5 条提交
  Cynthia Rogers (@jasminebrown): 4 条提交

=== Q3: 每个仓库有多少条提交？ ===
  bed-far: 7 条提交
  doctor-Mr: 11 条提交
  ...

[OK] MCP read-only account query succeeded - all 3 questions answered.
```

只读权限验证：`[OK] INSERT blocked: insufficient privilege`

## 快速开始（5 分钟跑起来）

### 1. 环境要求

- Python >= 3.12
- pip（或你喜欢的包管理器）

### 2. 安装依赖

```bash
# 克隆项目后进入目录
cd smart-commit-helper-backend

# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS / Linux

# 安装运行依赖 + 开发依赖
pip install -e ".[dev]"
```

### 3. 启动服务

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动成功后访问：

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8000/docs | Swagger UI 交互式 API 文档 |
| http://127.0.0.1:8000/redoc | ReDoc 文档 |
| http://127.0.0.1:8000/health | 健康检查 |

### 4. 运行测试

```bash
pytest
```

预期输出：`42 passed`，覆盖率 ≥ 70%。

### 5. 代码检查

```bash
ruff check .    # 代码风格检查
mypy app         # 类型检查
```

---

## API 概览

所有接口前缀：`/api/v1`

### 通用请求头

| Header | 说明 | 示例 |
|--------|------|------|
| `X-Team-Id` | 团队 ID（多租户隔离） | `team-alpha` |
| `X-User-Role` | 请求者角色（权限控制） | `admin` / `developer` / `viewer` |

> 不传 `X-User-Role` 默认为 `viewer`。

### 通用响应头

| Header | 说明 |
|--------|------|
| `X-Trace-Id` | 链路追踪 ID，错误排查时使用 |

### 错误格式（RFC 7807）

```json
{
  "type": "https://httpstatuses.com/404",
  "title": "Not Found",
  "status": 404,
  "detail": "查无此人",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 接口列表

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 服务健康状态 |

### 成员管理（Members）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/api/v1/members` | admin | 创建成员 |
| GET | `/api/v1/members` | 所有角色 | 成员列表（分页+筛选） |
| GET | `/api/v1/members/{member_id}` | 所有角色 | 成员详情 |
| PUT | `/api/v1/members/{member_id}` | admin | 更新成员 |
| DELETE | `/api/v1/members/{member_id}` | admin | 删除成员 |

**查询参数（列表）：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int ≥ 1 | 1 | 页码 |
| `page_size` | int 1-100 | 20 | 每页条数 |
| `role` | string | - | 按角色筛选（admin/developer/viewer） |
| `name` | string | - | 按姓名模糊搜索 |

### 提交记录（Commits）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/v1/commits` | 所有角色 | 提交列表（分页+筛选） |
| GET | `/api/v1/commits/{commit_id}` | 所有角色 | 提交详情 |
| GET | `/api/v1/commits/workload/{member_id}` | 所有角色 | 成员工作量统计 |

**查询参数（列表）：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int ≥ 1 | 1 | 页码 |
| `page_size` | int 1-100 | 20 | 每页条数 |
| `member_id` | string | - | 按成员筛选 |
| `repository` | string | - | 按仓库名筛选（模糊匹配） |
| `start_date` | ISO 8601 | - | 起始时间 |
| `end_date` | ISO 8601 | - | 截止时间 |

**查询参数（工作量）：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `start_date` | ISO 8601 | 统计起始时间 |
| `end_date` | ISO 8601 | 统计截止时间 |

---

## 快速验证（curl 示例）

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 查看成员列表（team-alpha，admin 角色）
curl -H "X-Team-Id: team-alpha" -H "X-User-Role: admin" \
  http://127.0.0.1:8000/api/v1/members

# 查看提交记录
curl -H "X-Team-Id: team-alpha" -H "X-User-Role: admin" \
  http://127.0.0.1:8000/api/v1/commits

# 创建成员（需要 admin 权限）
curl -X POST -H "X-Team-Id: team-alpha" -H "X-User-Role: admin" \
  -H "Content-Type: application/json" \
  -d '{"name":"张三","email":"zhangsan@example.com","role":"developer"}' \
  http://127.0.0.1:8000/api/v1/members
```

---

## 项目结构

```
app/
├── __init__.py
├── main.py              # FastAPI 应用入口、异常处理器
├── config.py            # 应用配置
├── database.py          # 内存数据存储 + 种子数据
├── exceptions/          # 自定义异常类
│   └── __init__.py
├── middleware/          # 请求日志 + Trace ID 中间件
│   └── __init__.py
├── models/              # 领域模型（dataclass）
│   ├── member.py
│   └── commit.py
├── routes/              # API 路由层
│   ├── members.py
│   └── commits.py
├── schemas/             # Pydantic 请求/响应模型
│   ├── common.py
│   ├── member.py
│   └── commit.py
└── services/            # 业务逻辑层
    ├── member_service.py
    └── commit_service.py

tests/                   # pytest 测试（42 个用例，覆盖率 94%+）
├── conftest.py
├── test_health.py
├── test_members.py
└── test_commits.py

bruno/                   # Bruno API 调试集合
└── bruno.json
```

---

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.115+ |
| ASGI 服务器 | Uvicorn |
| 数据校验 | Pydantic v2 |
| 测试框架 | pytest + httpx + anyio |
| 代码检查 | ruff / mypy（strict 模式） |
| 数据存储 | 内存存储（开发阶段） |

---

## 多租户说明

- 所有数据通过 `X-Team-Id` 请求头隔离，不同团队数据完全不可见。
- 内置两个测试团队：`team-alpha`、`team-beta`，各有 4 名成员和若干提交记录。
- 角色权限：`admin`（全部操作）、`developer`（只读）、`viewer`（只读）。