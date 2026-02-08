# QQ Channel 测试文档

## 测试环境要求

- Python 3.11+
- pytest >= 7.0.0
- pytest-asyncio >= 0.21.0

## 测试文件

- `tests/channels/test_qq.py` - QQ 渠道测试用例

## 测试覆盖范围

### 1. 基础功能测试 (TestQQChannelBasic)
- ✅ 渠道初始化
- ✅ 启动和停止
- ✅ 权限控制（allow_from）

### 2. WebSocket 连接测试 (TestQQChannelWebSocket)
- ⏳ WebSocket 连接到 NapCat
- ⏳ 断线重连
- ⏳ 错误处理

### 3. 消息处理测试 (TestQQChannelMessageHandling)
- ⏳ 接收私聊消息
- ⏳ 接收群聊消息
- ⏳ 发送文本消息

### 4. CQ 码解析测试 (TestQQChannelCQCode)
- ⏳ 解析图片 CQ 码
- ⏳ 解析 @ 提及 CQ 码
- ⏳ 解析表情 CQ 码
- ⏳ 解析混合 CQ 码

### 5. MessageBus 集成测试 (TestQQChannelIntegration)
- ✅ 消息发布到 bus
- ✅ 消息从 bus 消费
- ✅ 消息路由

### 6. 配置测试 (TestQQChannelConfig)
- ✅ 默认配置
- ✅ 自定义配置
- ✅ 配置验证

## 运行测试

### 运行所有测试
```bash
cd E:\code\nanobot
python -m pytest tests/channels/test_qq.py -v
```

### 运行特定测试类
```bash
python -m pytest tests/channels/test_qq.py::TestQQChannelBasic -v
```

### 运行特定测试方法
```bash
python -m pytest tests/channels/test_qq.py::TestQQChannelBasic::test_channel_initialization -v
```

### 运行并显示覆盖率
```bash
python -m pytest tests/channels/test_qq.py --cov=nanobot.channels.qq --cov-report=html
```

## 测试状态

- ✅ 已完成：基础测试框架和 Mock 测试
- ⏳ 待完成：需要实际 QQChannel 实现后移除 `@pytest.mark.skip` 标记

## 已知问题

1. **Python 版本问题**
   - 项目要求 Python 3.11+
   - 当前环境 Python 3.9.13
   - 需要升级 Python 版本

2. **依赖问题**
   - 需要安装 `pytest-asyncio` 用于异步测试
   - 运行：`pip install pytest-asyncio`

## 测试数据

### OneBot 11 消息示例

**私聊消息**：
```json
{
  "post_type": "message",
  "message_type": "private",
  "user_id": 123456,
  "message": "Hello, bot!",
  "message_id": 1001
}
```

**群聊消息**：
```json
{
  "post_type": "message",
  "message_type": "group",
  "user_id": 123456,
  "group_id": 987654,
  "message": "Hello, group!",
  "message_id": 1002
}
```

**CQ 码示例**：
- 图片：`[CQ:image,file=xxx.jpg,url=http://...]`
- @ 提及：`[CQ:at,qq=123456]`
- 表情：`[CQ:face,id=123]`

## 下一步

1. 等待 developer 完成 QQChannel 实现
2. 移除测试中的 `@pytest.mark.skip` 标记
3. 添加更多边界情况测试
4. 添加性能测试
5. 添加压力测试
