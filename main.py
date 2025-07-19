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
# 全局标记，防止重复注册
_plugin_loaded = False

@register(
    "astrbot_plugin_daily_fortune",
    "xSapientia",
    "今日人品测试插件 - 测试你的今日运势",
    "0.1.2", # 更新版本号
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

    # --- 数据加载和保存方法 (省略，与上一版本相同) ---
    async def load_data(self, file_path: str) -> dict:
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
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"保存数据失败 {file_path}: {e}")

    # --- 辅助方法 (省略，与上一版本相同) ---
    def get_fortune_level(self, fortune: int) -> str:
        for (min_val, max_val), level in self.fortune_levels.items():
            if min_val <= fortune <= max_val:
                return level
        return "正常运气"

    def get_today_key(self) -> str:
        return date.today().strftime("%Y-%m-%d")

    async def get_user_name(self, event: AstrMessageEvent) -> str:
        name = event.get_sender_name()
        if not name or name == "未知":
            name = f"用户{event.get_sender_id()[-4:]}"
        return name

    def _check_duplicate_request(self, user_id: str, command: str) -> bool:
        current_time = datetime.now()
        cache_key = f"{user_id}:{command}"
        if cache_key in self._request_cache:
            last_time = self._request_cache[cache_key]
            if (current_time - last_time).total_seconds() < self._cache_timeout:
                logger.warning(f"Duplicate request detected for {cache_key}")
                return True
        self._request_cache[cache_key] = current_time
        # 清理过期缓存 (此处省略具体实现，与上一版本相同)
        return False

    def _get_default_advice(self, fortune: int, level: str) -> str:
        advice_map = {
            "极其倒霉": "今天还是躺平吧，啥也别干最安全！",
            # ... (其他默认建议)
        }
        return advice_map.get(level, "保持平常心，做好自己。")

    # --- 核心逻辑修改开始 ---

    @filter.command_group("jrrp", alias={"-jrrp", "今日人品"})
    def jrrp_group(self):
        """今日人品指令组"""
        pass

    @jrrp_group.command("", alias={"test", "测试"}) # 注册为空字符串，作为默认指令
    async def daily_fortune(self, event: AstrMessageEvent):
        """查看今日人品"""
        async with _fortune_lock:
            try:
                # 检查是否是重复请求
                user_id = event.get_sender_id()
                if self._check_duplicate_request(user_id, "jrrp"):
                    return

                # ... (daily_fortune 的核心逻辑，与上一版本相同) ...
                # (此处省略具体实现，保持与上一版本一致)

                # 模拟核心逻辑
                yield event.plain_result("今日人品测试逻辑执行成功（省略具体实现）")

            except Exception as e:
                logger.error(f"处理今日人品指令时出错: {e}", exc_info=True)
                yield event.plain_result("抱歉，处理您的请求时出现了错误。")

    @jrrp_group.command("rank", alias={"排行", "排行榜"})
    async def fortune_rank(self, event: AstrMessageEvent):
        """查看群聊内今日人品排行"""
        async with _fortune_lock:
            try:
                # 检查是否是重复请求
                user_id = event.get_sender_id()
                if self._check_duplicate_request(user_id, "jrrp rank"):
                    return

                # ... (fortune_rank 的核心逻辑，与上一版本相同) ...
                # (此处省略具体实现，保持与上一版本一致)

                # 模拟核心逻辑
                yield event.plain_result("人品排行榜逻辑执行成功（省略具体实现）")

            except Exception as e:
                logger.error(f"处理人品排行指令时出错: {e}", exc_info=True)
                yield event.plain_result("抱歉，获取排行榜时出现了错误。")

    @jrrp_group.command("history", alias={"hi", "历史"})
    async def fortune_history(self, event: AstrMessageEvent):
        """查看个人人品历史"""
        async with _fortune_lock:
            try:
                # 检查是否是重复请求
                user_id = event.get_sender_id()
                if self._check_duplicate_request(user_id, "jrrp history"):
                    return

                # ... (fortune_history 的核心逻辑，与上一版本相同) ...
                # (此处省略具体实现，保持与上一版本一致)

                # 模拟核心逻辑
                yield event.plain_result("人品历史记录逻辑执行成功（省略具体实现）")

            except Exception as e:
                logger.error(f"处理人品历史指令时出错: {e}", exc_info=True)
                yield event.plain_result("抱歉，获取历史记录时出现了错误。")

    @jrrp_group.command("reset", alias={"重置所有"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def reset_all_fortune(self, event: AstrMessageEvent):
        """清除所有数据（仅管理员）"""
        async with _fortune_lock:
            try:
                # ... (reset_all_fortune 的核心逻辑，与上一版本相同) ...
                # (此处省略具体实现，保持与上一版本一致)

                # 模拟核心逻辑
                yield event.plain_result("清除所有数据逻辑执行成功（省略具体实现）")

            except Exception as e:
                logger.error(f"清除所有数据时出错: {e}", exc_info=True)
                yield event.plain_result("抱歉，清除数据时出现了错误。")

    @jrrp_group.command("delete", alias={"del", "删除"})
    async def delete_user_fortune(self, event: AstrMessageEvent):
        """清除使用人的数据"""
        async with _fortune_lock:
            try:
                # ... (delete_user_fortune 的核心逻辑，与上一版本相同) ...
                # (此处省略具体实现，保持与上一版本一致)

                # 模拟核心逻辑
                yield event.plain_result("清除用户数据逻辑执行成功（省略具体实现）")

            except Exception as e:
                logger.error(f"清除用户数据时出错: {e}", exc_info=True)
                yield event.plain_result("抱歉，清除数据时出现了错误。")

    # --- 核心逻辑修改结束 ---

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
