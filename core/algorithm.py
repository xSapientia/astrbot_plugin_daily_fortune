"""
人品值计算算法模块
"""

import random
import hashlib
import numpy as np
from datetime import datetime, date
from typing import Dict, Tuple
from astrbot.api import logger


class FortuneAlgorithm:
    """人品值算法管理器"""
    
    def __init__(self, config: dict):
        """
        初始化算法管理器
        
        Args:
            config: 插件配置字典
        """
        self.config = config
        self.fortune_levels = {}
        self._init_fortune_levels()
        
    def _parse_ranges_string(self, ranges_str: str) -> list:
        """解析人品值分段字符串"""
        try:
            ranges = []
            parts = [part.strip() for part in ranges_str.split(',')]
            for part in parts:
                if '-' in part:
                    min_val, max_val = part.split('-', 1)
                    ranges.append([int(min_val.strip()), int(max_val.strip())])
                else:
                    # 如果没有'-'，则认为是单个值
                    val = int(part.strip())
                    ranges.append([val, val])
            return ranges
        except Exception as e:
            logger.error(f"[daily_fortune] 解析人品值分段失败: {e}")
            return []
            
    def _parse_list_string(self, list_str: str) -> list:
        """解析逗号分隔的字符串列表"""
        try:
            return [item.strip() for item in list_str.split(',') if item.strip()]
        except Exception as e:
            logger.error(f"[daily_fortune] 解析字符串列表失败: {e}")
            return []
            
    def _init_fortune_levels(self):
        """初始化运势等级映射"""
        # 获取配置的人品值分段字符串
        ranges_jrrp_str = self.config.get("ranges_jrrp", "0-1, 2-10, 11-20, 21-30, 31-40, 41-60, 61-80, 81-98, 99-100")
        ranges_jrrp_config = self._parse_ranges_string(ranges_jrrp_str)
        
        # 获取配置的运势描述字符串
        ranges_fortune_str = self.config.get("ranges_fortune", "极凶, 大凶, 凶, 小凶, 末吉, 小吉, 中吉, 大吉, 极吉")
        ranges_fortune_config = self._parse_list_string(ranges_fortune_str)
        
        # 获取配置的emoji字符串
        ranges_emoji_str = self.config.get("ranges_emoji", "💀, 😨, 😰, 😟, 😐, 🙂, 😊, 😄, 🤩")
        ranges_emoji_config = self._parse_list_string(ranges_emoji_str)
        
        # 保存配置字符串供外部使用
        self.ranges_jrrp_str = ranges_jrrp_str
        self.ranges_fortune_str = ranges_fortune_str
        self.ranges_emoji_str = ranges_emoji_str
        
        # 构建运势等级映射
        self.fortune_levels = {}
        
        for i, range_config in enumerate(ranges_jrrp_config):
            if len(range_config) >= 2:
                min_val = int(range_config[0])
                max_val = int(range_config[1])
                
                # 获取对应的运势描述和emoji，如果超出范围则使用默认值
                fortune_name = ranges_fortune_config[i] if i < len(ranges_fortune_config) else "未知"
                fortune_emoji = ranges_emoji_config[i] if i < len(ranges_emoji_config) else "❓"
                
                self.fortune_levels[(min_val, max_val)] = (fortune_name, fortune_emoji)
                
        # 如果配置为空或无效，使用默认配置
        if not self.fortune_levels:
            self.fortune_levels = {
                (0, 1): ("极凶", "💀"),
                (2, 10): ("大凶", "😨"),
                (11, 20): ("凶", "😰"),
                (21, 30): ("小凶", "😟"),
                (31, 40): ("末吉", "😐"),
                (41, 60): ("小吉", "🙂"),
                (61, 80): ("中吉", "😊"),
                (81, 98): ("大吉", "😄"),
                (99, 100): ("极吉", "🤩")
            }
            
        logger.info(f"[daily_fortune] 运势等级映射已初始化，共 {len(self.fortune_levels)} 个等级")
        
    def get_today_key(self) -> str:
        """获取今日日期作为key，确保每日只能测试一次"""
        return datetime.now().strftime("%Y-%m-%d")
        
    def get_current_timestamp(self) -> str:
        """获取当前时间戳，用于存储测试时间"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def calculate_jrrp(self, user_id: str) -> int:
        """
        计算今日人品值
        
        Args:
            user_id: 用户ID
            
        Returns:
            人品值 (0-100)
        """
        algorithm = self.config.get("jrrp_algorithm", "random")
        today = self.get_today_key()
        
        if algorithm == "random":
            # 纯随机算法（添加时间变量实现真随机）
            current_time = datetime.now().strftime("%H:%M:%S.%f")  # 包含微秒的时间
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            return random.randint(0, 100)
            
        elif algorithm == "hash":
            # 基于用户ID和日期的哈希算法（保持固定）
            seed = f"{user_id}_{today}"
            hash_value = int(hashlib.md5(seed.encode()).hexdigest(), 16)
            return hash_value % 101
            
        elif algorithm == "normal":
            # 正态分布算法（中间值概率高）
            current_time = datetime.now().strftime("%H:%M:%S.%f")
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            # 均值50，标准差20的正态分布
            value = int(np.random.normal(50, 20))
            # 限制在0-100范围内
            return max(0, min(100, value))
            
        elif algorithm == "lucky":
            # 幸运算法（高分值概率较高）
            current_time = datetime.now().strftime("%H:%M:%S.%f")
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            # 使用beta分布，α=8, β=2，偏向高分
            value = int(np.random.beta(8, 2) * 100)
            return value
            
        elif algorithm == "challenge":
            # 挑战算法（极端值概率较高）
            current_time = datetime.now().strftime("%H:%M:%S.%f")
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            # 30%概率获得极低或极高值
            if random.random() < 0.3:
                # 极端值
                if random.random() < 0.5:
                    return random.randint(0, 20)  # 极低
                else:
                    return random.randint(80, 100)  # 极高
            else:
                # 普通值
                return random.randint(21, 79)
        else:
            # 默认使用random算法
            current_time = datetime.now().strftime("%H:%M:%S.%f")
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            return random.randint(0, 100)
            
    def get_fortune_info(self, jrrp: int) -> Tuple[str, str]:
        """
        根据人品值获取运势信息
        
        Args:
            jrrp: 人品值
            
        Returns:
            (运势描述, emoji表情)
        """
        # 按照配置的分段从左到右匹配
        for (min_val, max_val), (fortune, emoji) in self.fortune_levels.items():
            if min_val <= jrrp <= max_val:
                return fortune, emoji
        return "未知", "❓"
        
    def get_fortune_variables(self) -> Dict[str, str]:
        """
        获取运势相关的模板变量
        
        Returns:
            包含运势相关变量的字典
        """
        return {
            "ranges_jrrp": self.ranges_jrrp_str,
            "ranges_fortune": self.ranges_fortune_str,
            "ranges_emoji": self.ranges_emoji_str
        }
