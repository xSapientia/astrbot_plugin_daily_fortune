"""
用户信息获取模块
"""

from typing import Dict, Optional, Tuple
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.api import logger
import astrbot.api.message_components as Comp


class UserInfoManager:
    """用户信息管理器"""
    
    def __init__(self, context: Context):
        """
        初始化用户信息管理器
        
        Args:
            context: AstrBot上下文
        """
        self.context = context
        
    async def get_user_info(self, event: AstrMessageEvent, target_user_id: str = None) -> Dict[str, str]:
        """
        获取用户信息（从rawmessage_viewer1插件）
        
        Args:
            event: 消息事件
            target_user_id: 目标用户ID（如果为None则获取发送者信息）
            
        Returns:
            包含用户信息的字典
        """
        user_id = target_user_id or event.get_sender_id()
        nickname = event.get_sender_name() if not target_user_id else f"用户{target_user_id}"
        card = nickname  # 默认值
        title = "无"  # 默认值
        
        # 尝试从rawmessage_viewer1插件获取增强信息
        try:
            if event.get_platform_name() == "aiocqhttp":
                # 如果是查询自己，直接从事件的raw_message获取信息
                if not target_user_id:
                    raw_message = event.message_obj.raw_message
                    if isinstance(raw_message, dict):
                        sender = raw_message.get("sender", {})
                        if sender:
                            # 优先使用原始消息中的信息
                            nickname = sender.get("nickname", nickname)
                            card = sender.get("card", "") or nickname
                            title = sender.get("title", "") or "无"
                            
                            # 调试日志
                            logger.debug(f"[daily_fortune] 从raw_message获取用户信息: user_id={user_id}, nickname={nickname}, card={card}, title={title}")
                            
                # 如果raw_message中没有，或者是查询他人，再尝试从插件获取
                if (card == nickname and title == "无") or target_user_id:
                    message_id = event.message_obj.message_id
                    plugins = self.context.get_all_stars()
                    for plugin_meta in plugins:
                        if plugin_meta.metadata.name == "astrbot_plugin_rawmessage_viewer1":
                            plugin_instance = plugin_meta.instance
                            if hasattr(plugin_instance, 'enhanced_messages'):
                                enhanced_msg = plugin_instance.enhanced_messages.get(message_id, {})
                                if enhanced_msg:
                                    # 如果是查询自己，确保获取的是当前消息的发送者信息
                                    if not target_user_id:
                                        msg_sender = enhanced_msg.get("sender", {})
                                        if msg_sender.get("user_id") == int(user_id):
                                            nickname = msg_sender.get("nickname", nickname)
                                            card = msg_sender.get("card", nickname)
                                            title = msg_sender.get("title", "无")
                                            logger.debug(f"[daily_fortune] 从rawmessage_viewer1获取用户信息: user_id={user_id}, nickname={nickname}, card={card}, title={title}")
                                    else:
                                        # 查询他人时，尝试从@信息中获取
                                        for i in range(1, 10):  # 检查ater1到ater9
                                            ater_key = f"ater{i}"
                                            if ater_key in enhanced_msg:
                                                ater_info = enhanced_msg[ater_key]
                                                if str(ater_info.get("user_id")) == str(target_user_id):
                                                    nickname = ater_info.get("nickname", nickname)
                                                    card = ater_info.get("card", nickname)
                                                    title = ater_info.get("title", "无")
                                                    logger.debug(f"[daily_fortune] 从ater信息获取用户信息: user_id={user_id}, nickname={nickname}, card={card}, title={title}")
                                                    break
                            break
        except Exception as e:
            logger.debug(f"获取增强用户信息失败: {e}")
            
        # 确保card有值
        if not card or card == "":
            card = nickname
            
        return {
            "user_id": user_id,
            "nickname": nickname,
            "card": card,
            "title": title
        }
        
    def get_target_user_from_event(self, event: AstrMessageEvent) -> Tuple[Optional[str], Optional[str]]:
        """
        从消息中提取目标用户ID和昵称
        
        Args:
            event: 消息事件
            
        Returns:
            (用户ID, 昵称) 元组，如果没有@任何人则返回 (None, None)
        """
        for comp in event.message_obj.message:
            if isinstance(comp, Comp.At):
                return str(comp.qq), f"用户{comp.qq}"
        return None, None
