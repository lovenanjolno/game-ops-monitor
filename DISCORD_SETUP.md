# Discord 接入指南

## 为什么必须用 Bot

1. Discord 不支持普通用户程序化读取消息（违反 ToS，会被封号）
2. Bot 是 Discord 官方支持的自动化身份
3. Bot token 独立，泄露不影响个人账号
4. Bot 可以 7×24 在线，不影响你正常用 Discord

## 5 步创建你的 Bot

### 1. 创建 Application

访问 https://discord.com/developers/applications
- 点击 "New Application"
- 名字随便取，比如 "GameOpsMonitor"
- 同意 ToS

### 2. 创建 Bot

- 左侧菜单 → Bot
- 点击 "Add Bot"
- **重要**：点击 "Reset Token" → 复制保存（只显示一次！）
- 打开这三个 Privileged Intents：
  - ✅ MESSAGE CONTENT INTENT ← 关键！没有它读不到消息内容
  - ✅ SERVER MEMBERS INTENT（可选，用于查用户）
  - ✅ PRESENCE INTENT（可选）

### 3. 邀请 Bot 到服务器

- 左侧菜单 → OAuth2 → URL Generator
- Scopes 勾选：`bot`
- Bot Permissions 勾选：
  - ✅ View Channels
  - ✅ Read Message History
  - ✅ Send Messages（可选，用于回复）
- 复制生成的 URL，在浏览器打开
- 选择你的服务器，授权

### 4. 配置项目

编辑项目根目录的 `.env`：
```
DISCORD_BOT_TOKEN=刚才复制的token
```

编辑 `config.yaml`：
```yaml
sources:
  discord:
    enabled: true
    targets:
      - guild_id: "123456789012345678"  # 服务器 ID（右键服务器图标 → 复制 ID）
        guild_name: "我的官方服务器"
        name: "客诉频道"
        channel_id: "987654321098765432"  # 频道 ID（右键频道 → 复制 ID）
        enabled: true
```

### 5. 启用开发者模式

Discord 设置 → 高级 → 开发者模式 ✅
然后右键服务器/频道就能看到 "复制 ID"。

## 实现代码

打开 `src/sources/discord.py`，参考文件中的 docstring 示例，实现 `fetch` 和 `listen` 方法。

主流程（CLI、未来的 GUI）**不需要任何改动**——会自动发现 Discord 数据源。

## 后续：实时监听

Discord 比 Google Play 强的地方是支持实时监听。可以在 `DiscordSource.listen()` 里实现：

```python
async def listen(self, target_id, callback, **kwargs):
    @client.event
    async def on_message(message):
        if str(message.channel.id) == target_id:
            raw = self._to_raw_message(message)
            callback(raw)  # 实时推给分类器
```

GUI 可以用 WebSocket / Signal 推送到桌面端，实现真正的"实时告警"。

## 常见问题

**Q: Bot 看不到消息？**
A: 检查 MESSAGE CONTENT INTENT 是否打开。

**Q: "Missing Access" 错误？**
A: Bot 没被邀请到服务器，或频道权限不够。

**Q: 多频道怎么配置？**
A: `targets` 是数组，每个元素是一个频道。

**Q: 能监听多服务器吗？**
A: 可以，一个 Bot 可以加入多个服务器（最多 2000 个）。
