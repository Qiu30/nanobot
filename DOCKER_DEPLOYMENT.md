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
```

### 3. 配置 Claude Code

创建 Claude Code 配置文件：

```bash
mkdir -p .claude
nano .claude/settings.json
```

配置示例：

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "true",
    "ANTHROPIC_BASE_URL": "http://your-api-base/",
    "ANTHROPIC_API_KEY": "your-api-key"
  },
  "includeCoAuthoredBy": false
}
```

**注意**：
- Claude Code 会自动读取 `.claude/settings.json` 中的配置
- `ANTHROPIC_API_KEY`: 你的 API 密钥
- `ANTHROPIC_BASE_URL`: API 基础 URL（可选）

### 4. 准备 nanobot 配置文件

### 4. 准备 nanobot 配置文件

创建 nanobot 配置目录并添加配置文件：

```bash
mkdir -p .nanobot
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

### 5. 启动容器

```bash
cd ~/docker/software/nanobot
docker compose up -d
```

### 6. 查看日志

```bash
docker logs -f nanobot
```

### 7. 停止容器

```bash
docker compose down
```

## 版本历史

- **v1.4.0**: 新增会话复用功能，自动维护聊天上下文
- **v1.2.0**: 内置 Claude Code CLI，支持在容器内直接调用
- **v1.1.0**: 修复 Anthropic 自定义 API 基础 URL 和 LiteLLM 提供商检测问题
- **v1.0.0**: 初始版本，支持飞书和 QQ 频道

## 特性

- ✅ 内置 Claude Code CLI (v2.1.34)
- ✅ 支持飞书 WebSocket 长连接
- ✅ 支持自定义 Anthropic API 中转
- ✅ 会话持久化（使用 Docker volumes）
- ✅ 工作空间持久化
- ✅ **会话复用**：自动维护聊天上下文，无需手动管理 session

## 会话复用功能

### 功能说明

从 v1.4.0 开始，nanobot 支持会话复用功能，为每个聊天会话自动维护上下文：

- **自动上下文维护**：每个聊天会话（如飞书对话）会自动保持上下文连续性
- **无需手动管理**：无需手动创建或管理 session，系统自动处理
- **智能过期机制**：会话在 1 小时无活动后自动过期，释放资源

### 使用说明

#### 会话生命周期

1. **会话创建**：当用户首次发送消息时，系统自动创建会话
2. **上下文保持**：在会话有效期内，所有对话都会保持上下文连续性
3. **自动续期**：每次交互都会刷新会话过期时间
4. **自动过期**：1 小时无活动后，会话自动清理

#### 如何利用会话上下文

- **连续对话**：可以在多轮对话中引用之前的内容
  - 例如："帮我修改刚才那个文件"
  - 例如："继续上一个任务"

- **上下文记忆**：AI 会记住当前会话中的：
  - 已讨论的问题
  - 已执行的操作
  - 工作目录和文件状态

- **新会话开始**：如果需要开始全新的对话，可以：
  - 等待 1 小时后会话自动过期
  - 或明确告知 AI "开始新的会话"

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
