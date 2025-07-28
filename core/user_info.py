"""
用户信息获取模块 - 重构优化版
参考astrbot_plugin_box插件的优秀实践，优化用户信息获取逻辑
支持多种信息源整合：基础信息、tip内容解析、缓存机制
"""

from typing import Dict, Optional, Tuple, Any, List
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.api import logger
import astrbot.api.message_components as Comp
import time
import json
import re


class UserInfo:
    """用户信息数据类"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.nickname = f"用户{user_id[-6:]}"
        self.card = ""
        self.title = ""
        self.sex = "unknown"
        self.level = 0
        self.is_admin = False
        self.platform = ""
        self.group_id = ""
        self.last_updated = time.time()
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "card": self.card or self.nickname,
            "title": self.title or "无",
            "sex": self.sex,
            "level": self.level,
            "is_admin": self.is_admin,
            "platform": self.platform,
            "group_id": self.group_id,
            "last_updated": self.last_updated
        }
        
    def update_from_dict(self, data: Dict[str, Any]):
        """从字典更新信息"""
        for key, value in data.items():
            if hasattr(self, key) and value:
                setattr(self, key, value)
        self.last_updated = time.time()
        
    def is_expired(self, expire_time: int = 300) -> bool:
        """检查是否过期"""
        return time.time() - self.last_updated > expire_time


class UserInfoManager:
    """用户信息管理器 - 重构优化版"""
    
    def __init__(self, context: Context):
        """
        初始化用户信息管理器
        
        Args:
            context: AstrBot上下文
        """
        self.context = context
        self.user_cache: Dict[str, UserInfo] = {}
        self.cache_expire_time = 300  # 缓存过期时间：5分钟
        self.max_cache_size = 100  # 最大缓存数量
        
        logger.info("[UserInfoManager] 用户信息管理器已初始化")
        
    async def get_user_info(self, event: AstrMessageEvent, target_user_id: str = None) -> Dict[str, Any]:
        """
        获取用户完整信息 - 多源整合
        
        Args:
            event: 消息事件
            target_user_id: 目标用户ID（如果为None则获取发送者信息）
            
        Returns:
            包含用户信息的字典
        """
        user_id = target_user_id or event.get_sender_id()
        
        try:
            # 获取或创建用户信息对象
            user_info = self._get_or_create_user_info(user_id)
            
            # 如果缓存未过期，直接返回
            if not user_info.is_expired(self.cache_expire_time):
                logger.debug(f"[UserInfoManager] 使用缓存信息: {user_id}")
                return user_info.to_dict()
            
            # 更新用户信息
            await self._update_user_info(event, user_info, target_user_id)
            
            # 缓存管理
            self._manage_cache()
            
            result = user_info.to_dict()
            logger.debug(f"[UserInfoManager] 获取用户信息: {user_id} -> {result['nickname']}")
            return result
            
        except Exception as e:
            logger.error(f"[UserInfoManager] 获取用户信息失败: {user_id}, 错误: {e}")
            return self._get_fallback_user_info(event, user_id, target_user_id)
    
    def _get_or_create_user_info(self, user_id: str) -> UserInfo:
        """获取或创建用户信息对象"""
        if user_id not in self.user_cache:
            self.user_cache[user_id] = UserInfo(user_id)
        return self.user_cache[user_id]
    
    async def _update_user_info(self, event: AstrMessageEvent, user_info: UserInfo, target_user_id: str = None):
        """更新用户信息"""
        # 1. 获取基础信息
        basic_info = self._extract_basic_info(event, user_info.user_id, target_user_id)
        user_info.update_from_dict(basic_info)
        
        # 2. 尝试从tip内容获取增强信息
        tip_info = self._extract_tip_info(event, user_info.user_id, target_user_id)
        if tip_info:
            user_info.update_from_dict(tip_info)
            logger.debug(f"[UserInfoManager] 从tip获取增强信息: {user_info.user_id}")
    
    def _extract_basic_info(self, event: AstrMessageEvent, user_id: str, target_user_id: str = None) -> Dict[str, Any]:
        """提取基础用户信息"""
        info = {
            "user_id": user_id,
            "platform": event.get_platform_name(),
            "is_admin": event.is_admin() if not target_user_id else False,
            "group_id": event.get_group_id() or ""
        }
        
        if not target_user_id:
            # 获取发送者信息
            info["nickname"] = event.get_sender_name() or f"用户{user_id[-6:]}"
        else:
            # 获取目标用户信息
            info["nickname"] = f"用户{user_id[-6:]}"
            
        return info
    
    def _extract_tip_info(self, event: AstrMessageEvent, user_id: str, target_user_id: str = None) -> Optional[Dict[str, Any]]:
        """从tip内容提取用户信息"""
        try:
            message_str = event.message_obj.message_str
            if not message_str or "<tip>" not in message_str:
                return None
                
            # 提取并解析tip内容
            tip_data = self._parse_tip_content(message_str)
            if not tip_data:
                return None
            
            # 根据查询类型提取信息
            if target_user_id:
                return self._extract_target_user_from_tip(tip_data, target_user_id)
            else:
                return self._extract_sender_from_tip(tip_data, user_id)
                
        except Exception as e:
            logger.debug(f"[UserInfoManager] tip信息提取失败: {e}")
            return None
    
    def _parse_tip_content(self, message_str: str) -> Optional[Dict[str, Any]]:
        """解析tip内容"""
        try:
            # 提取tip标签内容
            start_idx = message_str.find("<tip>")
            end_idx = message_str.find("</tip>")
            
            if start_idx == -1 or end_idx == -1:
                return None
                
            tip_content = message_str[start_idx + 5:end_idx].strip()
            
            # 查找JSON部分
            json_start = tip_content.find("{")
            if json_start == -1:
                return None
                
            json_str = tip_content[json_start:]
            
            # 尝试解析JSON
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # 尝试修复JSON格式
                fixed_json = self._fix_json_format(json_str)
                if fixed_json:
                    return json.loads(fixed_json)
                return None
                
        except Exception as e:
            logger.debug(f"[UserInfoManager] tip内容解析失败: {e}")
            return None
    
    def _fix_json_format(self, json_str: str) -> Optional[str]:
        """修复JSON格式问题"""
        try:
            # 截取到最后一个}
            last_brace = json_str.rfind('}')
            if last_brace != -1:
                json_str = json_str[:last_brace + 1]
            
            # 替换Python字面量
            json_str = (json_str.replace("True", "true")
                              .replace("False", "false")
                              .replace("None", "null"))
            
            # 修复键名的单引号（简单处理）
            json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
            
            return json_str
        except Exception:
            return None
    
    def _extract_sender_from_tip(self, tip_data: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
        """从tip数据提取发送者信息"""
        try:
            sender = tip_data.get("sender", {})
            if sender and str(sender.get("user_id")) == str(user_id):
                return self._normalize_user_data(sender)
        except Exception as e:
            logger.debug(f"[UserInfoManager] 提取发送者信息失败: {e}")
        return None
    
    def _extract_target_user_from_tip(self, tip_data: Dict[str, Any], target_user_id: str) -> Optional[Dict[str, Any]]:
        """从tip数据提取目标用户信息"""
        try:
            # 查找ater1-ater20
            for i in range(1, 21):
                ater_key = f"ater{i}"
                if ater_key in tip_data:
                    ater_info = tip_data[ater_key]
                    if str(ater_info.get("user_id")) == str(target_user_id):
                        return self._normalize_user_data(ater_info)
        except Exception as e:
            logger.debug(f"[UserInfoManager] 提取目标用户信息失败: {e}")
        return None
    
    def _normalize_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化用户数据"""
        normalized = {}
        
        # 字段映射和转换
        field_mapping = {
            "nickname": "nickname",
            "card": "card", 
            "title": "title",
            "sex": "sex",
            "level": "level"
        }
        
        for src_field, dst_field in field_mapping.items():
            if src_field in data and data[src_field]:
                value = data[src_field]
                # 类型转换
                if dst_field == "level":
                    try:
                        normalized[dst_field] = int(value)
                    except (ValueError, TypeError):
                        normalized[dst_field] = 0
                else:
                    normalized[dst_field] = str(value)
        
        return normalized
    
    def _get_fallback_user_info(self, event: AstrMessageEvent, user_id: str, target_user_id: str = None) -> Dict[str, Any]:
        """获取降级用户信息"""
        fallback_nickname = f"用户{user_id[-6:]}"
        if not target_user_id:
            fallback_nickname = event.get_sender_name() or fallback_nickname
            
        return {
            "user_id": user_id,
            "nickname": fallback_nickname,
            "card": fallback_nickname,
            "title": "无",
            "sex": "unknown",
            "level": 0,
            "is_admin": event.is_admin() if not target_user_id else False,
            "platform": event.get_platform_name(),
            "group_id": event.get_group_id() or "",
            "last_updated": time.time()
        }
    
    def _manage_cache(self):
        """管理缓存大小和过期"""
        try:
            # 清理过期缓存
            current_time = time.time()
            expired_keys = [
                user_id for user_id, user_info in self.user_cache.items()
                if user_info.is_expired(self.cache_expire_time)
            ]
            
            for user_id in expired_keys:
                del self.user_cache[user_id]
            
            # 如果缓存仍然过大，删除最旧的
            if len(self.user_cache) > self.max_cache_size:
                sorted_items = sorted(
                    self.user_cache.items(),
                    key=lambda x: x[1].last_updated
                )
                
                # 保留一半的缓存
                keep_count = self.max_cache_size // 2
                for user_id, _ in sorted_items[:-keep_count]:
                    del self.user_cache[user_id]
                    
            if expired_keys:
                logger.debug(f"[UserInfoManager] 清理了{len(expired_keys)}个过期缓存，当前缓存: {len(self.user_cache)}")
                
        except Exception as e:
            logger.warning(f"[UserInfoManager] 缓存管理失败: {e}")
    
    def get_target_user_from_message(self, event: AstrMessageEvent) -> Tuple[Optional[str], Optional[str]]:
        """
        从消息中提取@的目标用户
        参考box插件的实现方式
        
        Args:
            event: 消息事件
            
        Returns:
            (用户ID, 昵称) 元组
        """
        try:
            # 查找@组件，排除机器人自身
            self_id = event.get_self_id()
            
            for comp in event.message_obj.message:
                if isinstance(comp, Comp.At):
                    user_id = str(comp.qq)
                    if user_id != self_id:
                        # 尝试从缓存获取昵称
                        if user_id in self.user_cache:
                            cached_info = self.user_cache[user_id]
                            nickname = cached_info.nickname
                        else:
                            nickname = f"用户{user_id[-6:]}"
                        
                        return user_id, nickname
                        
        except Exception as e:
            logger.debug(f"[UserInfoManager] 提取目标用户失败: {e}")
            
        return None, None
    
    async def get_batch_user_info(self, event: AstrMessageEvent, user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取用户信息
        
        Args:
            event: 消息事件
            user_ids: 用户ID列表
            
        Returns:
            用户ID到信息的映射
        """
        result = {}
        
        for user_id in user_ids:
            try:
                result[user_id] = await self.get_user_info(event, user_id)
            except Exception as e:
                logger.warning(f"[UserInfoManager] 批量获取用户{user_id}信息失败: {e}")
                result[user_id] = self._get_fallback_user_info(event, user_id, user_id)
                
        return result
    
    def format_user_display_name(self, user_info: Dict[str, Any]) -> str:
        """
        格式化用户显示名称
        优先级: card > nickname > 用户ID后6位
        
        Args:
            user_info: 用户信息字典
            
        Returns:
            格式化的显示名称
        """
        card = user_info.get("card", "").strip()
        nickname = user_info.get("nickname", "").strip()
        user_id = user_info.get("user_id", "")
        
        if card and card != "无" and card != nickname:
            return card
        elif nickname:
            return nickname
        else:
            return f"用户{user_id[-6:]}"
    
    def get_user_gender_display(self, user_info: Dict[str, Any]) -> str:
        """
        获取用户性别显示文本
        
        Args:
            user_info: 用户信息字典
            
        Returns:
            性别显示文本
        """
        sex = user_info.get("sex", "unknown").lower()
        gender_map = {
            "male": "男",
            "female": "女", 
            "unknown": "未知"
        }
        return gender_map.get(sex, "未知")
    
    def clear_cache(self):
        """清空所有缓存"""
        self.user_cache.clear()
        logger.info("[UserInfoManager] 已清空所有缓存")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        current_time = time.time()
        expired_count = sum(
            1 for user_info in self.user_cache.values()
            if user_info.is_expired(self.cache_expire_time)
        )
        
        return {
            "total_cached": len(self.user_cache),
            "expired_count": expired_count,
            "active_count": len(self.user_cache) - expired_count,
            "max_cache_size": self.max_cache_size,
            "cache_expire_time": self.cache_expire_time
        }
    
    def debug_user_info(self, user_id: str) -> Dict[str, Any]:
        """调试用户信息"""
        if user_id in self.user_cache:
            user_info = self.user_cache[user_id]
            return {
                "cached": True,
                "expired": user_info.is_expired(self.cache_expire_time),
                "info": user_info.to_dict()
            }
        else:
            return {
                "cached": False,
                "expired": None,
                "info": None
            }
