"""
用户信息获取模块 - 基于aiocqhttp API的完美方案
参考GitHub代码，直接调用API获取真实用户信息
"""

from typing import Dict, Optional, Tuple, Any
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.api import logger
import astrbot.api.message_components as Comp


class UserInfoManager:
    """用户信息管理器 - API直接获取版"""
    
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
        获取用户信息 - 直接调用API
        
        Args:
            event: 消息事件
            target_user_id: 目标用户ID（如果为None则获取发送者信息）
            
        Returns:
            包含用户信息的字典
        """
        user_id = target_user_id or event.get_sender_id()
        
        # 获取基础信息
        if not target_user_id:
            # 获取发送者信息 - 需要调用API获取详细信息
            if event.get_platform_name() == "aiocqhttp":
                return await self._get_aiocqhttp_user_info(event, user_id)
            else:
                # 其他平台使用基础信息
                nickname = event.get_sender_name() or f"用户{user_id[-6:]}"
                return {
                    "user_id": user_id,
                    "nickname": nickname,
                    "card": nickname,
                    "title": "无",
                    "sex": "unknown",
                    "platform": event.get_platform_name(),
                    "group_id": event.get_group_id() or ""
                }
        
        # 获取@用户的详细信息
        if event.get_platform_name() == "aiocqhttp":
            return await self._get_aiocqhttp_user_info(event, user_id)
        else:
            # 其他平台使用基础信息
            return {
                "user_id": user_id,
                "nickname": f"用户{user_id[-6:]}",
                "card": f"用户{user_id[-6:]}",
                "title": "无", 
                "sex": "unknown",
                "platform": event.get_platform_name(),
                "group_id": event.get_group_id() or ""
            }
    
    async def _get_aiocqhttp_user_info(self, event: AstrMessageEvent, user_id: str) -> Dict[str, Any]:
        """
        从aiocqhttp获取用户详细信息 - 参考GitHub完美方案
        
        Args:
            event: 消息事件
            user_id: 用户ID
            
        Returns:
            用户信息字典
        """
        try:
            # 获取aiocqhttp client
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            if isinstance(event, AiocqhttpMessageEvent):
                client = event.bot
                
                # 获取陌生人信息
                stranger_info = {}
                try:
                    stranger_info = await client.get_stranger_info(
                        user_id=int(user_id), no_cache=True
                    )
                except Exception as e:
                    logger.debug(f"[UserInfoManager] 获取陌生人信息失败: {e}")
                
                # 获取群成员信息
                member_info = {}
                group_id = event.get_group_id()
                if group_id:
                    try:
                        member_info = await client.get_group_member_info(
                            user_id=int(user_id), group_id=int(group_id)
                        )
                    except Exception as e:
                        logger.debug(f"[UserInfoManager] 获取群成员信息失败: {e}")
                
                # 组合信息
                nickname = stranger_info.get("nickname") or f"用户{user_id[-6:]}"
                card = member_info.get("card") or nickname
                title = member_info.get("title") or "无"
                sex = stranger_info.get("sex") or "unknown"
                
                return {
                    "user_id": user_id,
                    "nickname": nickname,
                    "card": card,
                    "title": title,
                    "sex": sex,
                    "platform": "aiocqhttp",
                    "group_id": group_id or ""
                }
                
        except Exception as e:
            logger.error(f"[UserInfoManager] aiocqhttp信息获取失败: {e}")
        
        # 降级处理
        return {
            "user_id": user_id,
            "nickname": f"用户{user_id[-6:]}",
            "card": f"用户{user_id[-6:]}",
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
