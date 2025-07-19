import json
import random
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Star, register, Context
from astrbot.api import logger, AstrBotConfig

@register(
    name="astrbot_plugin_jrrp",
    author="xSapientia",
    desc="今日人品查询插件 - 支持群排行/LLM增强",
    version="2.0.0"
)
class JRRPPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config if config else AstrBotConfig()
        self.data_dir = Path("data/jrrp")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file = self.data_dir / "jrrp_data.json"
        self.load_data()

        # 设置默认配置
        self.ensure_config_defaults()

        logger.info("今日人品插件 v2.0.0 加载成功！")

    def ensure_config_defaults(self):
        """确保配置有默认值"""
        defaults = {
            "enable_plugin": True,
            "min_value": 0,
            "max_value": 100,
            "enable_llm_process": False,
            "process_prompt": "用水晶球占卜的口吻，描述{user_name}的今日人品值是{value}({desc})的过程。要神秘且有趣，50字以内。",
            "enable_llm_advice": False,
            "advice_prompt": "根据{user_name}的今日人品值{value}({desc})，用幽默的方式给出今日建议或吐槽。30字以内。"
        }

        for key, default_value in defaults.items():
            if key not in self.config:
                self.config[key] = default_value

    def load_data(self):
        """加载数据"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            else:
                self.data = {}
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            self.data = {}

    def save_data(self):
        """保存数据"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据失败: {e}")

    def get_jrrp(self, user_id: str, user_name: str, group_id: Optional[str] = None) -> Tuple[int, bool]:
        """获取今日人品值"""
        today = datetime.now().strftime("%Y-%m-%d")
        user_key = f"{user_id}_{today}"

        # 如果今天已经查询过，返回缓存的结果
        if user_key in self.data:
            return self.data[user_key]["value"], False

        # 生成今日人品值
        min_val = self.config.get("min_value", 0)
        max_val = self.config.get("max_value", 100)

        seed = f"{user_id}{today}jrrp"
        random.seed(int(hashlib.md5(seed.encode()).hexdigest(), 16) % 100000)
        value = random.randint(min_val, max_val)
        random.seed()  # 重置随机种子

        # 保存结果
        self.data[user_key] = {
            "user_name": user_name,
            "value": value,
            "date": today,
            "group_id": group_id  # 记录群组ID，用于排行榜
        }
        self.save_data()

        return value, True

    def get_luck_desc(self, value: int) -> str:
        """根据人品值返回运势描述"""
        max_val = self.config.get("max_value", 100)
        percent = (value / max_val) * 100

        if percent >= 100:
            return "万事皆允 👑"
        elif percent >= 90:
            return "极其好运 🌟"
        elif percent >= 80:
            return "好运连连 🎉"
        elif percent >= 60:
            return "运气不错 😊"
        elif percent >= 40:
            return "平平淡淡 😐"
        elif percent >= 20:
            return "略有不顺 😕"
        elif percent >= 10:
            return "十分不顺 😣"
        elif percent > 0:
            return "倒大霉 😱"
        else:
            return "极其倒霉 💀"

    @filter.command("jrrp", alias=["-jrrp", "今日人品"])
    async def cmd_jrrp(self, event: AstrMessageEvent):
        """查询今日人品"""
        # 检查插件是否启用
        if not self.config.get("enable_plugin", True):
            return

        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        group_id = event.get_group_id()

        value, is_new = self.get_jrrp(user_id, user_name, group_id)
        desc = self.get_luck_desc(value)

        if is_new:
            # 新查询
            if self.config.get("enable_llm_process", False):
                # 使用LLM生成水晶球过程
                prompt = self.config.get("process_prompt").format(
                    user_name=user_name,
                    value=value,
                    desc=desc
                )
                yield event.request_llm(prompt)
            else:
                # 使用默认文本
                result = f"🔮 {user_name} 的今日人品值: {value}\n📊 运势: {desc}"
                yield event.plain_result(result)

            # 生成建议
            if self.config.get("enable_llm_advice", False):
                prompt = self.config.get("advice_prompt").format(
                    user_name=user_name,
                    value=value,
                    desc=desc
                )
                yield event.request_llm(prompt)
        else:
            # 重复查询
            result = f"📌 {user_name} 今天已经查询过了哦~\n今日人品值: {value}\n运势: {desc}"
            yield event.plain_result(result)

    @filter.command("jrrprank", alias=["人品排行", "jrrp排行"])
    async def cmd_jrrprank(self, event: AstrMessageEvent):
        """查看群聊人品排行榜"""
        # 检查插件是否启用
        if not self.config.get("enable_plugin", True):
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 此指令仅在群聊中可用")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        today_users = []

        # 收集今天该群的所有查询记录
        for user_key, data in self.data.items():
            if data.get("date") == today and data.get("group_id") == group_id:
                today_users.append({
                    "name": data.get("user_name", "未知用户"),
                    "value": data["value"]
                })

        if not today_users:
            yield event.plain_result("📊 今天本群还没有人查询人品哦~")
            return

        # 排序
        today_users.sort(key=lambda x: x["value"], reverse=True)

        # 生成排行榜文本
        rank_text = "📊 今日人品排行榜\n" + "=<font color=#AAAAAA>20 + "\n"
        for i, user in enumerate(today_users[:10], 1):  # 只显示前10名
            medal = ""
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            rank_text += f"{medal}{i}. {user['name']}: {user['value']}分\n"

        yield event.plain_result(rank_text)

    async def terminate(self):
        """插件卸载时调用"""
        self.save_data()
        logger.info("今日人品插件已卸载")
