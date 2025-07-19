from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import json
import random
import os
from datetime import datetime, date
from typing import Dict, List, Optional
import aiofiles

@register(
    "astrbot_plugin_daily_fortune",
    "xSapientia",
    "今日人品测试插件 - 测试你的今日运势",
    "0.1.1",
    "https://github.com/xSapientia/astrbot_plugin_daily_fortune",
)
class DailyFortunePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.context = context
        self.config = config if config else AstrBotConfig()

        # 设置默认配置
        if not self.config:
            self.config = {
                "enable_plugin": True,
                "min_fortune": 0,
                "max_fortune": 100,
                "use_llm": True,
                "use_forward_message": False,
                "process_prompt": "你是一个神秘的占卜师，正在使用水晶球为用户[{name}]占卜今日人品值。请描述水晶球中浮现的画面和占卜过程，最后揭示今日人品值为{fortune}。描述要神秘且富有画面感，50字以内。",
                "advice_prompt": "用户[{name}]的今日人品值为{fortune}，运势等级为{level}。请根据这个人品值给出今日建议或吐槽，要幽默风趣，50字以内。"
            }

        # 数据文件路径
        self.data_dir = os.path.join("data", "daily_fortune")
        self.fortune_file = os.path.join(self.data_dir, "fortunes.json")
        self.history_file = os.path.join(self.data_dir, "history.json")

        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)

        # 运势等级定义
        self.fortune_levels = {
            (0, 0): "极其倒霉",
            (1, 2): "倒大霉",
            (3, 10): "十分不顺",
            (11, 20): "略微不顺",
            (21, 30): "正常运气",
            (31, 98): "好运",
            (99, 99): "极其好运",
            (100, 100): "万事皆允"
        }

        logger.info("今日人品插件 v0.1.1 加载成功！")

    async def load_data(self, file_path: str) -> dict:
        """异步加载JSON数据"""
        if not os.path.exists(file_path):
            return {}
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except Exception as e:
            logger.error(f"加载数据失败 {file_path}: {e}")
            return {}

    async def save_data(self, file_path: str, data: dict):
        """异步保存JSON数据"""
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"保存数据失败 {file_path}: {e}")

    def get_fortune_level(self, fortune: int) -> str:
        """获取运势等级"""
        for (min_val, max_val), level in self.fortune_levels.items():
            if min_val <= fortune <= max_val:
                return level
        return "正常运气"

    def get_today_key(self) -> str:
        """获取今日日期键"""
        return date.today().strftime("%Y-%m-%d")

    async def get_user_name(self, event: AstrMessageEvent) -> str:
        """获取用户名称"""
        name = event.get_sender_name()
        if not name or name == "未知":
            name = f"用户{event.get_sender_id()[-4:]}"
        return name

    @filter.command("jrrp", alias={"-jrrp", "今日人品"})
    async def daily_fortune(self, event: AstrMessageEvent):
        """查看今日人品"""
        if not self.config.get("enable_plugin", True):
            yield event.plain_result("今日人品插件已关闭")
            return

        user_id = event.get_sender_id()
        user_name = await self.get_user_name(event)
        today_key = self.get_today_key()

        # 加载今日人品数据
        fortunes = await self.load_data(self.fortune_file)

        # 检查用户今日是否已经测试过
        if today_key not in fortunes:
            fortunes[today_key] = {}

        if user_id in fortunes[today_key]:
            # 已经测试过，直接返回结果
            fortune_value = fortunes[today_key][user_id]["value"]
            level = self.get_fortune_level(fortune_value)

            if self.config.get("use_forward_message", False) and event.get_platform_name() == "aiocqhttp":
                # 使用合并转发
                messages = [
                    f"【{user_name}】今日人品已测试",
                    f"💎 人品值：{fortune_value}\n🔮 运势：{level}",
                    "✨ 记住，人品值只是参考，真正的运气掌握在自己手中！"
                ]
                yield self._build_forward_message(event, messages, user_name)
            else:
                # 普通消息
                result = f"【{user_name}】今日人品已测试\n"
                result += f"💎 人品值：{fortune_value}\n"
                result += f"🔮 运势：{level}\n"
                result += f"✨ 记住，人品值只是参考，真正的运气掌握在自己手中！"
                yield event.plain_result(result)
            return

        # 生成新的人品值
        min_val = self.config.get("min_fortune", 0)
        max_val = self.config.get("max_fortune", 100)
        fortune_value = random.randint(min_val, max_val)
        level = self.get_fortune_level(fortune_value)

        # 保存今日人品
        fortunes[today_key][user_id] = {
            "value": fortune_value,
            "name": user_name,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        await self.save_data(self.fortune_file, fortunes)

        # 保存到历史记录
        history = await self.load_data(self.history_file)
        if user_id not in history:
            history[user_id] = {}
        history[user_id][today_key] = {
            "value": fortune_value,
            "name": user_name
        }
        await self.save_data(self.history_file, history)

        # 构建回复
        if self.config.get("use_forward_message", False) and event.get_platform_name() == "aiocqhttp":
            messages = await self._build_fortune_messages(user_name, fortune_value, level)
            yield self._build_forward_message(event, messages, user_name)
        else:
            result = await self._build_fortune_text(user_name, fortune_value, level)
            yield event.plain_result(result)

    async def _build_fortune_messages(self, user_name: str, fortune_value: int, level: str) -> List[str]:
        """构建占卜消息列表"""
        messages = [f"【{user_name}】开始测试今日人品..."]

        # 如果启用LLM，生成占卜过程描述
        if self.config.get("use_llm", True) and self.context.get_using_provider():
            try:
                # 生成占卜过程
                process_prompt = self.config.get("process_prompt", "").format(
                    name=user_name,
                    fortune=fortune_value
                )
                process_resp = await self.context.get_using_provider().text_chat(
                    prompt=process_prompt,
                    session_id=None,
                    contexts=[],
                    system_prompt="你是一个神秘的占卜师，请用50字以内描述占卜过程。"
                )
                if process_resp.completion_text:
                    messages.append(f"🔮 {process_resp.completion_text}")

                # 生成建议
                advice_prompt = self.config.get("advice_prompt", "").format(
                    name=user_name,
                    fortune=fortune_value,
                    level=level
                )
                advice_resp = await self.context.get_using_provider().text_chat(
                    prompt=advice_prompt,
                    session_id=None,
                    contexts=[],
                    system_prompt="你是一个幽默的占卜师，请用50字以内给出建议或吐槽。"
                )
                advice = advice_resp.completion_text if advice_resp.completion_text else self._get_default_advice(fortune_value, level)
            except Exception as e:
                logger.error(f"LLM调用失败: {e}")
                messages.append("🔮 水晶球中浮现出神秘的光芒...")
                advice = self._get_default_advice(fortune_value, level)
        else:
            messages.append("🔮 水晶球中浮现出神秘的光芒...")
            advice = self._get_default_advice(fortune_value, level)

        # 添加结果
        result = f"💎 人品值：{fortune_value}\n✨ 运势：{level}"
        if advice:
            result += f"\n💬 建议：{advice}"
        messages.append(result)

        return messages

    async def _build_fortune_text(self, user_name: str, fortune_value: int, level: str) -> str:
        """构建占卜文本"""
        messages = await self._build_fortune_messages(user_name, fortune_value, level)
        return "\n\n".join(messages)

    def _build_forward_message(self, event: AstrMessageEvent, messages: List[str], user_name: str):
        """构建合并转发消息"""
        try:
            from astrbot.api.message_components import Node, Plain

            nodes = []
            for msg in messages:
                node = Node(
                    uin=event.get_self_id(),
                    name="占卜师",
                    content=[Plain(msg)]
                )
                nodes.append(node)

            return event.chain_result(nodes)
        except Exception as e:
            logger.error(f"构建合并转发失败: {e}")
            # 失败时使用普通方式发送
            return event.plain_result("\n\n".join(messages))

    def _get_default_advice(self, fortune: int, level: str) -> str:
        """获取默认建议"""
        advice_map = {
            "极其倒霉": "今天还是躺平吧，啥也别干最安全！",
            "倒大霉": "建议今天低调行事，小心为妙。",
            "十分不顺": "多喝热水，保持微笑，会好起来的。",
            "略微不顺": "平常心对待，小挫折而已。",
            "正常运气": "普普通通的一天，按部就班就好。",
            "好运": "运气不错哦，可以试试买个彩票？",
            "极其好运": "天选之子！今天做什么都会顺利！",
            "万事皆允": "恭喜！今天你就是世界的主角！"
        }
        return advice_map.get(level, "保持平常心，做好自己。")

    @filter.command("jrrprank", alias={"人品排行", "jrrp排行"})
    async def fortune_rank(self, event: AstrMessageEvent):
        """查看群聊内今日人品排行"""
        if not self.config.get("enable_plugin", True):
            yield event.plain_result("今日人品插件已关闭")
            return

        if event.is_private_chat():
            yield event.plain_result("人品排行榜仅在群聊中可用")
            return

        today_key = self.get_today_key()
        fortunes = await self.load_data(self.fortune_file)

        if today_key not in fortunes or not fortunes[today_key]:
            yield event.plain_result("今天还没有人测试人品哦~")
            return

        # 获取并排序今日人品
        today_fortunes = fortunes[today_key]
        sorted_fortunes = sorted(
            today_fortunes.items(),
            key=lambda x: x[1]["value"],
            reverse=True
        )

        # 构建排行榜
        if self.config.get("use_forward_message", False) and event.get_platform_name() == "aiocqhttp":
            messages = [f"📊【今日人品排行榜】{today_key}"]

            medals = ["🥇", "🥈", "🥉"]
            rank_lines = []
            for idx, (user_id, data) in enumerate(sorted_fortunes[:10]):
                medal = medals[idx] if idx < 3 else f"{idx+1}."
                name = data["name"]
                value = data["value"]
                level = self.get_fortune_level(value)
                rank_lines.append(f"{medal} {name}: {value} ({level})")

            messages.append("\n".join(rank_lines))

            if len(sorted_fortunes) > 10:
                messages.append(f"...共 {len(sorted_fortunes)} 人已测试")

            yield self._build_forward_message(event, messages, "排行榜")
        else:
            result = f"📊【今日人品排行榜】{today_key}\n"
            result += "━━━━━━━━━━━━━━━\n"

            medals = ["🥇", "🥈", "🥉"]
            for idx, (user_id, data) in enumerate(sorted_fortunes[:10]):
                medal = medals[idx] if idx < 3 else f"{idx+1}."
                name = data["name"]
                value = data["value"]
                level = self.get_fortune_level(value)
                result += f"{medal} {name}: {value} ({level})\n"

            if len(sorted_fortunes) > 10:
                result += f"\n...共 {len(sorted_fortunes)} 人已测试"

            yield event.plain_result(result)

    @filter.command("jrrphistory", alias={"jrrphi", "人品历史"})
    async def fortune_history(self, event: AstrMessageEvent):
        """查看个人人品历史"""
        if not self.config.get("enable_plugin", True):
            yield event.plain_result("今日人品插件已关闭")
            return

        user_id = event.get_sender_id()
        user_name = await self.get_user_name(event)
        history = await self.load_data(self.history_file)

        if user_id not in history or not history[user_id]:
            yield event.plain_result(f"【{user_name}】还没有人品测试记录")
            return

        user_history = history[user_id]
        sorted_history = sorted(user_history.items(), reverse=True)[:10]

        # 计算统计信息
        all_values = [record["value"] for record in user_history.values()]
        avg_fortune = sum(all_values) / len(all_values)
        max_fortune = max(all_values)
        min_fortune = min(all_values)

        if self.config.get("use_forward_message", False) and event.get_platform_name() == "aiocqhttp":
            messages = [f"📈【{user_name}的人品历史】"]

            history_lines = []
            for date_key, data in sorted_history:
                value = data["value"]
                level = self.get_fortune_level(value)
                history_lines.append(f"📅 {date_key}: {value} ({level})")

            messages.append("\n".join(history_lines))

            stats = f"""📊 统计信息：
平均人品：{avg_fortune:.1f}
最高人品：{max_fortune}
最低人品：{min_fortune}
测试次数：{len(all_values)}"""

            messages.append(stats)

            yield self._build_forward_message(event, messages, user_name)
        else:
            result = f"📈【{user_name}的人品历史】\n"
            result += "━━━━━━━━━━━━━━━\n"

            for date_key, data in sorted_history:
                value = data["value"]
                level = self.get_fortune_level(value)
                result += f"📅 {date_key}: {value} ({level})\n"

            result += "\n📊 统计信息：\n"
            result += f"平均人品：{avg_fortune:.1f}\n"
            result += f"最高人品：{max_fortune}\n"
            result += f"最低人品：{min_fortune}\n"
            result += f"测试次数：{len(all_values)}"

            yield event.plain_result(result)

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("今日人品插件已卸载")
