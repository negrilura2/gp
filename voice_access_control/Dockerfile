# 使用官方 Python 3.9 镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (libsndfile 用于音频处理)
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 使用清华源加速 (可选，视网络情况而定)
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PROJECT_ROOT=/app
ENV PYTHONPATH=/app

# 暴露端口 (Django 默认)
EXPOSE 8000

# 默认启动命令 (可被 docker-compose 覆盖)
CMD ["python", "backend/manage.py", "runserver", "0.0.0.0:8000"]
