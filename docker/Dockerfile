# syntax=docker/dockerfile:1.7

# ===================================
# A\u80a1\u81ea\u9009\u80a1\u667a\u80fd\u5206\u6790\u7cfb\u7edf - Docker \u955c\u50cf
# ===================================
# \u591a\u9636\u6bb5\u6784\u5efa：\u524d\u7aef\u6253\u5305 + \u540e\u7aef\u8fd0\u884c

FROM node:20-slim AS web-builder

WORKDIR /app/apps/dsa-web

COPY apps/dsa-web/package.json apps/dsa-web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY apps/dsa-web/ ./
RUN npm run build

# Pin to bookworm: wkhtmltopdf was removed from Debian testing (2025)
FROM python:3.11-slim-bookworm

# \u8bbe\u7f6e\u5de5\u4f5c\u76ee\u5f55
WORKDIR /app

# \u8bbe\u7f6e\u65f6\u533a\u4e3a\u4e0a\u6d77
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# \u5b89\u88c5\u7cfb\u7edf\u4f9d\u8d56（wkhtmltopdf \u542b wkhtmltoimage，\u7528\u4e8e Markdown \u8f6c\u56fe\u7247 Issue #289）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    git \
    gosu \
    wkhtmltopdf \
    fontconfig \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# \u521b\u5efa\u975e root \u7528\u6237 (UID 1000)
RUN groupadd -g 1000 dsa && \
    useradd -u 1000 -g dsa -m dsa

# \u590d\u5236\u4f9d\u8d56\u6587\u4ef6
COPY requirements.txt .

# \u5b89\u88c5 Python \u4f9d\u8d56
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

# \u590d\u5236\u5e94\u7528\u4ee3\u7801
COPY *.py ./
COPY api/ ./api/
COPY data_provider/ ./data_provider/
COPY bot/ ./bot/
COPY src/ ./src/
COPY strategies/ ./strategies/
COPY --from=web-builder /app/static ./static/
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Verify the bundled AlphaSift adapter from requirements.
RUN python -c "import alphasift.dsa_adapter"

# \u786e\u4fdd\u6570\u636e\u76ee\u5f55\u5b58\u5728\u5e76\u6388\u6743\u7ed9 non-root \u7528\u6237
RUN mkdir -p /app/data /app/logs /app/reports && \
    chown -R dsa:dsa /app && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

# efinance \u5c06\u641c\u7d22\u7f13\u5b58（search-cache.json）\u5199\u5165\u81ea\u8eab\u5b89\u88c5\u5305\u5185\u7684 data \u76ee\u5f55，
# \u8be5\u76ee\u5f55\u9ed8\u8ba4\u5f52 root \u6240\u6709；\u5bb9\u5668\u4ee5\u975e root \u7528\u6237 dsa \u8fd0\u884c\u65f6\u5199\u5165\u4f1a PermissionError，
# \u5bfc\u81f4 efinance \u6570\u636e\u6e90\u6bcf\u6b21\u6293\u53d6 A \u80a1\u6570\u636e\u90fd\u5931\u8d25\u5e76\u964d\u7ea7。\u9884\u7f6e\u76ee\u5f55\u5c5e\u4e3b\u7ed9 dsa \u4fee\u590d\u6b64\u95ee\u9898。
# \u52a8\u6001\u89e3\u6790\u8def\u5f84，\u907f\u514d\u5199\u6b7b Python \u7248\u672c\u76ee\u5f55。
RUN EF_DATA_DIR="$(python -c 'import efinance, pathlib; print(pathlib.Path(efinance.__file__).parent / "data")')" && \
    mkdir -p "$EF_DATA_DIR" && \
    chown -R dsa:dsa "$EF_DATA_DIR"

# \u8bbe\u7f6e\u73af\u5883\u53d8\u91cf\u9ed8\u8ba4\u503c
ENV PYTHONUNBUFFERED=1
ENV LOG_DIR=/app/logs
ENV DATABASE_PATH=/app/data/stock_analysis.db
# Web/API service
ENV WEBUI_HOST=0.0.0.0
ENV API_PORT=8000

# \u66b4\u9732 API \u7aef\u53e3
EXPOSE 8000

# \u6570\u636e\u5377（\u6301\u4e45\u5316\u6570\u636e）
VOLUME ["/app/data", "/app/logs", "/app/reports"]

# \u5065\u5eb7\u68c0\u67e5（FastAPI \u6a21\u5f0f）
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || curl -f http://localhost:8000/health \
    || python -c "import sys; sys.exit(0)"

# \u542f\u52a8\u5165\u53e3\u5148\u4fee\u590d bind mount \u76ee\u5f55\u6743\u9650，\u518d\u964d\u6743\u4e3a dsa \u6267\u884c\u5e94\u7528；
# \u6587\u6863\u5316 docker-compose exec \u547d\u4ee4\u9700\u663e\u5f0f\u4f7f\u7528 -u dsa，\u907f\u514d\u624b\u52a8\u8fdb\u7a0b\u5199\u5165 root-owned \u6587\u4ef6。
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# \u9ed8\u8ba4\u547d\u4ee4（\u53ef\u88ab\u8986\u76d6）
CMD ["python", "main.py", "--schedule"]
