# CLAUDEDAY3.md — Smart Commit Helper 安全规范

> 本文件是 Smart Commit Helper 后端**安全认证与授权部分**的"宪法"，所有安全相关开发必须遵守。每个阶段的指令可直接复制给 AI 执行。

---

## 1. 项目概述

### 1.1 项目名称
Smart Commit Helper — 安全加固

### 1.2 项目背景
当前系统存在严重安全隐患：任何人都能调用接口、删除数据。本阶段目标是给系统装上完整的安全措施，做到：只有登录用户才能访问系统，管理员才能修改数据，普通成员只能查看，任何人只能看到自己团队的数据。密码安全存储，即使数据库泄露也拿不到原文。

### 1.3 核心业务规矩
- **密码绝不能明文存**：使用 bcrypt（cost=12）自动加盐加密。
- **Token 必须有有效期**：Access Token 15 分钟，Refresh Token 7 天。
- **只有管理员才能改数据**：写操作（POST/PUT/DELETE）必须校验管理员角色。
- **数据隔离是铁律**：所有查询必须带 `team_id` + `owner_id` 过滤，禁止跨团队访问。
- **登录失败统一回复**：无论邮箱不存在还是密码错误，统一返回"用户名或密码错误"，防止枚举攻击。
- **错误信息不能暴露敏感信息**：不返回堆栈、不泄露内部结构、不提示"邮箱已注册"。

### 1.4 核心交付物（8 个阶段）

| 阶段 | 交付物 | 验收标准 |
|------|--------|----------|
| S1 | 密码加密工具 | 同一密码每次生成不同 hash，但验证都能通过 |
| S2 | 注册接口 | Bruno 发注册请求，数据库 password 字段是乱码 |
| S3 | 登录接口 | 正确账号密码登录，拿到 Access Token + Refresh Token |
| S4 | Token 刷新接口 | 有效 Refresh Token 换新 Access Token，过期报错 |
| S5 | 认证依赖 | 不带 Token 访问受保护接口返回 401 |
| S6 | 角色校验依赖 | 普通成员 Token 调删除接口返回 403，管理员成功 |
| S7 | 行级权限校验 | 越权访问他团队数据返回 404 或 403 |
| S8 | 统一错误响应 | 所有错误 JSON 格式统一，带 trace_id |

---

## 2. 技术栈约束

| # | 约束 | 硬性要求 |
|---|------|----------|
| 1 | 密码加密 | **bcrypt**，cost=12，自动加盐 |
| 2 | Token 方案 | **JWT**，Access Token 15min + Refresh Token 7D |
| 3 | 签名算法 | **HS256**，用环境变量 `JWT_SECRET` 签名 |
| 4 | 密钥管理 | **环境变量**，所有 secret 走 `.env`，绝对不硬编码 |
| 5 | 权限校验 | **依赖注入**，FastAPI 的 `Depends()` 做统一拦截 |
| 6 | 行级权限 | **SQLAlchemy 查询过滤**，所有查询带 `team_id` + `owner_id` |
| 7 | CORS | **白名单**，只允许前端域名，不许设成 `"*"` |
| 8 | 类型检查 | **mypy** 严格模式，0 错误 |
| 9 | 代码风格 | **ruff**，0 警告 |
| 10 | 测试框架 | **pytest**，覆盖正常/无Token/过期Token/权限不足场景 |

---

## 3. 代码规范

### 3.1 核心安全铁律
1. **密码绝不明文**：数据库只存 bcrypt hash，禁止任何形式的明文存储或日志打印。
2. **JWT Secret 走环境变量**：`.env` 文件必须加入 `.gitignore`，绝对不提交 GitHub。
3. **Token 必须有过期时间**：Access 15min，Refresh 7d，禁止永久有效。
4. **Payload 最小化**：JWT Payload 只放 `user_id`、`role`、`exp`，禁止放密码等敏感信息。
5. **登录错误统一回复**：不区分"邮箱不存在"和"密码错误"，统一返回"用户名或密码错误"。
6. **查询必须带归属过滤**：所有数据查询必须带 `team_id` 过滤，防止 IDOR（越权访问）。
7. **CORS 禁止 `"*"`**：只开放前端域名白名单。
8. **错误不暴露堆栈**：统一用 HTTPException 抛出，不返回 traceback。

### 3.2 密码加密规范
- 使用 **bcrypt** 算法，cost factor = 12。
- 每次加密自动生成随机盐（salt），同一密码每次 hash 结果不同。
- 验证时使用 `bcrypt.checkpw()` 比对，不自行实现比较逻辑。
- 密码长度至少 8 位（注册时校验）。
- 禁止使用 MD5、SHA1、SHA256 等快速哈希算法（GPU 暴力破解极快）。

### 3.3 JWT Token 规范
- **Access Token**：
  - 有效期：15 分钟
  - 用途：访问受保护接口
  - Payload：`{ "sub": user_id, "role": role, "exp": 过期时间, "type": "access" }`
- **Refresh Token**：
  - 有效期：7 天
  - 用途：换取新的 Access Token
  - Payload：`{ "sub": user_id, "exp": 过期时间, "type": "refresh" }`
- 签名算法：HS256
- 签名密钥：从环境变量 `JWT_SECRET` 读取，禁止硬编码
- **Refresh Token 旋转**：旧 Refresh Token 被再次使用时，整条 Token 链作废（检测重放攻击）

### 3.4 权限校验规范
- 使用 FastAPI 的 `Depends()` 做统一拦截。
- **认证依赖 `get_current_user`**：验证 JWT 签名和过期时间，解析出 `user_id`，从数据库查出用户信息。
- **角色校验依赖 `require_admin`**：配合认证依赖，校验当前用户角色是否为 admin。
- **行级权限校验**：所有带 `id` 参数的接口，必须校验当前用户是否有权访问该数据（team_id 匹配）。
- 越权访问返回 404（不泄露资源是否存在）或 403。

### 3.5 错误响应规范
- 所有错误响应遵循 **RFC 7807**（Problem Details）格式。
- 必须包含 `trace_id` 字段，便于问题追踪。
- 500 错误不泄露堆栈、数据库结构、内部路径。
- 422 校验错误只返回字段级别的友好提示。
- 登录失败统一返回"用户名或密码错误"，不区分具体原因。

### 3.6 文件规范
- **单个代码文件 ≤ 500 行**，超过必须拆分。
- 文件命名使用小写+下划线（snake_case）。

### 3.7 项目结构（安全扩展）
```
app/
├── core/                    # 核心安全模块
│   ├── __init__.py
│   ├── security.py          # 密码加密/验证（bcrypt）
│   └── jwt_tokens.py        # JWT Token 生成/验证/刷新
├── dependencies/            # 依赖注入
│   ├── __init__.py
│   ├── auth.py              # get_current_user 认证依赖
│   └── roles.py             # require_admin 角色校验依赖
├── routes/
│   └── auth.py              # 注册/登录/刷新接口
├── schemas/
│   └── auth.py              # 认证相关 Schema
├── services/
│   └── auth_service.py      # 认证业务逻辑
└── middleware/
    └── token_blacklist.py   # Refresh Token 黑名单（旋转机制）
```

---

## 4. 开发流程

> 以下每个阶段的"执行指令"可直接复制给 AI 执行。每个阶段末尾附有本阶段相关的红线提醒。

---

### S1：密码加密工具

**本阶段做什么：**
1. 写一个加密工具，使用 bcrypt（cost=12）对密码进行哈希。
2. 写一个验证函数，校验用户输入的密码和数据库里的 hash 是否匹配。
3. 确保同一密码每次生成的 hash 都不一样（自动加盐），但验证都能通过。

**验收标准：**
- 同一个密码每次生成的 hash 都不一样。
- 用正确密码验证返回 True，错误密码返回 False。
- cost factor = 12。

**执行指令：**
```
请执行 S1 阶段：密码加密工具。
要求：
1. 创建 app/core/security.py。
2. 实现 hash_password(password: str) -> str：使用 bcrypt 加密密码，cost=12，自动加盐。
3. 实现 verify_password(plain_password: str, hashed_password: str) -> bool：验证密码是否匹配。
4. 确保同一密码每次 hash 结果不同（因为盐不同），但 verify 都能通过。
5. 禁止使用 MD5、SHA 等快速哈希算法。
6. 编写单元测试：
   - 同一密码两次 hash 结果不同
   - 正确密码验证通过
   - 错误密码验证失败
   - hash 以 $2b$12$ 开头（bcrypt 标识）
7. 运行 mypy 和 ruff 确保 0 错误 0 警告。
```

**本阶段红线提醒：**
- ⚠️ 红线1：密码绝不能明文存储或打印到日志。
- ⚠️ 红线2：禁止使用 MD5/SHA 等快速哈希，必须用 bcrypt cost=12。

---

### S2：注册接口

**本阶段做什么：**
1. 写一个注册接口，用户传邮箱、密码、团队编号。
2. 校验邮箱格式，密码长度至少 8 位。
3. 密码用 bcrypt 加密后存入数据库。

**验收标准：**
- 用 Bruno 发注册请求，数据库里能看到新用户。
- `password_hash` 字段是一串 bcrypt 乱码，不是明文。
- 邮箱格式错误返回 422。
- 密码少于 8 位返回 422。
- 邮箱已注册返回统一错误（不提示"邮箱已存在"以防枚举）。

**执行指令：**
```
请执行 S2 阶段：注册接口。
要求：
1. 创建 app/routes/auth.py，实现 POST /api/v1/auth/register。
2. 创建 app/schemas/auth.py，定义 RegisterRequest（email, password, name, team_id）和 RegisterResponse。
3. 请求校验：
   - email 必须是合法邮箱格式
   - password 至少 8 位
   - name 不能为空
4. 密码使用 S1 的 hash_password 加密后存入数据库。
5. 邮箱已存在时统一返回"注册失败，请检查输入"，不明确提示邮箱已注册。
6. 创建 app/services/auth_service.py 处理注册业务逻辑。
7. 用 Bruno 测试：
   - 正常注册返回 201
   - 邮箱格式错误返回 422
   - 密码少于 8 位返回 422
   - 查数据库确认 password_hash 是 bcrypt 乱码
8. 运行 mypy 和 ruff 确保 0 错误 0 警告。
```

**本阶段红线提醒：**
- ⚠️ 红线1：密码必须 bcrypt 加密后存储，禁止明文。
- ⚠️ 红线3：注册错误不提示"邮箱已存在"，防止枚举攻击。

---

### S3：登录接口

**本阶段做什么：**
1. 写一个登录接口，验证邮箱和密码。
2. 验证通过后签发两个 Token：
   - Access Token（15 分钟过期，用于访问接口）
   - Refresh Token（7 天过期，用于续期）

**验收标准：**
- 用正确的账号密码登录，拿到两个 Token。
- Access Token 解码后 Payload 只含 `user_id`、`role`、`exp`、`type`。
- 错误邮箱或密码统一返回"用户名或密码错误"。
- Token 有正确的过期时间。

**执行指令：**
```
请执行 S3 阶段：登录接口。
要求：
1. 创建 app/core/jwt_tokens.py，实现：
   - create_access_token(user_id: str, role: str) -> str：15 分钟过期
   - create_refresh_token(user_id: str) -> str：7 天过期
   - decode_token(token: str) -> dict：验证签名和过期时间
2. JWT 使用 HS256 算法，密钥从环境变量 JWT_SECRET 读取。
3. 在 app/routes/auth.py 实现 POST /api/v1/auth/login。
4. 登录逻辑：
   - 根据邮箱查用户
   - 用 verify_password 验证密码
   - 验证通过签发 Access Token + Refresh Token
   - 验证失败统一返回"用户名或密码错误"（不区分邮箱不存在还是密码错误）
5. Token Payload 只放 sub(user_id)、role、exp、type，禁止放密码。
6. 在 .env.example 中添加 JWT_SECRET 配置项。
7. 用 Bruno 测试：
   - 正确账号密码登录返回两个 Token
   - 错误密码返回"用户名或密码错误"
   - 不存在的邮箱返回"用户名或密码错误"
8. 运行 mypy 和 ruff 确保 0 错误 0 警告。
```

**本阶段红线提醒：**
- ⚠️ 红线4：JWT Secret 必须走环境变量，.env 必须在 .gitignore 中。
- ⚠️ 红线5：Token 必须有过期时间，Access 15min，Refresh 7d。
- ⚠️ 红线6：Payload 只放 user_id、role、exp，禁止放密码。

---

### S4：Token 刷新接口

**本阶段做什么：**
1. 用户用 Refresh Token 换一张新的 Access Token。
2. Refresh Token 过期了就报错"请重新登录"。
3. 实现 Refresh Token 旋转：旧 Refresh Token 被再次使用时，整条链作废。

**验收标准：**
- 拿有效 Refresh Token 能换新 Access Token，新 Token 能正常访问接口。
- Refresh Token 过期返回 401 "请重新登录"。
- 旧 Refresh Token 被再次使用时返回错误（旋转机制）。

**执行指令：**
```
请执行 S4 阶段：Token 刷新接口。
要求：
1. 在 app/routes/auth.py 实现 POST /api/v1/auth/refresh。
2. 逻辑：
   - 接收 Refresh Token
   - 验证签名和过期时间
   - 验证 Token 类型为 refresh
   - 检查 Refresh Token 是否在黑名单中（旋转机制）
   - 签发新的 Access Token
   - 将旧 Refresh Token 加入黑名单
3. Refresh Token 过期返回 401，detail 为"请重新登录"。
4. 实现 Token 黑名单机制（可用内存存储或数据库表）。
5. 用 Bruno 测试：
   - 有效 Refresh Token 换新 Access Token 成功
   - 新 Access Token 能正常访问受保护接口
   - 过期 Refresh Token 返回 401 "请重新登录"
   - 旧 Refresh Token 再次使用返回错误
6. 运行 mypy 和 ruff 确保 0 错误 0 警告。
```

**本阶段红线提醒：**
- ⚠️ 红线5：Token 必须有过期时间。
- ⚠️ 红线7：必须实现 Refresh Token 旋转，旧 Token 再次使用时整条链作废。

---

### S5：认证依赖

**本阶段做什么：**
1. 写一个认证依赖，每次请求进来验证签名和过期时间。
2. 解析出用户编号，从数据库查出用户信息。
3. 不带 Token 或 Token 无效返回 401。

**验收标准：**
- 访问带 `Depends(current_user)` 的接口，不带 Token 返回 401。
- 带有效 Token 能正常访问，并获取到当前用户信息。
- 带过期 Token 返回 401。
- 带伪造 Token 返回 401。

**执行指令：**
```
请执行 S5 阶段：认证依赖。
要求：
1. 创建 app/dependencies/auth.py，实现 get_current_user 依赖。
2. 逻辑：
   - 从 Authorization 头提取 Bearer Token
   - 验证 JWT 签名和过期时间
   - 验证 Token 类型为 access
   - 解析出 user_id
   - 从数据库查出用户信息
   - 用户不存在返回 401
3. 不带 Token 返回 401，detail 为"未提供认证凭证"。
4. Token 过期返回 401，detail 为"Token 已过期，请重新登录"。
5. Token 无效返回 401，detail 为"无效的认证凭证"。
6. 将现有 8 个接口全部加上 `Depends(get_current_user)` 保护。
7. 用 Bruno 测试：
   - 不带 Token 访问返回 401
   - 带有效 Token 访问成功
   - 带过期 Token 返回 401
   - 带伪造 Token 返回 401
8. 编写测试用例覆盖：正常、无 Token、过期 Token、无效 Token。
9. 运行 mypy 和 ruff 确保 0 错误 0 警告。
```

**本阶段红线提醒：**
- ⚠️ 红线8：所有受保护接口必须加认证依赖，不能遗漏。
- ⚠️ 红线5：Token 过期必须拒绝，不能放行。

---

### S6：角色校验依赖

**本阶段做什么：**
1. 写一个角色校验依赖，配合认证中间件校验当前用户角色。
2. 只允许管理员执行写操作（POST/PUT/DELETE）。
3. 普通成员的 Token 调用写操作返回 403。

**验收标准：**
- 用普通成员的 Token 调删除接口返回 403。
- 用管理员的 Token 调删除接口成功。
- 普通成员的 Token 调只读接口（GET）成功。

**执行指令：**
```
请执行 S6 阶段：角色校验依赖。
要求：
1. 创建 app/dependencies/roles.py，实现 require_admin 依赖。
2. 逻辑：
   - 依赖 get_current_user 获取当前用户
   - 校验用户角色是否为 admin
   - 非 admin 返回 403，detail 为"权限不足，需要管理员权限"
3. 将所有写操作（POST/PUT/DELETE）接口加上 Depends(require_admin)。
4. 只读接口（GET）只保留 Depends(get_current_user)。
5. 用 Bruno 测试：
   - 管理员 Token 调创建/更新/删除接口成功
   - 普通成员 Token 调创建/更新/删除接口返回 403
   - 普通成员 Token 调列表/详情接口成功
6. 编写测试用例覆盖：管理员写操作成功、普通成员写操作 403、普通成员读操作成功。
7. 运行 mypy 和 ruff 确保 0 错误 0 警告。
```

**本阶段红线提醒：**
- ⚠️ 红线9：写操作必须校验管理员角色，不能只校验登录状态。
- ⚠️ 红线10：403 错误不泄露资源是否存在。

---

### S7：行级权限校验

**本阶段做什么：**
1. 检查所有带 `id` 参数的接口。
2. 必须校验当前用户是否有权访问这个数据（team_id 匹配）。
3. 如果不匹配，返回 404 或 403，防止 IDOR（越权访问）。

**验收标准：**
- 用户 A 访问用户 B 团队的数据返回 404 或 403。
- 用户只能看到自己团队的数据。
- 所有查询都带 `team_id` 过滤。

**执行指令：**
```
请执行 S7 阶段：行级权限校验。
要求：
1. 审查所有带 {member_id}、{commit_id}、{team_id} 参数的接口。
2. 每个接口在查询数据时必须带 team_id 过滤：
   - 查询成员详情：WHERE id = :member_id AND team_id = :current_team_id
   - 查询提交详情：WHERE id = :commit_id AND team_id = :current_team_id
   - 更新成员：WHERE id = :member_id AND team_id = :current_team_id
   - 删除成员：WHERE id = :member_id AND team_id = :current_team_id
3. 从当前用户的认证信息中获取 team_id，不信任请求路径中的 team_id（防止篡改）。
4. 越权访问返回 404（不泄露资源是否存在），detail 为"查无此人"或"资源不存在"。
5. 用 Bruno 测试：
   - 团队 A 的用户访问团队 A 的数据成功
   - 团队 A 的用户访问团队 B 的数据返回 404
   - 修改路径中的 team_id 无法越权
6. 编写测试用例覆盖：正常访问、跨团队访问 404、篡改 team_id 404。
7. 运行 mypy 和 ruff 确保 0 错误 0 警告。
```

**本阶段红线提醒：**
- ⚠️ 红线11：team_id 必须从认证信息获取，不能信任请求路径中的 team_id。
- ⚠️ 红线12：所有查询必须带 team_id 过滤，禁止不带归属条件的查询。

---

### S8：统一错误响应

**本阶段做什么：**
1. 所有接口的错误响应统一格式。
2. 随便发一个错误请求，返回的 JSON 格式统一，带追踪号（trace_id）。
3. 错误信息不暴露堆栈、不泄露内部结构。

**验收标准：**
- 所有错误返回的 JSON 结构完全一致。
- 每个错误响应都带 trace_id。
- 响应头中有 X-Trace-Id。
- 500 错误不返回堆栈信息。

**执行指令：**
```
请执行 S8 阶段：统一错误响应。
要求：
1. 确保所有错误响应遵循 RFC 7807 格式，包含：type, title, status, detail, instance, trace_id。
2. 检查全局异常处理器覆盖：
   - 401 未认证 → RFC 7807 格式
   - 403 权限不足 → RFC 7807 格式
   - 404 资源不存在 → RFC 7807 格式
   - 422 参数校验失败 → RFC 7807 格式
   - 500 服务器内部错误 → RFC 7807 格式（不泄露堆栈）
3. 确保 trace_id 中间件正常工作：
   - 每个请求自动生成 UUID4
   - 响应头 X-Trace-Id 返回 trace_id
   - 错误响应体包含 trace_id
4. 登录失败统一返回"用户名或密码错误"，不区分具体原因。
5. 用 Bruno 测试：
   - 发一个 page=-1 的请求，返回 422 + 标准 JSON + trace_id
   - 查一个不存在的成员，返回 404 + 标准 JSON + trace_id
   - 不带 Token 访问，返回 401 + 标准 JSON + trace_id
   - 普通成员调删除，返回 403 + 标准 JSON + trace_id
   - 检查响应头都有 X-Trace-Id
6. 编写测试用例验证所有错误格式一致。
7. 运行 mypy 和 ruff 确保 0 错误 0 警告。
```

**本阶段红线提醒：**
- ⚠️ 红线13：500 错误绝对不能返回堆栈信息。
- ⚠️ 红线14：每个错误响应必须带 trace_id。

---

## 5. 安全与合规

### 5.1 密码安全
- 密码使用 bcrypt（cost=12）加密存储，自动加盐。
- 禁止明文存储、明文传输（生产环境必须 HTTPS）、日志打印密码。
- 禁止使用 MD5、SHA1、SHA256 等快速哈希算法。
- 密码长度至少 8 位。

### 5.2 Token 安全
- Access Token 有效期 15 分钟，Refresh Token 有效期 7 天。
- JWT Secret 从环境变量 `JWT_SECRET` 读取，禁止硬编码。
- `.env` 文件必须加入 `.gitignore`。
- Payload 只放 `user_id`、`role`、`exp`、`type`，禁止放密码。
- 实现 Refresh Token 旋转机制，检测重放攻击。

### 5.3 权限控制
- 写操作（POST/PUT/DELETE）必须校验管理员角色。
- 只读操作（GET）对团队所有登录成员开放。
- 所有查询必须带 `team_id` 过滤，多租户隔离是铁律。
- `team_id` 从认证信息获取，不信任请求路径参数。
- 越权访问返回 404，不泄露资源是否存在。

### 5.4 登录安全
- 登录失败统一返回"用户名或密码错误"，不区分邮箱不存在还是密码错误。
- 注册时邮箱已存在不明确提示，防止枚举攻击。
- 错误信息不暴露堆栈、数据库结构、内部路径。

### 5.5 CORS 安全
- **严禁使用通配符 `"*"`**。
- 白名单从配置文件读取，只允许前端域名。
- 开发环境：`http://localhost:3000`、`http://localhost:5173`。
- 生产环境只允许前端正式域名。

### 5.6 错误信息安全
- 所有错误遵循 RFC 7807 格式。
- 500 错误的 detail 不泄露堆栈、数据库结构、内部路径。
- 每个错误响应带 trace_id，便于排查。
- 统一用 HTTPException 抛出，不返回 traceback。

---

## 6. AI 协作约定

### 6.1 与 AI 协作的工作流
1. 每个阶段开始前，复制对应阶段的"执行指令"给 AI。
2. AI 完成后，按"验收标准"逐项验证。
3. 验收不通过则反馈问题，让 AI 修复后再验证。
4. 验收通过后再进入下一阶段，拒绝跳跃式开发。
5. Agent 仅负责代码生成，人工把控架构逻辑。
6. 每阶段代码需人工 Review，严禁直接合并未验证代码。

### 6.2 AI 必须遵守的规则
- 密码必须用 bcrypt（cost=12）加密，禁止明文。
- JWT Secret 必须走环境变量，禁止硬编码。
- Token 必须有过期时间，Access 15min，Refresh 7d。
- Payload 只放 user_id、role、exp、type，禁止放密码。
- 登录错误统一回复，不区分具体原因。
- 所有查询必须带 team_id 过滤。
- CORS 用白名单，禁止 `"*"`。
- 错误不暴露堆栈，统一 RFC 7807 格式。
- 所有路由用 `async def`。
- 单文件不超过 500 行，超过主动拆分。
- 写完代码后自动运行 ruff 和 mypy 检查。
- 功能写完必须同步写测试，覆盖正常/无Token/过期Token/权限不足场景。

### 6.3 上下文管理
- AI 每次只处理一个阶段，不要跨阶段操作。
- 如果 AI 丢失上下文，让它重新读取 Claudeday3.md 获取安全规矩。
- 安全相关操作必须在本文件（Claudeday3.md）的约束下进行。

---

## 7. 常见陷阱（14 条红线）

> 这 14 条红线来自 specday3.md，任何阶段都不可违反。

| # | 红线 | 陷阱描述 | 后果 | 规避措施 |
|---|------|----------|------|----------|
| 1 | 密码绝不明文 | 密码明文存数据库或打印日志 | 数据库泄露后所有用户密码暴露 | bcrypt cost=12 加密，禁止日志打印密码 |
| 2 | 禁止快速哈希 | 用 MD5 或 SHA 哈希密码 | GPU 暴力破解极快 | 必须用 bcrypt cost=12 |
| 3 | 登录错误统一回复 | 分情况提示"邮箱不存在"/"密码错误" | 攻击者可枚举出哪些邮箱已注册 | 统一返回"用户名或密码错误" |
| 4 | JWT Secret 走环境变量 | Secret 硬编码在代码里并提交 GitHub | 密钥泄漏，任何人都能伪造 Token | 用环境变量，.env 加 .gitignore |
| 5 | Token 必须有过期时间 | JWT 没有过期时间 | Token 永久有效，泄漏了永远能用 | Access 15min，Refresh 7d |
| 6 | Payload 最小化 | Payload 里塞了密码 | JWT 是 base64 编码，任何人都能解码 | Payload 只放 user_id、role、exp、type |
| 7 | Refresh Token 旋转 | Token 被盗了没反应 | 攻击者可以一直用 | 加 refresh 旋转，旧 Token 再次使用整条链作废 |
| 8 | 所有接口必须认证 | 接口漏加认证依赖 | 任何人都能调接口 | 所有受保护接口加 Depends(get_current_user) |
| 9 | 写操作必须校验角色 | 只校验登录不校验角色 | 普通成员能删数据 | 写操作加 Depends(require_admin) |
| 10 | 403 不泄露资源存在 | 403 提示"资源存在但无权限" | 攻击者能探测资源 | 越权访问返回 404 |
| 11 | team_id 从认证获取 | 信任请求路径中的 team_id | 篡改 team_id 越权访问 | 从 JWT/当前用户获取 team_id |
| 12 | 查询必须带 team_id | 只校验角色不校验归属（IDOR） | 普通成员能看到别的团队数据 | 查数据必须带 team_id 过滤 |
| 13 | 错误不暴露堆栈 | 错误信息返回 traceback | 攻击者能看到代码结构 | 统一用 HTTPException，500 不泄露细节 |
| 14 | 每个错误带 trace_id | 错误响应没有追踪号 | 出问题无法从日志定位 | trace_id 中间件自动注入，错误响应体包含 |

---

## 8. 决策日志 (ADR)

> Architecture Decision Records — 记录关键安全技术决策及其原因。

### ADR-001：使用 bcrypt 加密密码
- **状态**：已采纳
- **决定**：使用 bcrypt 算法（cost=12）加密密码
- **原因**：bcrypt 自带盐值、计算速度可调（cost factor），能有效抵抗 GPU 暴力破解；MD5/SHA 等快速哈希不安全
- **spec 依据**：技术栈第1条，注意事项第3条

### ADR-002：JWT 双 Token 方案
- **状态**：已采纳
- **决定**：Access Token 15min + Refresh Token 7d
- **原因**：Access Token 短期有效降低泄漏风险，Refresh Token 长期有效用于续期，用户无需频繁登录
- **spec 依据**：技术栈第2条，注意事项第2条

### ADR-003：JWT 使用 HS256 算法
- **状态**：已采纳
- **决定**：JWT 签名使用 HS256 算法，密钥从环境变量 JWT_SECRET 读取
- **原因**：HS256 实现简单、性能好，适合单体应用；密钥走环境变量防止硬编码泄漏
- **spec 依据**：技术栈第3、4条

### ADR-004：Refresh Token 旋转机制
- **状态**：已采纳
- **决定**：实现 Refresh Token 旋转，旧 Token 再次使用时整条链作废
- **原因**：检测重放攻击，Token 被盗后攻击者再次使用会触发作废机制
- **spec 依据**：注意事项第8条

### ADR-005：FastAPI Depends 统一权限拦截
- **状态**：已采纳
- **决定**：使用 FastAPI 的 Depends() 做认证和角色校验的统一拦截
- **原因**：依赖注入是 FastAPI 原生机制，声明式、可复用、易于测试
- **spec 依据**：技术栈第5条

### ADR-006：行级权限通过 team_id 过滤
- **状态**：已采纳
- **决定**：所有查询带 team_id + owner_id 过滤，team_id 从认证信息获取
- **原因**：防止 IDOR（不安全的直接对象引用），确保多租户隔离
- **spec 依据**：技术栈第6条，注意事项第5条

### ADR-007：登录错误统一回复
- **状态**：已采纳
- **决定**：登录失败统一返回"用户名或密码错误"，不区分具体原因
- **原因**：防止攻击者枚举已注册邮箱
- **spec 依据**：业务要求第5条，注意事项第4条

### ADR-008：RFC 7807 错误格式 + trace_id
- **状态**：已采纳
- **决定**：所有错误响应遵循 RFC 7807 格式，包含 trace_id
- **原因**：标准化错误格式，前端统一处理，trace_id 便于线上问题排查
- **spec 依据**：S8 阶段要求

---

## 9. 测试要求

### 9.1 基本要求
- 每个安全功能必须有单元测试。
- 测试必须覆盖：正常、无 Token、过期 Token、权限不足四种场景。
- 测试多租户隔离：A 团队用户无法访问 B 团队数据。
- 全局覆盖率 ≥ 70%。

### 9.2 必测场景
| 场景类型 | 必须覆盖 |
|----------|----------|
| 密码加密 | 同一密码两次 hash 不同、正确密码验证通过、错误密码验证失败 |
| 注册 | 正常注册 201、邮箱格式错误 422、密码太短 422、密码已加密存储 |
| 登录 | 正确凭据返回双 Token、错误密码 401、不存在邮箱 401、统一错误信息 |
| Token 刷新 | 有效 Refresh 换新 Access、过期 Refresh 401、旧 Refresh 重放被拒 |
| 认证 | 无 Token 401、有效 Token 200、过期 Token 401、伪造 Token 401 |
| 角色授权 | 管理员写操作成功、普通成员写操作 403、普通成员读操作成功 |
| 行级权限 | 本团队数据可访问、跨团队数据 404、篡改 team_id 404 |
| 错误格式 | 401/403/404/422/500 均为 RFC 7807 格式、均带 trace_id |
| CORS | 白名单域名可访问、非白名单域名被拒、不允许 `"*"` |

### 9.3 测试命令
```bash
# 运行全部测试
pytest -v

# 运行安全相关测试
pytest tests/test_auth.py tests/test_security.py -v

# 查看测试覆盖率
pytest --cov=app --cov-report=term-missing
```

---

## 10. 安全审计体系

### 10.1 审计角色定义
**资深安全审查员**，严守 OWASP Top 10 + CWE 标准。

### 10.2 输出强制格式
每个漏洞必须按以下格式输出：

| 字段 | 说明 |
|------|------|
| 漏洞 ID | 唯一编号 |
| OWASP 编号 | 对应的 OWASP Top 10 编号 |
| 严重度 | Critical / High / Medium / Low |
| 行号 | 问题代码所在行号 |
| 修复方案 | 具体修复建议 |
| 验证用例 | 修复后的验证方法 |

### 10.3 必检 25 项

#### 认证授权（8 项）
1. 密码是否 bcrypt 加密（cost=12）
2. 是否存在弱密码策略（长度<8）
3. JWT Secret 是否走环境变量
4. Token 是否有过期时间
5. Access Token 是否 15min 过期
6. Refresh Token 是否 7d 过期
7. 是否实现 Refresh Token 旋转
8. 写操作是否校验管理员角色

#### 输入校验（5 项）
9. 邮箱格式是否校验
10. 密码长度是否校验
11. 分页参数是否校验（page/size 范围）
12. 路径参数 id 是否校验归属
13. 请求体是否用 Pydantic 严格校验

#### 密钥管理（4 项）
14. JWT_SECRET 是否硬编码
15. .env 是否在 .gitignore 中
16. 数据库密码是否走环境变量
17. API Key/Secret 是否走环境变量

#### 依赖审计（3 项）
18. 依赖包是否有已知漏洞（pip audit）
19. 是否使用了不安全的哈希算法（MD5/SHA1）
20. JWT 库是否使用最新稳定版

#### 其他（5 项）
21. CORS 是否设为 `"*"`
22. 错误信息是否泄露堆栈
23. 登录错误是否区分情况（枚举风险）
24. 查询是否带 team_id 过滤（IDOR）
25. JWT Payload 是否包含敏感信息

### 10.4 严重度分级
| 级别 | 修复时限 | 说明 |
|------|----------|------|
| Critical | 当天修复 | 直接导致系统被攻破、数据泄露 |
| High | 一周内修复 | 严重安全隐患，可能被利用 |
| Medium | 下个迭代修复 | 有风险但利用条件苛刻 |
| Low | 排期修复 | 安全最佳实践建议 |

### 10.5 强制规则
- **无把握项必须标记 ⚠️**，提交人工兜底审查。
- 审计输出结构化表格，可直接粘贴至 PR/MR 评论区。
- 对 AI 无把握的风险点强制标记，引入人工兜底审查。
- 兼顾效率与严谨，提升代码上线安全性。

---

## 11. 常用命令速查

```bash
# 安装安全相关依赖
pip install bcrypt pyjwt[crypto]

# 运行类型检查
mypy app/ --strict

# 运行代码风格检查
ruff check app/

# 运行全部测试
pytest -v

# 运行安全相关测试
pytest tests/test_auth.py tests/test_security.py -v

# 查看测试覆盖率
pytest --cov=app --cov-report=term-missing

# 检查依赖漏洞
pip audit

# 生成 JWT Secret（用于 .env）
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## 12. 文档要求

### 12.1 必须存在的文档
| 文件 | 位置 | 用途 |
|------|------|------|
| Claudeday3.md | 项目根目录 | 安全规范项目宪法（本文件） |
| specday3.md | 项目根目录 | 安全需求说明书 |
| .env.example | 项目根目录 | 环境变量模板（不含真实密钥） |
| .gitignore | 项目根目录 | 必须包含 .env |
### 12.2 .env.example 必须包含
```env
# JWT
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
```

### 12.3 README 必须包含（安全部分）
1. 认证机制说明（JWT 双 Token）
2. 如何注册和登录
3. 如何在请求中携带 Token（Authorization: Bearer <token>）
4. 权限模型说明（管理员 vs 普通成员）
5. 环境变量配置说明
6. 安全测试命令
