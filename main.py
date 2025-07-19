import json
import random
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

@register(
    "astrbot_plugin_req_jrrp",
    "xSapientia",
    "今日人品查询插件",
    "1.0.0",
    "https://github.com/xSapientia/astrbot_plugin_req_jrrp",
)
class JRRPPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config if config else AstrBotConfig()
        self.data_path = Path("data/astrbot_plugin_jrrp")
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.data_file = self.data_path / "jrrp_data.json"

        # 加载历史数据
        self.load_data()

        logger.info("今日人品插件 v1.0.0 加载成功！")

    def load_data(self):
        """加载历史数据"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"加载数据失败: {e}")
                self.data = {}
        else:
            self.data = {}

    def save_data(self):
        """保存数据"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据失败: {e}")

    def get_today_str(self) -> str:
        """获取今天的日期字符串"""
        return datetime.now().strftime("%Y-%m-%d")

    def get_user_key(self, event: AstrMessageEvent) -> str:
        """获取用户唯一标识"""
        platform = event.get_platform_name()
        user_id = event.get_sender_id()
        return f"{platform}:{user_id}"

    def calculate_weighted_random(self) -> Tuple[int, str, str]:
        """根据权重计算人品值"""
        ranges = self.config.get("ranges", self.get_default_ranges())

        # 构建权重列表
        weighted_choices = []
        for range_config in ranges:
            weight = range_config.get("weight", 1.0)
            min_val = range_config.get("min", 0)
            max_val = range_config.get("max", 100)
            desc = range_config.get("description", "")
            emoji = range_config.get("emoji", "")

            # 为了保证权重分配准确，我们把范围扩展成每个数字
            for value in range(min_val, max_val + 1):
                weighted_choices.append((value, desc, emoji, weight))

        # 根据权重选择
        if weighted_choices:
            values, descs, emojis, weights = zip(*weighted_choices)
            selected_index = random.choices(range(len(values)), weights=weights)[0]
            return values[selected_index], descs[selected_index], emojis[selected_index]
        else:
            # 如果没有配置，使用默认值
            return random.randint(0, 100), "正常运气", "😊"

    def get_default_ranges(self) -> List[Dict]:
        """获取默认的人品范围配置"""
        return [
            {"min": 0, "max": 0, "description": "极其倒霉", "emoji": "💀", "weight": 0.5},
            {"min": 1, "max": 2, "description": "倒大霉", "emoji": "😱", "weight": 1},
            {"min": 3, "max": 10, "description": "十分不顺", "emoji": "😣", "weight": 5},
            {"min": 11, "max": 20, "description": "略微不顺", "emoji": "😕", "weight": 10},
            {"min": 21, "max": 30, "description": "正常运气", "emoji": "😐", "weight": 20},
            {"min": 31, "max": 60, "description": "还不错", "emoji": "😊", "weight": 30},
            {"min": 61, "max": 80, "description": "运气很好", "emoji": "😄", "weight": 20},
            {"min": 81, "max": 98, "description": "好运连连", "emoji": "🎉", "weight": 10},
            {"min": 99, "max": 99, "description": "极其好运", "emoji": "🌟", "weight": 1},
            {"min": 100, "max": 100, "description": "万事皆允", "emoji": "👑", "weight": 0.5}
        ]

    def get_jrrp_value(self, user_key: str, user_name: str) -> Tuple[int, bool, str, str]:
        """
        获取用户的今日人品值
        返回: (人品值, 是否为新查询, 描述, emoji)
        """
        today = self.get_today_str()

        # 检查是否已经查询过
        if user_key in self.data and self.data[user_key].get("date") == today:
            # 今天已经查询过，返回之前的结果
            value = self.data[user_key]["value"]
            desc = self.data[user_key].get("description", "")
            emoji = self.data[user_key].get("emoji", "")
            return value, False, desc, emoji

        # 生成新的人品值
        if self.config.get("use_hash_seed", True):
            # 使用哈希种子，确保同一天同一用户的结果一致
            seed_str = f"{user_key}:{today}:{self.config.get('salt', 'astrbot_jrrp')}"
            seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
            random.seed(seed)

        value, desc, emoji = self.calculate_weighted_random()

        # 重置随机种子
        random.seed()

        # 保存结果
        self.data[user_key] = {
            "date": today,
            "value": value,
            "user_name": user_name,
            "description": desc,
            "emoji": emoji
        }
        self.save_data()

        return value, True, desc, emoji

    @filter.command("jrrp", alias={"-jrrp", "今日人品"})
    async def jrrp(self, event: AstrMessageEvent):
        """查看今日人品"""
        if not self.config.get("enable_plugin", True):
            return

        user_name = event.get_sender_name()
        user_key = self.get_user_key(event)

        # 获取人品值
        value, is_new, desc, emoji = self.get_jrrp_value(user_key, user_name)

        if is_new:
            # 新查询，显示完整过程
            if self.config.get("enable_llm_process", True):
                # 使用LLM生成水晶球过程
                prompt_template = self.config.get("process_prompt",
                    "模拟一个水晶球显示人品值的神秘过程。用户名:{user_name}，人品值:{value}，运势描述:{desc}。请用50字以内生动描述水晶球的变化过程，最后告知人品值。")

                prompt = prompt_template.format(
                    user_name=user_name,
                    value=value,
                    desc=desc
                )

                yield event.request_llm(prompt)
            else:
                # 使用默认模板
                result_text = f"🔮 水晶球开始发光...\n✨ 光芒逐渐汇聚...\n\n{user_name}的今日人品值: {value} {emoji}\n运势: {desc}"
                yield event.plain_result(result_text)

            # 生成建议
            if self.config.get("enable_llm_advice", True):
                advice_prompt = self.config.get("advice_prompt",
                    "根据用户的人品值给出简短建议或吐槽。用户名:{user_name}，人品值:{value}(0-100)，运势:{desc}。请用30字以内幽默地给出建议。")

                prompt = advice_prompt.format(
                    user_name=user_name,
                    value=value,
                    desc=desc
                )

                yield event.request_llm(prompt)
        else:
            # 重复查询
            if self.config.get("enable_llm_repeat", True):
                # 使用LLM生成重复查询的有趣回复
                repeat_prompt = self.config.get("repeat_prompt",
                    "用户{user_name}今天已经查询过人品了，人品值是{value}({desc})。请用30字以内幽默地提醒ta已经查询过了。")

                prompt = repeat_prompt.format(
                    user_name=user_name,
                    value=value,
                    desc=desc
                )

                yield event.request_llm(prompt)
            else:
                # 使用默认回复
                result_text = f"{user_name}今天已经查询过了哦！\n今日人品值: {value} {emoji}\n运势: {desc}"
                yield event.plain_result(result_text)

    @filter.command("jrrp_rank")
    async def jrrp_rank(self, event: AstrMessageEvent):
        """查看今日人品排行榜"""
        if not self.config.get("enable_rank", True):
            return

        today = self.get_today_str()
        today_users = []

        # 收集今天的所有查询
        for user_key, data in self.data.items():
            if data.get("date") == today:
                today_users.append({
                    "name": data.get("user_name", "未知用户"),
                    "value": data["value"],
                    "emoji": data.get("emoji", "")
                })

        if not today_users:
            yield event.plain_result("今天还没有人查询人品哦！")
            return

        # 排序
        today_users.sort(key=lambda x: x["value"], reverse=True)

        # 生成排行榜文本
        rank_text = "📊 今日人品排行榜\n" + "=<font color=#AAAAAA>20 + "\n"
        for i, user in enumerate(today_users[:10], 1):  # 只显示前10名
            rank_text += f"{i}. {user['name']}: {user['value']} {user['emoji']}\n"

        yield event.plain_result(rank_text)

    @filter.command("jrrp_history")
    async def jrrp_history(self, event: AstrMessageEvent):
        """查看个人人品历史"""
        user_key = self.get_user_key(event)
        user_name = event.get_sender_name()

        # 查找该用户的所有历史记录
        history = []
        if user_key in self.data:
            # 当前记录
            history.append({
                "date": self.data[user_key]["date"],
                "value": self.data[user_key]["value"],
                "desc": self.data[user_key].get("description", ""),
                "emoji": self.data[user_key].get("emoji", "")
            })

        if not history:
            yield event.plain_result(f"{user_name}还没有查询过人品哦！")
            return

        # 生成历史文本
        history_text = f"📜 {user_name}的人品历史\n" + "="*20 + "\n"
        for record in sorted(history, key=lambda x: x["date"], reverse=True)[:7]:  # 只显示最近7条
            history_text += f"{record['date']}: {record['value']} {record['emoji']} {record['desc']}\n"

        # 计算平均值
        avg_value = sum(r["value"] for r in history) / len(history)
        history_text += f"\n平均人品值: {avg_value:.1f}"

        yield event.plain_result(history_text)

    async def terminate(self):
        """插件卸载时调用"""
        self.save_data()
        logger.info("今日人品插件已卸载")
