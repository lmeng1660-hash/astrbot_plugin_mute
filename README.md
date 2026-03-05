<div align="center">
  <img src="logo.jpg" alt="智能回复决策" width="120">
  <h1>astrbot_plugin_mute</h1>
  <p>让大模型自主决定是否回复。</p>
</div>

## 功能

当消息触发 LLM 时，本插件会在 system_prompt 中注入一段提示，要求 LLM 用 `[REPLY]` 或 `[PASS]` 标记来表明是否回复。

- `[REPLY]你好啊` → 发送"你好啊"
- `[PASS]` → 沉默，不发送任何消息
- 既没有 `[REPLY]` 也没有 `[PASS]` → 默认放行原文回复（可配置为丢弃）

## 工作原理

本插件通过 AstrBot 的中间件钩子实现：

1. **on_llm_request** — LLM 生成前，在 system_prompt 末尾追加判断提示
2. **on_llm_response** — LLM 生成后，解析标记：`[REPLY]` 提取内容，`[PASS]` 拦截，无标记则按配置放行或丢弃
3. **on_decorating_result** — 消息发送前，确保被拦截的空消息不会发出

## 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `skip_at` | bool | `false` | 被@时跳过判断，直接回复。关闭则被@也可以不回复 |
| `skip_private` | bool | `true` | 私聊时跳过判断，直接回复 |
| `custom_hint` | string | `""` | 自定义提示词，留空使用默认提示 |
| `fallback_reply` | bool | `true` | LLM未输出标记时，放行原文回复。关闭则丢弃无标记的回复 |

## 默认提示词

```
你可以自主决定是否回复这条消息。
如果你想回复，请在回复内容的最开头加上 [REPLY] 标记，然后紧跟你的回复内容。
如果你认为不需要回复（比如别人之间在对话、消息跟你无关、或者你没什么想说的），请只回复 [PASS]，不要输出任何其他内容。
你必须以 [REPLY] 或 [PASS] 开头，不要输出任何思考过程。
示例：
- 想回复：[REPLY]你好啊
- 不回复：[PASS]
```

## 适用场景

- 群聊中机器人不想对每条消息都回复
- 让 LLM 根据上下文自行判断是否需要参与对话
- 搭配其他角色扮演/人设插件使用，赋予"已读不回"能力

## 安装

将本插件目录放入 AstrBot 的 `data/plugins/` 下，重启 AstrBot 即可。

## 注意事项

- 本插件为轻量中间件，通过 `[REPLY]`/`[PASS]` 标记控制回复行为
- LLM 未输出任何标记时，默认放行原文回复；如需丢弃，可将 `fallback_reply` 设为 `false`
- 如果 LLM 对标记指令的遵循度不高，可通过 `custom_hint` 调整提示词
- 与其他插件兼容，不会冲突
