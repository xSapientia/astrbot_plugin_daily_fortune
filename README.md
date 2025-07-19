# 今日人品 AstrBot 插件

<div align="center">

[![Version](https://img.shields.io/badge/version-0.1.1-blue.svg)](https://github.com/xSapientia/astrbot_plugin_daily_fortune)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D3.4.0-green.svg)](https://github.com/Soulter/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

一个有趣的今日人品测试插件，让你的 AstrBot 成为神秘的占卜师！

</div>

## ✨ 功能特性

- 🎲 **每日人品测试** - 每人每天只能测试一次，获得 0-100 的人品值
- 🏆 **人品排行榜** - 查看群内今日人品排行榜（全局统计）
- 📊 **历史记录** - 查看个人人品历史和统计数据
- 🤖 **AI 占卜师** - 可选使用大语言模型生成个性化的占卜过程和建议
- 🛡️ **数据管理** - 支持管理员清除所有数据，用户清除个人数据
- ⚙️ **高度可配置** - 支持自定义人品值范围、提示词等

## 🎯 使用方法

### 基础指令

| 指令 | 别名 | 说明 | 权限 |
|------|------|------|------|
| `/jrrp` | `-jrrp`, `今日人品` | 测试今日人品值 | 所有人 |
| `/jrrprank` | `人品排行`, `jrrp排行` | 查看今日人品排行榜 | 仅群聊 |
| `/jrrphistory` | `/jrrphi`, `人品历史` | 查看个人历史记录 | 所有人 |
| `/jrrpreset` | `人品数据库清除` | 清除所有人品数据 | 管理员 |
| `/jrrpdel` | - | 清除个人人品数据 | 所有人 |

## ⚙️ 配置说明

插件支持在 AstrBot 管理面板中进行可视化配置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_plugin` | bool | true | 插件总开关 |
| `min_fortune` | int | 0 | 人品值下限 |
| `max_fortune` | int | 100 | 人品值上限 |
| `use_llm` | bool | true | 是否使用 LLM 生成占卜内容 |
| `process_prompt` | text | 见下方 | 占卜过程生成提示词 |
| `advice_prompt` | text | 见下方 | 建议生成提示词 |

### 默认提示词

**占卜过程提示词：**
```
你是一个神秘的占卜师，正在使用水晶球为用户[{name}]占卜今日人品值。
请描述水晶球中浮现的画面和占卜过程，最后揭示今日人品值为{fortune}。
描述要神秘且富有画面感，50字以内。
```

**建议提示词：**
```
用户[{name}]的今日人品值为{fortune}，运势等级为{level}。
请根据这个人品值给出今日建议或吐槽，要幽默风趣，50字以内。
```

支持的变量：
- `{name}` - 用户名称
- `{fortune}` - 人品值
- `{level}` - 运势等级

## 📊 人品值说明

| 人品值范围 | 运势等级 | 说明 |
|------------|----------|------|
| 0 | 极其倒霉 | 今天还是躺平吧... |
| 1-2 | 倒大霉 | 建议低调行事 |
| 3-10 | 十分不顺 | 保持微笑，会好起来的 |
| 11-20 | 略微不顺 | 平常心对待 |
| 21-30 | 正常运气 | 普普通通的一天 |
| 31-98 | 好运 | 运气不错哦！ |
| 99 | 极其好运 | 天选之子！ |
| 100 | 万事皆允 | 今天你就是世界的主角！ |

## 💾 数据存储

插件数据保存在以下位置：
- 人品数据：`data/plugin_data/astrbot_plugin_daily_fortune/fortunes.json`
- 历史记录：`data/plugin_data/astrbot_plugin_daily_fortune/history.json`
- 插件配置：`data/config/astrbot_plugin_daily_fortune_config.json`

## 🔧 高级特性

### 全局人品值
- 无论在私聊还是群聊中测试，每个用户的今日人品值都是全局一致的
- 排行榜会显示所有测试过的用户，不限于当前群组

### 防重复机制
- 采用多重保护机制防止消息重复发送
- 5秒内的重复请求会被自动忽略

### 数据安全
- 管理员清除数据需要二次确认
- 用户只能清除自己的数据
- 插件卸载时会自动清理所有相关文件

## 🐛 故障排除

### 插件无响应
1. 检查插件是否已启用
2. 确认指令格式是否正确
3. 查看 AstrBot 日志是否有错误信息

### LLM 功能不工作
1. 确认已配置大语言模型提供商
2. 检查 `use_llm` 配置是否开启
3. 查看提示词配置是否正确

### 数据丢失
- 数据文件保存在 `data/plugin_data` 目录下
- 更新插件不会影响数据
- 只有卸载插件或手动清除才会删除数据

## 📝 更新日志

### v0.1.1 (2024-12-26)
- ✅ 实现基础的今日人品测试功能
- ✅ 添加人品排行榜（全局统计）
- ✅ 支持查看个人历史记录
- ✅ 集成 LLM 生成占卜内容
- ✅ 添加数据管理功能
- ✅ 实现防重复发送机制
- ✅ 优化数据存储路径

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发指南

1. Fork 本仓库
2. 创建新的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的修改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 👨‍💻 作者

- **xSapientia** - *Initial work* - [GitHub](https://github.com/xSapientia)

## 🙏 致谢

- 感谢 [AstrBot](https://github.com/Soulter/AstrBot) 项目提供的优秀框架
- 感谢所有提出建议和反馈的用户

---

<div align="center">

如果这个插件对你有帮助，请给个 ⭐ Star！

[报告问题](https://github.com/xSapientia/astrbot_plugin_daily_fortune/issues) · [功能建议](https://github.com/xSapientia/astrbot_plugin_daily_fortune/issues) · [查看更多插件](https://github.com/xSapientia)

</div>
