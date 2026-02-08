# Docker 部署指南

## 快速开始

### 1. 准备部署目录（WSL）

在 WSL 中创建部署目录：

```bash
mkdir -p ~/docker/software/nanobot
cd ~/docker/software/nanobot
```

### 2. 复制部署文件

从项目仓库复制必要的文件：

```bash
# 复制 docker-compose.yml
cp /path/to/nanobot/docker-compose.yml .

# 复制 .env.example 并配置
cp /path/to/nanobot/.env.example .env
nano .env
```

### 3. 准备配置文件

创建 nanobot 配置目录并添加配置文件：

```bash
mkdir -p .nanobot .claude
nano .nanobot/config.json
```

配置示例：

```json
{
  "providers": {
    "anthropic": {
      "apiKey": "your-api-key",
      "apiBase": "http://your-api-base"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-5-20250929"
    }
  },
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "your-app-id",
      "appSecret": "your-app-secret",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": []
    }
  },
  "tools": {
    "claudeCode": {
      "enabled": true,
      "command": "claude",
      "allowedTools": ["Bash", "Read", "Edit", "Write", "Glob", "Grep"],
      "model": ""
    }
  }
}
```

### 2. 配置环境变量

复制环境变量模板并填入你的配置：

```bash
cp .env.example .env
nano .env
```

编辑 `.env` 文件：

```bash
ANTHROPIC_API_KEY=your-api-key-here
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

**注意**：`.env` 文件已在 `.gitignore` 中，不会被提交到 Git。

### 4. 启动容器

```bash
cd ~/docker/software/nanobot
docker compose up -d
```

### 5. 查看日志

```bash
docker logs -f nanobot
```

### 6. 停止容器

```bash
docker compose down
```

## 版本历史

- **v1.2.0**: 内置 Claude Code CLI，支持在容器内直接调用
- **v1.1.0**: 修复 Anthropic 自定义 API 基础 URL 和 LiteLLM 提供商检测问题
- **v1.0.0**: 初始版本，支持飞书和 QQ 频道

## 特性

- ✅ 内置 Claude Code CLI (v2.1.34)
- ✅ 支持飞书 WebSocket 长连接
- ✅ 支持自定义 Anthropic API 中转
- ✅ 会话持久化（使用 Docker volumes）
- ✅ 工作空间持久化

## 容器管理

### 重启容器

```bash
docker restart nanobot
```

### 进入容器

```bash
docker exec -it nanobot bash
```

### 查看 Claude Code 版本

```bash
docker exec nanobot claude --version
```

### 更新镜像

```bash
# 构建新镜像
docker build -t nanobot:latest .

# 重新创建容器
docker compose up -d --force-recreate
```

## 数据持久化

容器使用以下目录持久化数据（相对路径）：

- `./.nanobot`: nanobot 配置和数据
  - `config.json`: 配置文件
  - `sessions/`: 会话历史
  - `workspace/`: 工作空间
  - `cron/`: 定时任务
- `./.claude`: Claude Code 配置和项目
  - Claude Code CLI 的配置、会话和项目数据

### 推荐部署位置

```
~/docker/software/nanobot/
├── docker-compose.yml       # Docker Compose 配置
├── .env                     # 环境变量（API 密钥）
├── .nanobot/               # nanobot 数据目录
│   ├── config.json
│   ├── sessions/
│   ├── workspace/
│   └── cron/
└── .claude/                # Claude Code 数据目录
    ├── projects/
    ├── todos/
    └── debug/
```

### 访问配置文件

在 WSL 中直接编辑配置：

```bash
# 编辑 nanobot 配置
nano ~/docker/software/nanobot/.nanobot/config.json

# 查看 Claude Code 项目
ls ~/docker/software/nanobot/.claude/projects/
```

## 故障排查

### 查看实时日志

```bash
docker logs -f nanobot
```

### 检查容器状态

```bash
docker ps -a | grep nanobot
```

### 检查配置文件

```bash
docker exec nanobot cat /root/.nanobot/config.json
```

### 测试 Claude Code

```bash
docker exec -it nanobot claude -p "echo hello"
```
