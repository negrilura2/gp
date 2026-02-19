# 使用 Node.js 构建镜像
FROM node:18-alpine

# 设置工作目录
WORKDIR /app

# 复制 package.json 和 package-lock.json
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制源代码
COPY . .

# 暴露端口 (Vite 默认 5173)
EXPOSE 5173

# 启动开发服务器
CMD ["npm", "run", "dev", "--", "--host"]
