# CLAUDE14.md — Smart Commit Helper 容器化与工程化护栏

> 本文件是 Smart Commit Helper 后端**容器化、CV 推理服务、Hooks 护栏、质量门禁与类型同步**部分的"宪法"，所有相关开发必须遵守。每个阶段的指令可直接复制给 AI 执行。

---

## 1. 项目概述

### 1.1 项目名称
Smart Commit Helper SaaS — 容器化与工程化护栏（Day 14）

### 1.2 项目背景
本项目是 Smart Commit Helper 后端的工程化升级部分。当前代码只能在开发者本机运行，换台电脑或交给队友需要花半小时装环境、装依赖、配数据库；AI 写代码缺乏强制把关，可能藏有硬编码密钥、测试缺失、格式不统一等隐患；后端接口改了前端类型不同步，导致联调事故。

本项目要解决三个核心问题：
1. **环境一致性**：把后端打包成 Docker 镜像，新人 30 秒内拉起全套环境。
2. **AI 行为治理**：用 Hooks 在 AI 工具调用前后设卡，拦截危险操作和不规范代码。
3. **质量门禁**：测试覆盖率达标、前后端类型自动同步，不守规矩不让过。

### 1.3 前置依赖
在开始 Day 14 之前，必须确认以下内容已就绪：

| # | 依赖项 | 检查位置 | 要求 |
|---|--------|----------|------|
| 1 | Day 11 的 8 个接口代码 | `app/routes/` | 所有接口文件存在且能正常启动 |
| 2 | Day 12 的数据库 + MCP 配置 | `app/db/models/`、`alembic/`、`.mcp.json` | 7 张表模型、Migration 脚本、MCP 配置 |
| 3 | Day 13 的安全认证代码 | `app/core/security.py`、`app/routes/auth.py`、`app/dependencies/` | JWT 认证 + bcrypt 密码 + RBAC 权限中间件 |
| 4 | pytest 测试文件 | `tests/` | 至少覆盖 8 个接口核心流程，能跑通 |
| 5 | 服务能正常启动 | 本机运行 | `uvicorn app.main:app` 能起来，`/docs` 能访问 |

> 如果缺少测试文件，先补写 Day 11 八个接口的测试（至少覆盖正常流程和常见报错），跑通后再继续 Day 14。

### 1.4 具体目标
1. **Docker 镜像打包**：用多阶段构建把后端代码打包成 ≤200MB 的精简镜像。
2. **一键启动全套环境**：用 docker-compose 同时启动 API + PostgreSQL + Redis，新人 30 秒拉起。
3. **CV 推理服务容器化**：ONNX CPU 推理，带模型预热和健康检查，镜像 ≤500MB。
4. **5+ Hooks 护栏**：PreToolUse 拦截危险操作和密钥硬编码，PostToolUse 自动格式化和 Lint，Stop 钩子强制跑测试。
5. **质量门禁 + 类型同步**：pytest + httpx 覆盖率 70%+，OpenAPI 自动生成前端 TypeScript 类型。

### 1.5 核心交付物（6 个阶段）

| 阶段 | 交付物 | 验收标准 | 限时 |
|------|--------|----------|------|
| A | Dockerfile + .dockerignore | 镜像 ≤200MB，多阶段构建，非 root 用户运行 | 50 分钟 |
| B | docker-compose.yml | `docker-compose up -d` 30 秒内拉起 API+PG+Redis，三容器均 Up | 30 分钟 |
| C | CV 推理服务容器 | ONNX CPU 推理，模型预热 + 健康检查，镜像 ≤500MB | 30 分钟 |
| D | 5+ Hooks 护栏 | `.claude/settings.json` + `.claude/hooks/` 脚本，Pre/Post/Stop 钩子全部生效 | 35 分钟 |
| E | 质量门禁 + OpenAPI 类型同步 | pytest 覆盖率 70%+，openapi-typescript 生成前端 TS 类型 | 20 分钟 |
| F | 90 秒演示视频 | 完整展示 4 个场景：容器启动、/docs、类型同步、Hook 拦截 | 20 分钟 |

---

## 2. 技术栈约束

| # | 约束 | 硬性要求 |
|---|------|----------|
| 1 | 后端基础镜像 | **`python:3.12-slim`**，禁止用 `python:3.12`（太大） |
| 2 | 数据库镜像 | **`postgres:16-alpine`**（轻量版） |
| 3 | 缓存镜像 | **`redis:7-alpine`**（轻量版） |
| 4 | CV 推理 | **ONNX Runtime (CPU)**，镜像 ≤500MB |
| 5 | Hook 脚本语言 | **JavaScript / Shell**，放在 `.claude/hooks/` 目录 |
| 6 | Hook 输出 | **必须用 `console.error`（stderr）**，禁止 `console.log`（会污染 stdio 协议） |
| 7 | OpenAPI 工具 | **`openapi-typescript`**，从 `/openapi.json` 生成前端 TS 类型 |
| 8 | 测试框架 | **pytest + httpx**，覆盖率 ≥70%（`pyproject.toml` 已配置 `--cov-fail-under=70`） |
| 9 | 代码格式化 | **ruff format** |
| 10 | Lint | **ruff check** |
| 11 | 容器运行用户 | **非 root 用户**（如 `appuser`），生产环境强制 |
| 12 | 镜像大小 | 后端镜像 **≤200MB**，CV 镜像 **≤500MB** |

---

## 3. 代码规范

### 3.1 Docker 规范
1. **必须多阶段构建**：builder 阶段装依赖和编译，runtime 阶段只复制运行需要的文件。
2. **缓存优化**：先复制 `pyproject.toml`（依赖声明）装依赖，再复制业务代码，改代码不重装依赖。
3. **非 root 运行**：在 runtime 阶段创建普通用户（如 `appuser`），`USER appuser`。
4. **必须写 `.dockerignore`**：排除 `.git`、`venv`、`__pycache__`、`tests`、`.env`、`*.md` 等。
5. **健康检查**：Dockerfile 中配置 `HEALTHCHECK`，docker-compose 中配置 `healthcheck`。
6. **端口暴露**：显式 `EXPOSE 8000`。
7. **镜像大小 ≤200MB**：构建后用 `docker images` 验证。

### 3.2 docker-compose 规范
1. **三个服务**：`api`、`db`、`redis`，一键启动。
2. **依赖顺序**：`api` 用 `depends_on` + `condition: service_healthy` 等待 `db` 和 `redis` 就绪。
3. **健康检查**：
   - PostgreSQL：`pg_isready -U $POSTGRES_USER`
   - Redis：`redis-cli ping`
   - API：`curl -f http://localhost:8000/health` 或访问 `/docs`
4. **数据持久化**：PostgreSQL 数据用 named volume 挂载。
5. **环境变量**：从 `.env` 文件读取，不硬编码密码。
6. **网络**：三个服务在同一自定义网络中互通。

### 3.3 Hooks 规范
1. **Hook 脚本必须进 git**：`.claude/` 目录提交到版本控制。
2. **脚本位置**：`.claude/hooks/` 目录下。
3. **配置文件**：`.claude/settings.json` 注册所有钩子。
4. **输出规范**：所有输出走 `console.error`（stderr），禁止 `console.log`。
5. **退出码**：拦截时 `process.exit(1)`，放行时 `process.exit(0)`。
6. **至少 5 个 Hook 场景**：
   - PreToolUse：拦截硬编码密钥
   - PreToolUse：拦截误删迁移文件
   - PreToolUse：拦截 .env 文件提交
   - PostToolUse：自动 Lint + 格式化
   - Stop：强制运行测试
7. **测试要快**：Hook 触发的测试必须在 10 秒内完成，慢测试单独标记。

### 3.4 密钥拦截规则
Hook 必须能识别以下密钥格式并拦截：
- OpenAI/API 密钥：`sk-[a-zA-Z0-9]{20,}`
- AWS Access Key：`AKIA[A-Z0-9]{16}`
- GitHub Token：`ghp_[a-zA-Z0-9]{36}`
- 通用密钥模式：`api_key\s*=\s*["'][^"']+["']`、`secret\s*=\s*["'][^"']+["']`
- `.env` 文件写入操作

### 3.5 文件规范
- **单个代码文件 ≤ 500 行**，超过必须拆分。
- 文件命名使用小写+下划线（snake_case）。
- Hook 脚本使用 `.js` 或 `.sh` 后缀。

### 3.6 项目结构（Day 14 新增）
```
.
├── Dockerfile                    # 多阶段构建镜像
├── .dockerignore                 # Docker 构建排除文件
├── docker-compose.yml            # API + PG + Redis 一键启动
├── .claude/
│   ├── settings.json             # Hooks 配置
│   └── hooks/
│       ├── pre-secret-check.js   # 前置：密钥硬编码拦截
│       ├── pre-dangerous-cmd.js  # 前置：危险命令拦截
│       ├── pre-env-check.js      # 前置：.env 文件拦截
│       ├── post-lint-format.js   # 后置：自动 Lint + 格式化
│       └── stop-run-tests.js     # 停止：强制跑测试
├── cv-service/                   # CV 推理服务（CV 方向）
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── frontend-types/               # OpenAPI 生成的前端类型
│   └── api.d.ts
├── app/                          # 现有后端代码
├── tests/                        # 现有测试
├── pyproject.toml
└── specd14.md                    # 本阶段需求说明书
```

---

## 4. 开发流程

> 以下每个阶段的"执行指令"可直接复制给 AI 执行。每个阶段末尾附有本阶段相关的红线提醒。

---

### 阶段 A：写 Dockerfile

**本阶段做什么：**
1. 在项目根目录创建 `Dockerfile`，用多阶段构建（builder + runtime）。
2. 基础镜像用 `python:3.12-slim`。
3. builder 阶段：装构建依赖、`pip install`。
4. runtime 阶段：只复制运行时需要的文件，创建普通用户 `appuser`。
5. 先复制 `pyproject.toml` 装依赖，再复制业务代码（利用缓存）。
6. 创建 `.dockerignore`，排除不需要的文件。
7. 配置 `HEALTHCHECK`。
8. 构建镜像，验证大小 ≤200MB。

**验收标准：**
- `docker build -t smart-commit-backend .` 构建成功。
- `docker images` 显示镜像大小 ≤200MB。
- 容器内以非 root 用户运行（`whoami` 返回 `appuser`）。

**执行指令：**
```
请执行阶段 A：写 Dockerfile。
要求：
1. 在项目根目录创建 Dockerfile，使用多阶段构建（builder + runtime）。
2. 基础镜像用 python:3.12-slim，不要用 python:3.12。
3. builder 阶段：安装构建依赖（如 build-essential），复制 pyproject.toml，pip install 依赖。
4. runtime 阶段：
   - 基于 python:3.12-slim
   - 创建普通用户 appuser（useradd -m appuser）
   - 从 builder 复制已安装的 Python 包
   - 复制业务代码
   - USER appuser
   - EXPOSE 8000
   - HEALTHCHECK 用 curl 或 python 访问 /health
   - CMD 用 uvicorn 启动
5. 先复制 pyproject.toml 装依赖，再复制业务代码（利用 Docker 缓存）。
6. 创建 .dockerignore，排除：.git、venv、__pycache__、tests、.env、*.md、.mcp.json、.claude、bruno、docs、alembic/versions/*.pyc 等。
7. 构建镜像：docker build -t smart-commit-backend .
8. 运行 docker images 查看镜像大小，必须 ≤200MB。
9. 告诉我镜像大小是多少。
```

**本阶段红线提醒：**
- ⚠️ 红线1：基础镜像必须用 `python:3.12-slim`，用 `python:3.12` 镜像轻松 1GB+。
- ⚠️ 红线2：先复制依赖声明再复制业务代码，否则改一行代码就重装所有依赖。
- ⚠️ 红线3：容器里必须用非 root 用户跑，生产环境安全漏洞。
- ⚠️ 红线5：必须写 `.dockerignore`，否则 `.git`、`venv`、`tests` 全打包进镜像。

---

### 阶段 B：写 docker-compose.yml

**本阶段做什么：**
1. 在项目根目录创建 `docker-compose.yml`。
2. 三个服务：`api`、`db`（postgres:16-alpine）、`redis`（redis:7-alpine）。
3. 配置健康检查和依赖顺序。
4. PostgreSQL 数据用 volume 持久化。
5. 环境变量从 `.env` 读取。
6. 一键启动，30 秒内三个容器全部 Up。

**验收标准：**
- `docker-compose up -d` 启动成功。
- `docker-compose ps` 三个容器状态都是 Up（healthy）。
- 浏览器访问 `http://localhost:8000/docs` 能打开。

**执行指令：**
```
请执行阶段 B：写 docker-compose.yml。
要求：
1. 在项目根目录创建 docker-compose.yml。
2. 定义三个服务：
   - api：构建自当前目录 Dockerfile，端口映射 8000:8000
   - db：image: postgres:16-alpine，环境变量从 .env 读取
   - redis：image: redis:7-alpine
3. api 配置 depends_on，db 和 redis 的 condition 为 service_healthy。
4. 健康检查配置：
   - db：pg_isready -U $POSTGRES_USER
   - redis：redis-cli ping
   - api：curl -f http://localhost:8000/health 或 python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
5. PostgreSQL 数据用 named volume 持久化（pgdata）。
6. 三个服务加入同一自定义网络（如 backend-network）。
7. api 的环境变量从 .env 文件读取，数据库连接指向 db 服务名。
8. 运行 docker-compose up -d，等待 30 秒。
9. 运行 docker-compose ps，确认三个容器状态都是 Up。
10. 浏览器访问 http://localhost:8000/docs，确认能打开。
```

**本阶段红线提醒：**
- ⚠️ 红线4：必须加 `depends_on` + `condition: service_healthy`，否则后端在数据库没准备好时就启动会报错退出。
- ⚠️ 红线3：数据库密码不硬编码，从 `.env` 读取。

---

### 阶段 C：CV 推理服务容器化（CV 方向必做）

**本阶段做什么：**
1. 创建 `cv-service/` 目录，包含 `Dockerfile`、`app.py`、`requirements.txt`。
2. 用 ONNX Runtime (CPU) 部署推理服务。
3. 容器启动时加载模型（预热），避免首次请求超时。
4. 配置健康检查端点 `/health`，返回模型加载状态。
5. 镜像 ≤500MB。
6. 加入 docker-compose，与 API 服务网络互通。

**验收标准：**
- 容器启动后健康检查通过。
- 首次推理请求无需等待模型加载（预热生效）。
- `docker images` 显示 CV 镜像 ≤500MB。

**执行指令：**
```
请执行阶段 C：CV 推理服务容器化。
要求：
1. 创建 cv-service/ 目录，包含：
   - Dockerfile（基于 python:3.12-slim，安装 onnxruntime）
   - app.py（FastAPI 服务，加载 ONNX 模型，提供 /predict 和 /health 端点）
   - requirements.txt（fastapi、uvicorn、onnxruntime、numpy、pydantic）
2. Dockerfile 基于 python:3.12-slim，安装 onnxruntime（CPU 版）。
3. app.py 中在 startup 事件里加载 ONNX 模型（预热），/health 返回模型加载状态。
4. /predict 端点接收输入数据，返回推理结果。
5. 创建非 root 用户运行服务。
6. 配置 HEALTHCHECK。
7. 在 docker-compose.yml 中添加 cv 服务，与 api 在同一网络。
8. 构建镜像，验证大小 ≤500MB。
9. 启动容器，验证 /health 返回模型已加载。
```

**本阶段红线提醒：**
- ⚠️ 模型必须在容器启动时预热加载，否则首次推理请求会超时。
- ⚠️ CV 镜像 ≤500MB，用 slim 基础镜像控制体积。

---

### 阶段 D：配置 5+ Hooks 护栏

**本阶段做什么：**
1. 创建 `.claude/settings.json` 配置文件。
2. 创建 `.claude/hooks/` 目录，编写 5 个 Hook 脚本。
3. PreToolUse 钩子（3 个）：密钥拦截、危险命令拦截、.env 文件拦截。
4. PostToolUse 钩子（1 个）：自动 Lint + 格式化。
5. Stop 钩子（1 个）：强制运行测试。
6. 所有脚本用 `console.error` 输出，禁止 `console.log`。
7. 把 `.claude/` 目录提交到 git。

**验收标准：**
- 故意写 `sk-xxx`，Hook 拦截报错。
- 故意执行 `rm -rf alembic/`，Hook 拦截。
- 改完代码后 PostToolUse 自动跑 ruff format + ruff check。
- 会话结束时 Stop 钩子自动跑 pytest，不通过则阻断。

**执行指令：**
```
请执行阶段 D：配置 5+ Hooks 护栏。
要求：

1. 创建 .claude/settings.json，注册以下钩子：
   - PreToolUse（匹配 Write|Edit|Bash）：pre-secret-check.js
   - PreToolUse（匹配 Bash）：pre-dangerous-cmd.js
   - PreToolUse（匹配 Write|Edit）：pre-env-check.js
   - PostToolUse（匹配 Write|Edit）：post-lint-format.js
   - Stop：stop-run-tests.js

2. 创建 .claude/hooks/pre-secret-check.js：
   - 读取工具输入中的文件内容或命令文本
   - 用正则匹配密钥模式：sk-[a-zA-Z0-9]{20,}、AKIA[A-Z0-9]{16}、ghp_[a-zA-Z0-9]{36}、api_key\s*=\s*["'][^"']+["']、secret\s*=\s*["'][^"']+["']
   - 匹配到则 console.error 输出拦截原因，process.exit(1)
   - 否则 process.exit(0)
   - 所有输出用 console.error，禁止 console.log

3. 创建 .claude/hooks/pre-dangerous-cmd.js：
   - 读取 Bash 命令
   - 拦截 rm -rf migrations/、rm -rf alembic/、rm -rf app/、DROP TABLE、--no-verify 等危险操作
   - 匹配到则拦截，process.exit(1)

4. 创建 .claude/hooks/pre-env-check.js：
   - 检查写入的文件路径是否为 .env
   - 如果是 .env 文件，拦截并提示"禁止提交 .env 文件"

5. 创建 .claude/hooks/post-lint-format.js：
   - 对修改的 .py 文件运行 ruff format 和 ruff check
   - 检测 print() 调试语句、ALLOW_ORIGINS=*、Authorization 日志等安全警告
   - 用 console.error 输出结果

6. 创建 .claude/hooks/stop-run-tests.js：
   - 在会话结束时运行 pytest（带 --tb=short -q）
   - 测试不通过则 console.error 提示，process.exit(1)
   - 测试要快（<10 秒）

7. 确保 .claude/ 目录被 git 跟踪（不要被 .gitignore 排除）。

8. 测试每个 Hook 是否生效。
```

**本阶段红线提醒：**
- ⚠️ 红线6：Hook 脚本禁止用 `console.log`，MCP 走 stdio 通信会污染协议导致崩溃，必须用 `console.error`。
- ⚠️ 红线7：`.claude/` 目录必须进 git，否则队友拿不到 Hook 配置。
- ⚠️ 红线8：Stop 钩子跑的测试必须 <10 秒，慢测试单独标记。

---

### 阶段 E：质量门禁 + OpenAPI 类型同步

**本阶段做什么：**
1. 确认 pytest + httpx 测试覆盖率 ≥70%。
2. 用 `scripts/export_openapi.py` 导出 OpenAPI schema（无需启动服务器）。
3. 用 `openapi-typescript` 从本地 `openapi.json` 生成前端 TypeScript 类型。
4. 通过 `npm run gen:types` 一键生成类型（已配置，无需修改 package.json）。

> **⚠️ Hook 交互注意事项（必读，避免工具调用反复失败）**
>
> 阶段 E 涉及大量测试文件编写和命令执行。以下 Hook 行为已修正以适配本阶段：
>
> 1. **`post-lint-format.js`**：写入 `.py` 文件后运行 `ruff format --check`（只读，不自动修改文件）和 `ruff check`。Lint/格式问题**只输出警告，不阻断**工具调用。如果看到 ruff 警告，在后续编辑中修复即可，**不要反复重试同一个写入操作**。
> 2. **`pre-secret-check.js`**：测试文件（`tests/`、`conftest.py`、`seed.py`、`scripts/`）已加入白名单，不会因 `password = "testpass123"` 等测试数据被拦截。非测试文件中仍禁止硬编码密钥。
> 3. **`stop-run-tests.js`**：会话结束时运行 `pytest --no-cov`（不含覆盖率检查），只验证测试是否通过。覆盖率门禁在手动运行 `pytest --cov` 或 CI 时才生效。
> 4. **执行策略**：
>    - 新建测试文件用 `write_to_file`，修改已有测试文件用 `replace_in_file`。
>    - 运行测试和类型生成命令用 `execute_command`，**不要手动写入 `openapi.json` 或 `api.d.ts`**（这些是自动生成的产物）。
>    - 如果 `replace_in_file` 报 SEARCH 不匹配，先 `read_file` 重新读取当前文件内容再操作。
>    - 项目已有 `scripts/export_openapi.py`、`package.json` 中的 `gen:types` 脚本、`frontend-types/` 目录，**不要重复创建**。

**验收标准：**
- `pytest --cov=app --cov-report=term-missing --cov-fail-under=70` 通过。
- `python scripts/export_openapi.py` 能导出 `openapi.json`。
- `npm run gen:types` 能生成 `frontend-types/api.d.ts`。

**执行指令：**
```
请执行阶段 E：质量门禁 + OpenAPI 类型同步。

重要前提：项目已有 scripts/export_openapi.py、package.json（含 gen:types 脚本）、
frontend-types/ 目录和 openapi-typescript 依赖。不要重复创建这些文件。

要求：
1. 运行覆盖率检查：
   python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70 --no-header -q
   如果覆盖率不达标，针对未覆盖的模块用 write_to_file 或 replace_in_file 补写测试。
   测试文件中的 password = "testpass123" 等测试数据不会被 Hook 拦截。

2. 导出 OpenAPI schema 并生成 TypeScript 类型（一条命令完成，无需启动服务器）：
   npm run gen:types
   此命令内部执行：
   python scripts/export_openapi.py && npx openapi-typescript openapi.json -o frontend-types/api.d.ts

3. 用 read_file 检查 frontend-types/api.d.ts 包含完整的接口类型定义。

4. 确保测试能在 10 秒内跑完，慢测试用 @pytest.mark.slow 标记。
   pyproject.toml 中已配置 markers = ["slow: marks tests as slow"]。
```

**本阶段红线提醒：**
- ⚠️ 红线9：OpenAPI 类型生成必须加进 CI，否则后端改字段前端忘了同步。
- ⚠️ 红线8：测试要快（<10 秒），慢测试单独标记。

---

### 阶段 F：录 90 秒演示视频

**本阶段做什么：**
1. 录屏演示 4 个场景。
2. 展示 Docker 启动快、Hook 拦截快。

**验收标准：**
- 视频完整展示 4 个场景。
- 三个容器 30 秒内启动。
- Hook 拦截提示几秒内弹出。

**执行指令：**
```
请协助准备阶段 F 的演示：
1. 确保 docker-compose up -d 能在 30 秒内启动三个容器。
2. 确保 /docs 能正常访问。
3. 准备一个后端字段变更的示例，运行 npm run gen:types 展示类型自动更新。
4. 准备一个带 sk-xxx 的代码示例，展示 Hook 拦截。
5. 录制 90 秒视频，包含以上 4 个场景。
```

---

## 5. 验收标准（总表）

| # | 验收项 | 验收方式 | 通过标准 |
|---|--------|----------|----------|
| 1 | 后端镜像大小 | `docker images` | ≤200MB |
| 2 | 三容器启动 | `docker-compose ps` | api、db、redis 状态均为 Up（healthy） |
| 3 | API 文档可访问 | 浏览器访问 `http://localhost:8000/docs` | 能看到接口列表 |
| 4 | 密钥拦截 | 故意写 `sk-xxx` | Hook 拦截报错，exit code 1 |
| 5 | 危险命令拦截 | 故意执行 `rm -rf alembic/` | Hook 拦截 |
| 6 | 测试门禁 | 改完代码后 Stop 钩子 | pytest 全绿才放行 |
| 7 | OpenAPI JSON | 访问 `/openapi.json` | 返回完整 JSON |
| 8 | 前端类型生成 | 运行 `npm run gen:types` | `frontend-types/api.d.ts` 有输出 |
| 9 | 非 root 运行 | 容器内 `whoami` | 返回 `appuser` |
| 10 | CV 推理服务 | 容器启动后访问 `/health` | 返回模型已加载，镜像 ≤500MB |

---

## 6. 常见陷阱（10 条红线）

| # | 陷阱 | 后果 | 规避措施 |
|---|------|------|----------|
| 1 | 基础镜像用 `python:3.12` 而不是 `slim` | 镜像轻松 1GB+ | 必须用 `python:3.12-slim` |
| 2 | 先 COPY 业务代码再装依赖 | 改一行代码就重装所有依赖，每次构建 30 秒 | 先 COPY `pyproject.toml` 装依赖，再 COPY 业务代码 |
| 3 | 容器里用 root 用户跑程序 | 生产环境安全漏洞 | 必须创建普通用户 `appuser` 运行 |
| 4 | docker-compose 忘了加 healthcheck | 后端在数据库还没准备好时就启动，报错退出 | 加 `depends_on` + `condition: service_healthy` |
| 5 | `.dockerignore` 没写 | 把 `.git`、`venv`、`tests` 全打包进镜像，体积暴增 | 必须有 `.dockerignore` |
| 6 | Hook 脚本用 `console.log` 输出 | MCP 走 stdio 通信，`console.log` 污染协议导致崩溃 | 用 `console.error` 走 stderr |
| 7 | Hooks 没进 git | 队友拿不到 Hook 配置 | 把 `.claude/` 目录提交到 git |
| 8 | 测试跑得太慢，Hook 卡住 | AI 每次结束都要等很久 | 测试 <10 秒，慢测试单独标记 |
| 9 | OpenAPI 类型没加进 CI | 后端改字段前端忘了同步，联调爆炸 | 类型生成命令加进 CI |
| 10 | 互拆环节走形式 | 漏掉的 Hook 拦截点没被发现 | 互拆必须产出正式报告，列出 3 条发现 |

---

## 7. 安全注意事项（10 条）

| # | 安全风险 | 说明 | 防护措施 |
|---|----------|------|----------|
| 01 | 硬编码 API 密钥（`sk-xxx`） | 直接提交密钥导致敏感信息泄露，Critical 级 | Hook 强制拦截 |
| 02 | 误删数据库迁移文件 | `rm -rf migrations/` 破坏版本控制，不可逆 | Hook 强制阻断 |
| 03 | 跳过 Git 钩子检查 | `--no-verify` 绕过防护 | CI 流水线兜底 |
| 04 | 提交 `.env` 文件 | 含密钥，入库即泄露 | Hook 拦截 + `.gitignore` 双重防护 |
| 05 | Docker 容器以 Root 运行 | 容器内 root 存在越权攻击风险 | Lint 阶段抛出安全警告 |
| 06 | 测试失败强行 Push | 用例未通过禁止提交 | Hook 直接阻断 |
| 07 | 日志明文记录 Token | Authorization 头写入日志导致泄露 | 静态代码扫描拦截 |
| 08 | 跨域 `ALLOW_ORIGINS=*` | 生产环境放开所有跨域导致 CSRF | Lint 检查强烈警告 |
| 09 | `print` 替代 Logger | 线上残留 print 导致日志混乱 | Hook + Lint 拦截 |
| 10 | 盲目复制外部代码 | 第三方代码可能携带漏洞或协议冲突 | License Check 扫描 |

---

## 8. 协作心法

- **并行推进**：四个子项目（Docker、CV、Hooks、质量门禁）同步开发，遇到阻塞快速结对排查，不卡点。
- **策略**：优先完成可演示的最小可用版本，小步快跑迭代。
- **图码验收时刻**：135 分钟后全员演示 PK，重点验收镜像轻量化与工程化完备度。
- **比拼**：谁的镜像体积最小？谁的 Hook 设计最实用？
- **互拆**：互拆必须产出一份正式报告，列出至少 3 条发现。
