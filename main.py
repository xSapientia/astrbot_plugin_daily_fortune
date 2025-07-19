from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import json
import random
import os
import shutil
from datetime import datetime, date
from typing import Dict, List, Optional
import aiofiles
import asyncio
import threading

# 全局锁，防止并发执行
_fortune_lock = asyncio.Lock()

@register(
    "astrbot_plugin_daily_fortune",
    "xSapientia",
    "今日人品测试插件 - 测试你的今日运势",
    "0.1.2",
    "https://github.com/xSapientia/astrbot_plugin_daily_fortune",
)
class DailyFortunePlugin(Star):
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, context: Context, config: AstrBotConfig = None):
        # 防止重复初始化
        if DailyFortunePlugin._initialized:
            logger.warning("DailyFortunePlugin already initialized, skipping...")
            return

        super().__init__(context)
        self.context = context
        self.config = config if config else {}

        # 设置默认配置
        self.config.setdefault("enable_plugin", True)
        self.config.setdefault("min_fortune", 0)
        self.config.setdefault("max_fortune", 100)
        self.config.setdefault("use_llm", True)
        self.config.setdefault("process_prompt", "你是一个神秘的占卜师，正在使用水晶球为用户[{name}]占卜今日人品值。请描述水晶球中浮现的画面和占卜过程，最后揭示今日人品值为{fortune}。描述要神秘且富有画面感，50字以内。")
        self.config.setdefault("advice_prompt", "用户[{name}]的今日人品值为{fortune}，运势等级为{level}。请根据这个人品值给出今日建议或吐槽，要幽默风趣，50字以内。")

        # 数据文件路径
        self.data_dir = os.path.join("data", "plugin_data", "astrbot_plugin_daily_fortune")
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

        # 请求去重
        self._request_cache = {}
        self._cache_timeout = 5  # 5秒内相同请求视为重复

        DailyFortunePlugin._initialized = True
        logger.info("今日人品插件 v0.1.2 加载成功！")

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

    def _check_duplicate_request(self, user_id: str, command: str) -> bool:
        """检查是否是重复请求"""
        current_time = datetime.now()
        cache_key = f"{user_id}:{command}"

        if cache_key in self._request_cache:
            last_time = self._request_cache[cache_key]
            if (current_time - last_time).total_seconds() < self._cache_timeout:
                logger.warning(f"Duplicate request detected for {cache_key}")
                return True

        self._request_cache[cache_key] = current_time
        # 清理过期缓存
        expired_keys = []
        for key, time in self._request_cache.items():
            if (current_time - time).total_seconds() > self._cache_timeout:
                expired_keys.append(key)
        for key in expired_keys:
            del self._request_cache[key]

        return False

    @filter.command("jrrp", alias={"今日人品"})
    async def jrrp_command(self, event: AstrMessageEvent, *args):
        """统一的jrrp命令处理器"""
        async with _fortune_lock:
            # 检查插件是否启用
            if not self.config.get("enable_plugin", True):
                yield event.plain_result("今日人品插件已关闭")
                return

            # 解析子命令
            if not args:
                # 没有参数，执行默认的人品测试
                await self._daily_fortune(event)
                return

            subcommand = args[0].lower()

            # 处理子命令
            if subcommand == "rank":
                await self._fortune_rank(event)
            elif subcommand in ["history", "hi"]:
                await self._fortune_history(event)
            elif subcommand == "reset":
                # 检查是否有 --confirm 参数
                if len(args) > 1 and args[1] == "--confirm":
                    await self._reset_all_fortune(event, confirmed=True)
                else:
                    yield event.plain_result("⚠️ 危险操作！如果确定要重置所有人品数据，请使用: /jrrp reset --confirm")
            elif subcommand in ["delete", "del"]:
                await self._delete_user_fortune(event)
            else:
                # 未知子命令，当作测试人品处理
                await self._daily_fortune(event)

    async def _daily_fortune(self, event: AstrMessageEvent):
        """查看今日人品（内部方法）"""
        try:
            # 检查是否是重复请求
            user_id = event.get_sender_id()
            if self._check_duplicate_request(user_id, "jrrp"):
                logger.info(f"Ignored duplicate jrrp request from {user_id}")
                return

            user_name = await self.get_user_name(event)
            today_key = self.get_today_key()

            # 加载今日人品数据
            fortunes = await self.load_data(self.fortune_file)

            # 确保数据结构存在
            if today_key not in fortunes:
                fortunes[today_key] = {}

            # 检查用户今日是否已经测试过
            if user_id in fortunes[today_key]:
                # 已经测试过，直接返回结果
                fortune_data = fortunes[today_key][user_id]
                fortune_value = fortune_data["value"]
                level = self.get_fortune_level(fortune_value)

                result = f"📌 {user_name} 今天已经查询过了哦~\n"
                result += f"今日人品值: {fortune_value}\n"
                result += f"运势: {level} 😊"

                yield event.plain_result(result)
                return

            # 生成新的人品值
            min_val = self.config.get("min_fortune", 0)
            max_val = self.config.get("max_fortune", 100)
            fortune_value = random.randint(min_val, max_val)
            level = self.get_fortune_level(fortune_value)

            logger.info(f"Generated fortune for {user_id}: {fortune_value}")

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

            # 构建基础回复
            result = f"【{user_name}】开始测试今日人品...\n\n"

            # 如果启用LLM，生成占卜过程描述
            process_text = ""
            advice = ""

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
                    if process_resp and process_resp.completion_text:
                        process_text = process_resp.completion_text

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
                    if advice_resp and advice_resp.completion_text:
                        advice = advice_resp.completion_text
                except Exception as e:
                    logger.error(f"LLM调用失败: {e}")

            # 使用默认文本
            if not process_text:
                process_text = "水晶球中浮现出神秘的光芒..."
            if not advice:
                advice = self._get_default_advice(fortune_value, level)

            # 组装完整消息
            result += f"🔮 {process_text}\n\n"
            result += f"💎 人品值：{fortune_value}\n"
            result += f"✨ 运势：{level}\n"
            result += f"💬 建议：{advice}"

            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"处理今日人品指令时出错: {e}", exc_info=True)
            yield event.plain_result("抱歉，处理您的请求时出现了错误。")

    async def _fortune_rank(self, event: AstrMessageEvent):
        """查看群聊内今日人品排行（内部方法）"""
        try:
            # 检查是否是重复请求
            user_id = event.get_sender_id()
            if self._check_duplicate_request(user_id, "jrrp rank"):
                return

            if event.is_private_chat():
                yield event.plain_result("人品排行榜仅在群聊中可用")
                return

            today_key = self.get_today_key()

            # 直接从全局人品数据中读取
            fortunes = await self.load_data(self.fortune_file)

            # 检查是否有数据
            if today_key not in fortunes or not fortunes[today_key]:
                yield event.plain_result("📊 今天还没有人查询人品哦~")
                return

            # 获取所有今日人品数据并排序
            today_fortunes = fortunes[today_key]
            sorted_fortunes = sorted(
                today_fortunes.items(),
                key=lambda x: x[1]["value"],
                reverse=True
            )

            # 构建排行榜
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

        except Exception as e:
            logger.error(f"处理人品排行指令时出错: {e}", exc_info=True)
            yield event.plain_result("抱歉，获取排行榜时出现了错误。")

    async def _fortune_history(self, event: AstrMessageEvent):
        """查看个人人品历史（内部方法）"""
        try:
            # 检查是否是重复请求
            user_id = event.get_sender_id()
            if self._check_duplicate_request(user_id, "jrrp history"):
                return

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

        except Exception as e:
            logger.error(f"处理人品历史指令时出错: {e}", exc_info=True)
            yield event.plain_result("抱歉，获取历史记录时出现了错误。")

    async def _reset_all_fortune(self, event: AstrMessageEvent, confirmed: bool = False):
        """清除所有数据（仅管理员）（内部方法）"""
        try:
            if not event.is_admin():
                yield event.plain_result("❌ 只有管理员才能使用此命令")
                return

            if confirmed:
                # 直接执行清除操作
                try:
                    if os.path.exists(self.fortune_file):
                        os.remove(self.fortune_file)
                    if os.path.exists(self.history_file):
                        os.remove(self.history_file)

                    yield event.plain_result("✅ 所有人品数据已清除")
                    logger.info(f"Admin {event.get_sender_id()} reset all fortune data")
                except Exception as e:
                    yield event.plain_result(f"❌ 清除数据时出错: {str(e)}")
            else:
                # 未确认，提示需要确认
                yield event.plain_result("⚠️ 危险操作！如果确定要重置所有人品数据，请使用: /jrrp reset --confirm")

        except Exception as e:
            logger.error(f"清除所有数据时出错: {e}", exc_info=True)
            yield event.plain_result("抱歉，清除数据时出现了错误。")

    async def _delete_user_fortune(self, event: AstrMessageEvent):
        """清除使用人的数据（内部方法）"""
        try:
            user_id = event.get_sender_id()
            user_name = await self.get_user_name(event)

            # 清除今日人品数据
            fortunes = await self.load_data(self.fortune_file)
            deleted = False

            for date_key in list(fortunes.keys()):
                if user_id in fortunes[date_key]:
                    del fortunes[date_key][user_id]
                    deleted = True
                    # 如果这一天没有数据了，删除整个日期键
                    if not fortunes[date_key]:
                        del fortunes[date_key]

            if deleted:
                await self.save_data(self.fortune_file, fortunes)

            # 清除历史记录
            history = await self.load_data(self.history_file)
            history_deleted = False

            if user_id in history:
                del history[user_id]
                history_deleted = True
                await self.save_data(self.history_file, history)

            if deleted or history_deleted:
                yield event.plain_result(f"✅ 已清除 {user_name} 的所有人品数据")
                logger.info(f"User {user_id} deleted their fortune data")
            else:
                yield event.plain_result(f"ℹ️ {user_name} 没有人品数据记录")

        except Exception as e:
            logger.error(f"清除用户数据时出错: {e}", exc_info=True)
            yield event.plain_result("抱歉，清除数据时出现了错误。")

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

    async def terminate(self):
        """插件卸载时调用"""
        try:
            # 删除配置文件
            config_file = os.path.join("data", "config", "astrbot_plugin_daily_fortune_config.json")
            if os.path.exists(config_file):
                os.remove(config_file)
                logger.info(f"Removed config file: {config_file}")

            # 删除数据目录
            if os.path.exists(self.data_dir):
                shutil.rmtree(self.data_dir)
                logger.info(f"Removed data directory: {self.data_dir}")

        except Exception as e:
            logger.error(f"Error during plugin termination: {e}")

        DailyFortunePlugin._initialized = False
        DailyFortunePlugin._instance = None
        logger.info("今日人品插件已卸载")
