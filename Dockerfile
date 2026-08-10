# syntax=docker/dockerfile:1
FROM python:3.12-alpine AS builder

WORKDIR /build

# 配置 Alpine 镜像源（使用清华镜像加速）
RUN sed -i 's|dl-cdn.alpinelinux.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apk/repositories && \
    apk add --no-cache gcc musl-dev

# 创建虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 配置 pip 镜像源并升级 pip
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装运行时依赖
# --no-compile 跳过 .pyc 生成以减小体积
RUN pip install --no-cache-dir --no-compile -i https://pypi.tuna.tsinghua.edu.cn/simple \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "pydantic>=2.9.0" \
    "pydantic-settings>=2.4.0" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "psycopg[binary]>=3.2.0" \
    "email-validator>=2.0.0" \
    "alembic>=1.13.0" \
    "bcrypt>=4.0.0" \
    "PyJWT>=2.8.0"

# 深度清理虚拟环境
RUN find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
    find /opt/venv -type f -name "*.pyc" -delete; \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null; \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null; \
    find /opt/venv -name "*.pyi" -delete; \
    rm -rf /opt/venv/share/man /opt/venv/share/doc; \
    find /opt/venv -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true

# ========== 运行时阶段 ==========
FROM python:3.12-alpine

WORKDIR /app

# 配置 Alpine 镜像源
RUN sed -i 's|dl-cdn.alpinelinux.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apk/repositories

# asyncpg 自带 C 扩展，不依赖 libpq，无需安装额外系统包
# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 创建非 root 用户
RUN addgroup -S appuser && adduser -S appuser -G appuser

# 仅复制运行时所需的应用代码
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY run.py ./

# 设置目录权限并清理 pyc
RUN chown -R appuser:appuser /app && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
    find /app -type f -name "*.pyc" -delete

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
