FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预下载 Embedding 模型（设置 BUILD_EMBEDDING=1 启用语义搜索）
ARG BUILD_EMBEDDING=
ARG HF_ENDPOINT=https://hf-mirror.com
RUN if [ "$BUILD_EMBEDDING" = "1" ]; then \
        pip install --no-cache-dir "sentence-transformers>=3.0,<4.0" && \
        python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')" && \
        echo "✓ Embedding model pre-downloaded"; \
    fi

# 复制项目文件
COPY . .

# 创建上传目录
RUN mkdir -p uploads

# 暴露端口
EXPOSE 5000

# 使用 gunicorn 启动
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "run:app"]
