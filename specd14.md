# SmartCommitHelper·后端工程化+AI行为治理项目说明书 (specd14.md)

## 一、项目目的

给 **Smart Commit Backend** 做两件事：打包成 Docker 镜像，并给它装上 Hooks。

### 解决什么问题：
- **现在代码只能在你的电脑上跑**，换台电脑或交给队友，要花半小时装环境、装依赖、配数据库，效率极低。
- **AI 写代码太"自由"**，AI 帮写的代码里可能还藏着隐患（比如报错格式不统一、测试没写完整），需要有人把关。
- **规范靠人记，迟早会忘**。你定的代码规矩，AI 和队友可能没认真看，需要有个东西能"强制"执行，而不是靠自觉。

### 这个项目做完之后的效果：
- 任何新人拿到代码，**30 秒内**就能在电脑上把全套后端跑起来。
- AI 每次写代码/改代码，**自动跑测试、自动查有没有硬编码密钥、自动格式化**，不守规矩就不让过。
- 后端接口改了，前端类型**自动同步**，不会出现"后端改了字段，前端还在用旧的"这种联调事故。

---

## 二、前置依赖（本项目的"原材料"清单）

在开始 Day14 之前，必须先确认下面这些东西已经准备好。如果没有，先补上再进这一步。

在开始本项目之前，应该已经有：

| # | 依赖项 | 位置 | 要求 |
|---|--------|------|------|
| 1 | Day11 的 8 个接口代码 | `app/routes/` 目录下的所有接口 | 接口文件齐全 |
| 2 | Day12 的数据库+MCP配置 | 7张表的SQLAlchemy模型、Alembic Migration、`.mcp.json` | 模型和迁移可正常执行 |
| 3 | Day13 的安全认证代码 | JWT认证+bcrypt密码+RBAC权限中间件 | 认证流程可跑通 |
| 4 | pytest测试文件 | `tests/` 目录 | 至少覆盖8个接口的核心流程，能跑通 |
| 5 | 服务能正常启动 | 本机运行 | `uvicorn app.main:app` 能起来，`/docs` 能访问 |

**确认清单：**
> 请检查：`app/routes/` 有接口文件，`app/db/models/` 有数据库模型，`app/core/` 有认证代码，`tests/` 有测试文件。如果缺了，先补完对应的 Day11-13 任务再回来。
>
> **如果没有测试文件，让 AI 先补写 Day11 八个接口的测试（至少覆盖正常流程和常见报错），跑通后再继续 Day 14。**

---

## 三、项目功能

1. **把后端装进 Docker 集装箱**：把代码和运行环境打包成一个标准镜像，在任何电脑上都能一键启动。
2. **一键启动全套环境**：用 `docker-compose` 同时启动后端+PostgreSQL+Redis，新人 30 秒拉起。
3. **给 AI 装"规矩"**：用 Hooks 在 Cline 写代码/改代码时自动拦截检查：查密钥硬编码、自动格式化、自动跑测试。
4. **前后端类型同步**：后端接口改了，用 OpenAPI 自动生成前端 TypeScript 类型，前后端永远对齐。
5. **CV 推理服务容器化**（CV 方向必做）：ONNX CPU 推理能力，配置模型预热与健康检查机制，镜像 ≤500MB。

---

## 四、核心约束

1. **镜像大小必须 ≤200MB**：不能用那些"全家桶"基础镜像，必须用精简版。
2. **生产环境容器里不能用 root 用户跑**：必须创建普通用户来运行程序。
3. **API+PG+Redis 三个容器必须一起启动**：`docker-compose up` 一键拉起全套环境。
4. **Hook 必须放在项目仓库里**：`.claude/hooks/` 目录下的脚本要进 git。
5. **"测试即门禁"**：Hooks 里必须配置"测试不通过就不让提交"。
6. **密钥拦截必须生效**：任何写 `sk-xxx`、`AKIAxxx` 等密钥格式的代码，Hook 直接拦截，不许提交。
7. **CV 推理镜像 ≤500MB**：CV 方向必做项，ONNX CPU 推理，带模型预热和健康检查。

---

## 五、技术限制

| 项目 | 技术选型 | 说明 |
|------|----------|------|
| 后端基础镜像 | `python:3.12-slim` | 精简版，别用 `python:3.12`（太大） |
| 数据库镜像 | `postgres:16-alpine` | 轻量版 PostgreSQL |
| 缓存镜像 | `redis:7-alpine` | 轻量版 Redis |
| Hook 脚本语言 | JavaScript / Shell | 放在 `.claude/hooks/` 目录 |
| OpenAPI 工具 | `openapi-typescript` | 后端 schema 自动生成前端类型 |
| 测试工具 | `pytest + httpx` | 和之前保持一致 |
| CV 推理 | ONNX Runtime (CPU) | 模型预热 + 健康检查 |

---

## 六、完成步骤

### 阶段 A：写 Dockerfile（50 分钟）

在项目根目录写一个 Dockerfile，把后端代码打包成镜像。要求：

1. 用**多阶段构建**（builder + runtime），第一阶段装依赖和编译，第二阶段只复制运行需要的文件。
2. 基础镜像用 `python:3.12-slim`，不要用 `python:3.12`（太大）。
3. 先复制 `requirements.txt`（或 `pyproject.toml`）装依赖，再复制业务代码（这样可以充分利用缓存，改代码不用重装依赖）。
4. 创建普通用户（如 `appuser`），容器里不用 root 跑程序。
5. 暴露端口（如 8000），配置健康检查（HEALTHCHECK）。
6. 必须写 `.dockerignore`，排除 `.git`、`venv`、`__pycache__`、`tests`、`.env` 等不需要的文件。
7. 最终镜像大小必须 ≤200MB。

**验收：** AI 构建完成后告诉你镜像大小，必须 ≤200MB。把 `docker images` 截图发给你看。

---

### 阶段 B：写 docker-compose.yml（30 分钟）

用 docker-compose 同时启动三个服务：后端 API、PostgreSQL、Redis。

1. 三个服务：`api`（后端）、`db`（PostgreSQL 16 Alpine）、`redis`（Redis 7 Alpine）。
2. `api` 服务依赖 `db` 和 `redis`，配置 `depends_on` + `condition: service_healthy`，确保数据库准备好后再启动后端。
3. 数据库配置健康检查（`pg_isready`），Redis 配置健康检查（`redis-cli ping`）。
4. 后端配置健康检查（访问 `/health` 或 `/docs`）。
5. 数据持久化：PostgreSQL 数据用 volume 挂载。
6. 环境变量从 `.env` 文件读取，不硬编码密码。
7. 一键启动：`docker-compose up -d`，三个容器 30 秒内全部 Up。

**验收：** 跑 `docker-compose ps`，三个容器状态都是 Up。浏览器访问 `/docs` 能打开。

---

### 阶段 C：CV 推理服务容器化（30 分钟，CV 方向必做）

1. 用 ONNX Runtime (CPU) 部署推理服务。
2. 配置模型预热：容器启动时加载模型，避免首次请求超时。
3. 配置健康检查端点（如 `/health`），返回模型加载状态。
4. 镜像 ≤500MB。
5. 加入 docker-compose，与 API 服务网络互通。

**验收：** 容器启动后健康检查通过，首次推理请求无需等待模型加载。

---

### 阶段 D：配置 5+ Hooks 护栏（35 分钟）

在 `.claude/hooks/` 目录下配置钩子脚本，在 `.claude/settings.json` 中注册。

**前置拦截（PreToolUse）——安全与合规的第一道防线：**
- 在执行 Bash 命令或写入文件前自动触发校验脚本。
- 拦截危险操作（如 `rm -rf migrations/`、`rm -rf alembic/`）。
- 扫描密钥硬编码风险（`sk-xxx`、`AKIAxxx`、`ghp_xxx` 等）。
- 拦截 `.env` 文件提交。
- 从源头阻断安全隐患与违规行为。

**后置闭环（PostToolUse）——自动化质量与测试保障：**
- 自动触发代码格式化（ruff format）与 Lint 检查（ruff check）。
- 检测 `print()` 调试语句、`ALLOW_ORIGINS=*` 跨域通配符、root 用户运行等安全警告。
- 检测日志中明文记录 Authorization Token。

**Stop 钩子——会话结束强制测试：**
- 在会话结束时强制运行单元测试（pytest）。
- 测试不通过则阻断，确保交付代码符合质量标准。

**至少 5 个 Hook 场景：**
1. PreToolUse：拦截硬编码密钥
2. PreToolUse：拦截误删迁移文件
3. PreToolUse：拦截 .env 文件提交
4. PostToolUse：自动 Lint + 格式化
5. Stop：强制运行测试
6. （可选）PostToolUse：检测 print 调试语句 / CORS 通配符 / Token 日志

**注意：** Hook 脚本中禁止使用 `console.log` 输出（MCP 走 stdio 通信，console.log 会污染协议导致崩溃），必须用 `console.error` 走 stderr。

**验收：** 让 AI 故意写 `sk-xxx`，Hook 拦截报错。改完代码后测试自动跑，全绿才放行。

---

### 阶段 E：质量门禁 + OpenAPI 类型同步（20 分钟）

1. 确保 pytest + httpx 测试覆盖率 ≥70%（`pyproject.toml` 已配置 `--cov-fail-under=70`）。
2. 用 `openapi-typescript` 从后端 `/openapi.json` 自动生成前端 TypeScript 类型文件。
3. 把类型生成命令加进 CI 流程或 npm script，后端改了字段前端能自动同步。
4. 测试要快（<10 秒），慢的测试单独标记。

**验收：** 访问 `/openapi.json` 能看到完整 JSON。跑生成命令后有 `.ts` 文件输出。

---

### 阶段 F：录 90 秒演示视频（20 分钟）

录 90 秒视频，演示下面的内容：

1. 跑 `docker-compose up -d`，三个容器启动。
2. 浏览器打开 `/docs`，能看到接口列表。
3. 后端接口改了字段，跑一次类型生成命令，前端类型自动更新。
4. 故意让 AI 写一个带密钥的代码，Hook 拦截报警。

**验收：** 视频里能完整看到上面 4 个场景。

> 注意：视频里要尽量展示出 **Docker 启动快**（三个容器启动能在 30 秒内完成）、**Hook 拦截快**（拦截提示在几秒内弹出）的效果。

---

## 七、验收标准

| 阶段 | 你怎么验收 |
|------|-----------|
| 1 | Cline 给你看 `docker images` 截图，镜像大小 ≤200MB |
| 2 | 跑 `docker-compose ps`，三个容器状态都是 `Up`。浏览器访问 `/docs` 能打开 |
| 3 | 让 Cline 故意写 `sk-xxx`，Hook 拦截报错。改完代码后测试自动跑，全绿才放行 |
| 4 | 访问 `/openapi.json` 能看到完整 JSON。跑生成命令后有 `.ts` 文件输出 |

---

## 八、常见陷阱（10 条红线）

| # | 陷阱 | 后果 | 规避措施 |
|---|------|------|----------|
| 1 | 基础镜像用 `python:3.12` 而不是 `slim` | 镜像轻松 1GB+ | 必须用 `python:3.12-slim` |
| 2 | 先 COPY 业务代码再装依赖 | 改一行代码就重装所有依赖，每次构建 30 秒 | 先 COPY `requirements.txt`/`pyproject.toml` 装依赖，再 COPY 业务代码 |
| 3 | 容器里用 root 用户跑程序 | 生产环境安全漏洞 | 必须创建普通用户（如 `appuser`）运行 |
| 4 | docker-compose 里忘了加 healthcheck | 后端在数据库还没准备好时就开始跑，报错退出 | 加 `depends_on` + `condition: service_healthy` |
| 5 | `.dockerignore` 没写 | 把 `.git`、`venv`、`tests` 全打包进镜像，体积暴增 | 必须有 `.dockerignore`，排除不需要的文件 |
| 6 | Hook 脚本用 `console.log` 输出 | MCP 走 stdio 通信，`console.log` 会污染协议导致崩溃 | 用 `console.error` 走 stderr |
| 7 | Hooks 没进 git | 队友拿不到 Hook 配置，只有你有 | 把 `.claude/` 目录提交到 git |
| 8 | 测试跑得太慢，Hook 卡住 | AI 每次结束都要等很久 | 测试要快（<10 秒），慢的测试单独标记 |
| 9 | OpenAPI 类型没加进 CI | 后端改了字段，前端忘了同步，联调爆炸 | 把类型生成命令加进 CI 流程 |
| 10 | 互拆环节走形式 | 漏掉的 Hook 拦截点没被发现 | 互拆必须产出一份正式报告，列出 3 条发现 |

---

## 九、安全注意事项（10 条）

| # | 安全风险 | 说明 | 防护措施 |
|---|----------|------|----------|
| 01 | 硬编码 API 密钥（`sk-xxx`） | 直接提交密钥会导致敏感信息泄露，属于 Critical 级风险 | Hook 强制拦截 |
| 02 | 误删数据库迁移文件 | 执行 `rm -rf migrations/` 会破坏版本控制，操作不可逆 | Hook 强制阻断提交 |
| 03 | 强行跳过 Git 钩子检查 | 使用 `--no-verify` 绕过防护，Hook 难以直接拦截 | 依赖 CI 流水线作为最后兜底 |
| 04 | 提交敏感配置 `.env` 文件 | 配置文件含密钥，一旦入库即泄露 | Hook 拦截 + `.gitignore` 规则双重防护 |
| 05 | Docker 容器以 Root 运行 | 容器内使用 root 存在越权攻击风险 | 代码 Lint 阶段直接抛出安全警告 |
| 06 | 单元测试失败强行 Push | pytest 用例未通过时禁止提交 | Hook 直接阻断操作，避免污染主干代码 |
| 07 | 日志明文记录鉴权 Token | Authorization 头写入日志会引发严重数据泄露 | 静态代码扫描必须拦截 |
| 08 | 跨域配置 `ALLOW_ORIGINS=*` | 生产环境放开所有跨域会导致 CSRF 攻击风险 | Lint 检查给出强烈安全警告 |
| 09 | 调试用 `print` 替代 Logger | 线上残留 print 会导致日志混乱且无法分级 | Hook 配合 Lint 拦截此类不规范代码 |
| 10 | 盲目复制粘贴外部代码 | 第三方代码可能携带漏洞或开源协议冲突 | 通过 License Check 扫描规避合规风险 |

---

## 十、协作心法

- **并行推进**：四个子项目（Docker、CV、Hooks、质量门禁）同步开发，遇到阻塞快速结对排查，不卡点。
- **策略**：优先完成可演示的最小可用版本，小步快跑迭代。
- **图码验收时刻**：135 分钟后全员演示 PK，重点验收镜像轻量化与工程化完备度。
- **比拼**：谁的镜像体积最小？谁的 Hook 设计最实用？