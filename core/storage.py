"""
数据存储和缓存管理模块
"""

import json
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from astrbot.api import logger


class Storage:
    """数据存储管理器"""
    
    def __init__(self, plugin_name: str = "astrbot_plugin_daily_fortune"):
        """
        初始化存储管理器
        
        Args:
            plugin_name: 插件名称
        """
        # 数据应该存储在 AstrBot 的 data/plugin_data 目录下
        self.data_dir = Path(f"data/plugin_data/{plugin_name}")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据文件路径
        self.fortune_file = self.data_dir / "daily_fortune.json"
        self.history_file = self.data_dir / "fortune_history.json"
        
        # 加载数据
        self.daily_data = self._load_data(self.fortune_file)
        self.history_data = self._load_data(self.history_file)
        
        # 正在处理的用户集合（防止重复请求）
        self.processing_users = set()
        
    def _load_data(self, file_path: Path) -> Dict:
        """加载JSON数据"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载数据文件失败: {e}")
        return {}
        
    def _save_data(self, data: Dict, file_path: Path):
        """保存JSON数据"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据文件失败: {e}")
            
    def is_user_processing(self, user_id: str) -> bool:
        """检查用户是否正在处理中"""
        return user_id in self.processing_users
        
    def add_processing_user(self, user_id: str):
        """添加正在处理的用户"""
        self.processing_users.add(user_id)
        
    def remove_processing_user(self, user_id: str):
        """移除正在处理的用户"""
        self.processing_users.discard(user_id)
        
    def get_today_fortune(self, today: str, user_id: str) -> Optional[Dict]:
        """
        获取用户今日运势数据
        
        Args:
            today: 日期字符串
            user_id: 用户ID
            
        Returns:
            运势数据字典，如果不存在返回None
        """
        if today in self.daily_data and user_id in self.daily_data[today]:
            return self.daily_data[today][user_id]
        return None
        
    def save_today_fortune(self, today: str, user_id: str, fortune_data: Dict):
        """
        保存用户今日运势数据
        
        Args:
            today: 日期字符串
            user_id: 用户ID
            fortune_data: 运势数据
        """
        if today not in self.daily_data:
            self.daily_data[today] = {}
            
        self.daily_data[today][user_id] = fortune_data
        self._save_data(self.daily_data, self.fortune_file)
        
        # 同时更新历史记录
        if user_id not in self.history_data:
            self.history_data[user_id] = {}
            
        self.history_data[user_id][today] = {
            "jrrp": fortune_data["jrrp"],
            "fortune": fortune_data["fortune"]
        }
        self._save_data(self.history_data, self.history_file)
        
    def get_today_all_fortunes(self, today: str) -> Dict:
        """
        获取今日所有用户的运势数据
        
        Args:
            today: 日期字符串
            
        Returns:
            所有用户的运势数据
        """
        return self.daily_data.get(today, {})
        
    def get_user_history(self, user_id: str, limit: int = 30) -> Dict:
        """
        获取用户历史记录
        
        Args:
            user_id: 用户ID
            limit: 获取的最大记录数
            
        Returns:
            用户历史记录
        """
        if user_id not in self.history_data:
            return {}
            
        user_history = self.history_data[user_id]
        # 按日期排序并限制数量
        sorted_dates = sorted(user_history.keys(), reverse=True)[:limit]
        
        return {date: user_history[date] for date in sorted_dates}
        
    def delete_user_history(self, user_id: str, today: str) -> int:
        """
        删除用户历史记录（保留今日）
        
        Args:
            user_id: 用户ID
            today: 今日日期字符串
            
        Returns:
            删除的记录数
        """
        deleted_count = 0
        
        # 删除历史记录（保留今日）
        if user_id in self.history_data:
            user_history = self.history_data[user_id]
            dates_to_delete = [date for date in user_history.keys() if date != today]
            for date in dates_to_delete:
                del user_history[date]
                deleted_count += 1
                
            # 如果历史记录为空，删除整个用户记录
            if not user_history:
                del self.history_data[user_id]
                
            self._save_data(self.history_data, self.history_file)
            
        # 删除每日记录（保留今日）
        dates_to_delete = [date for date in self.daily_data.keys() if date != today]
        for date in dates_to_delete:
            if user_id in self.daily_data[date]:
                del self.daily_data[date][user_id]
                deleted_count += 1
            # 如果该日期没有任何用户数据，删除整个日期记录
            if not self.daily_data[date]:
                del self.daily_data[date]
                
        self._save_data(self.daily_data, self.fortune_file)
        
        return deleted_count
        
    def clear_today_fortune(self, today: str, user_id: str) -> bool:
        """
        清除用户今日运势记录
        
        Args:
            today: 今日日期字符串
            user_id: 用户ID
            
        Returns:
            是否成功删除
        """
        deleted = False
        
        # 删除今日记录
        if today in self.daily_data and user_id in self.daily_data[today]:
            del self.daily_data[today][user_id]
            deleted = True
            # 如果该日期没有任何用户数据，删除整个日期记录
            if not self.daily_data[today]:
                del self.daily_data[today]
            self._save_data(self.daily_data, self.fortune_file)
            
        # 删除今日历史记录
        if user_id in self.history_data and today in self.history_data[user_id]:
            del self.history_data[user_id][today]
            deleted = True
            # 如果历史记录为空，删除整个用户记录
            if not self.history_data[user_id]:
                del self.history_data[user_id]
            self._save_data(self.history_data, self.history_file)
            
        # 从正在处理的集合中移除（如果存在）
        self.remove_processing_user(user_id)
        
        return deleted
        
    def reset_all_data(self):
        """重置所有数据"""
        self.daily_data = {}
        self.history_data = {}
        self._save_data(self.daily_data, self.fortune_file)
        self._save_data(self.history_data, self.history_file)
        
        # 清空正在处理的用户集合
        self.processing_users.clear()
        
    def get_user_statistics(self, user_id: str) -> Dict:
        """
        获取用户统计信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含平均值、最高值、最低值的统计信息
        """
        if user_id not in self.history_data:
            return {"avg": 0, "max": 0, "min": 0, "count": 0}
            
        jrrp_values = [data["jrrp"] for data in self.history_data[user_id].values()]
        
        if not jrrp_values:
            return {"avg": 0, "max": 0, "min": 0, "count": 0}
            
        return {
            "avg": round(sum(jrrp_values) / len(jrrp_values), 1),
            "max": max(jrrp_values),
            "min": min(jrrp_values),
            "count": len(jrrp_values)
        }
        
    def cleanup_data(self, delete_data: bool = False, delete_config: bool = False, config_name: str = ""):
        """
        清理数据（插件卸载时调用）
        
        Args:
            delete_data: 是否删除数据目录
            delete_config: 是否删除配置文件
            config_name: 配置文件名
        """
        if delete_data:
            import shutil
            if self.data_dir.exists():
                shutil.rmtree(self.data_dir)
                logger.info(f"已删除插件数据目录: {self.data_dir}")
                
        if delete_config and config_name:
            import os
            config_file = f"data/config/{config_name}_config.json"
            if os.path.exists(config_file):
                os.remove(config_file)
                logger.info(f"已删除配置文件: {config_file}")
