"""
用户信息获取模块 - 简化版
每次从信息源直接获取，无缓存机制
"""

from typing import Dict, Optional, Tuple, Any
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.api import logger
import astrbot.api.message_components as Comp
import json
import re


class UserInfoManager:
    """用户信息管理器 - 简化版"""
    
    def __init__(self, context: Context):
        """
        初始化用户信息管理器
        
        Args:
            context: AstrBot上下文
        """
        self.context = context
        logger.info("[UserInfoManager] 用户信息管理器已初始化")
        
    async def get_user_info(self, event: AstrMessageEvent, target_user_id: str = None) -> Dict[str, Any]:
        """
        获取用户信息
        
        Args:
            event: 消息事件
            target_user_id: 目标用户ID（如果为None则获取发送者信息）
            
        Returns:
            包含用户信息的字典
        """
        user_id = target_user_id or event.get_sender_id()
        
        try:
            # 获取基础信息
            user_info = self._get_basic_info(event, user_id, target_user_id)
            
            # 尝试从tip内容获取增强信息
            tip_info = self._extract_tip_info(event, user_id, target_user_id)
            if tip_info:
                user_info.update(tip_info)
                
            return user_info
            
        except Exception as e:
            logger.error(f"[UserInfoManager] 获取用户信息失败: {user_id}, 错误: {e}")
            return self._get_fallback_info(event, user_id, target_user_id)
    
    def _get_basic_info(self, event: AstrMessageEvent, user_id: str, target_user_id: str = None) -> Dict[str, Any]:
        """获取基础用户信息"""
        if not target_user_id:
            # 获取发送者信息
            nickname = event.get_sender_name() or f"用户{user_id[-6:]}"
        else:
            # 获取目标用户信息
            nickname = f"用户{user_id[-6:]}"
            
        return {
            "user_id": user_id,
            "nickname": nickname,
            "card": nickname,
            "title": "无",
            "sex": "unknown",
            "platform": event.get_platform_name(),
            "group_id": event.get_group_id() or ""
        }
    
    def _extract_tip_info(self, event: AstrMessageEvent, user_id: str, target_user_id: str = None) -> Optional[Dict[str, Any]]:
        """从tip内容提取用户信息"""
        try:
            message_str = event.message_obj.message_str
            if not message_str or "<tip>" not in message_str:
                return None
                
            # 提取tip内容
            start_idx = message_str.find("<tip>")
            end_idx = message_str.find("</tip>")
            if start_idx == -1 or end_idx == -1:
                return None
                
            tip_content = message_str[start_idx + 5:end_idx].strip()
            
            # 解析JSON
            json_start = tip_content.find("{")
            if json_start == -1:
                return None
                
            json_str = tip_content[json_start:]
            
            # 修复JSON格式
            json_str = self._fix_json(json_str)
            if not json_str:
                return None
                
            data = json.loads(json_str)
            
            # 提取用户信息
            if target_user_id:
                return self._extract_target_user(data, target_user_id)
            else:
                return self._extract_sender(data, user_id)
                
        except Exception as e:
            logger.debug(f"[UserInfoManager] tip信息提取失败: {e}")
            return None
    
    def _fix_json(self, json_str: str) -> Optional[str]:
        """修复JSON格式"""
        try:
            # 截取到最后一个}
            last_brace = json_str.rfind('}')
            if last_brace != -1:
                json_str = json_str[:last_brace + 1]
            
            # 替换Python字面量
            json_str = (json_str.replace("True", "true")
                              .replace("False", "false")
                              .replace("None", "null"))
            
            # 修复单引号键名
            json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
            
            return json_str
        except Exception:
            return None
    
    def _extract_sender(self, data: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
        """从tip数据提取发送者信息"""
        try:
            sender = data.get("sender", {})
            if sender and str(sender.get("user_id")) == str(user_id):
                return self._normalize_data(sender)
        except Exception:
            pass
        return None
    
    def _extract_target_user(self, data: Dict[str, Any], target_user_id: str) -> Optional[Dict[str, Any]]:
        """从tip数据提取目标用户信息"""
        try:
            # 查找ater1-ater20
            for i in range(1, 21):
                ater_key = f"ater{i}"
                if ater_key in data:
                    ater_info = data[ater_key]
                    if str(ater_info.get("user_id")) == str(target_user_id):
                        return self._normalize_data(ater_info)
        except Exception:
            pass
        return None
    
    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化用户数据"""
        normalized = {}
        
        if data.get("nickname"):
            normalized["nickname"] = str(data["nickname"])
        if data.get("card"):
            normalized["card"] = str(data["card"])
        if data.get("title"):
            normalized["title"] = str(data["title"])
        if data.get("sex"):
            normalized["sex"] = str(data["sex"])
        
        return normalized
    
    def _get_fallback_info(self, event: AstrMessageEvent, user_id: str, target_user_id: str = None) -> Dict[str, Any]:
        """获取降级用户信息"""
        nickname = f"用户{user_id[-6:]}"
        if not target_user_id:
            nickname = event.get_sender_name() or nickname
            
        return {
            "user_id": user_id,
            "nickname": nickname,
            "card": nickname,
            "title": "无",
            "sex": "unknown",
            "platform": event.get_platform_name(),
            "group_id": event.get_group_id() or ""
        }
    
    def get_target_user_from_event(self, event: AstrMessageEvent) -> Tuple[Optional[str], Optional[str]]:
        """
        从事件中提取@的目标用户
        
        Args:
            event: 消息事件
            
        Returns:
            (用户ID, 昵称) 元组
        """
        try:
            for comp in event.message_obj.message:
                if isinstance(comp, Comp.At):
                    user_id = str(comp.qq)
                    nickname = f"用户{user_id[-6:]}"
                    return user_id, nickname
        except Exception as e:
            logger.debug(f"[UserInfoManager] 提取目标用户失败: {e}")
            
        return None, None
