"""
群聊白名单管理模块
"""

from typing import Set, List
from astrbot.api import logger


class GroupWhitelistManager:
    """群聊白名单管理器"""
    
    def __init__(self, config):
        """
        初始化群聊白名单管理器
        
        Args:
            config: 插件配置对象
        """
        self.config = config
        self._whitelist_groups: Set[str] = set()
        self._load_whitelist()
    
    def _load_whitelist(self):
        """从配置中加载群聊白名单"""
        try:
            # 获取群聊白名单配置
            whitelist_config = self.config.get("group_whitelist", {})
            groups_list = whitelist_config.get("groups", [])
            
            # 清空现有白名单
            self._whitelist_groups.clear()
            
            # 解析群号列表
            if groups_list and isinstance(groups_list, list):
                # 将所有群号转换为字符串并加入白名单
                for group in groups_list:
                    if group:  # 确保不是空值
                        self._whitelist_groups.add(str(group).strip())
                
                logger.info(f"群聊白名单已加载，共 {len(self._whitelist_groups)} 个群聊")
            else:
                logger.info("群聊白名单为空")
                
        except Exception as e:
            logger.error(f"加载群聊白名单失败: {e}")
            self._whitelist_groups.clear()
    
    def is_whitelist_enabled(self) -> bool:
        """
        检查群聊白名单功能是否启用
        
        Returns:
            bool: 白名单功能是否启用
        """
        try:
            whitelist_config = self.config.get("group_whitelist", {})
            return whitelist_config.get("enable", False)
        except Exception as e:
            logger.error(f"检查白名单启用状态失败: {e}")
            return False
    
    def is_group_allowed(self, group_id: str) -> bool:
        """
        检查群聊是否在白名单中
        
        Args:
            group_id: 群聊ID
            
        Returns:
            bool: 群聊是否被允许使用插件
        """
        # 如果白名单功能未启用，则允许所有群聊
        if not self.is_whitelist_enabled():
            return True
        
        # 如果白名单为空，则即使启用了白名单功能也默认无效
        if not self._whitelist_groups:
            logger.debug("群聊白名单为空，默认允许所有群聊")
            return True
        
        # 检查群聊是否在白名单中
        is_allowed = str(group_id) in self._whitelist_groups
        logger.debug(f"群聊 {group_id} 白名单检查结果: {is_allowed}")
        return is_allowed
    
    def can_use_plugin(self, event) -> bool:
        """
        检查事件来源是否可以使用插件
        
        Args:
            event: AstrMessageEvent 事件对象
            
        Returns:
            bool: 是否可以使用插件
        """
        try:
            # 如果白名单功能未启用，则允许所有用户使用
            if not self.is_whitelist_enabled():
                return True
            
            # 如果是私聊，则允许使用
            if event.is_private_chat():
                return True
            
            # 如果是群聊，检查群聊是否在白名单中
            group_id = event.get_group_id()
            if group_id:
                return self.is_group_allowed(group_id)
            
            # 其他情况默认允许
            return True
            
        except Exception as e:
            logger.error(f"检查插件使用权限失败: {e}")
            # 出现错误时默认允许使用，避免影响正常功能
            return True
    
    def get_whitelist_groups(self) -> List[str]:
        """
        获取白名单群聊列表
        
        Returns:
            List[str]: 白名单群聊ID列表
        """
        return list(self._whitelist_groups)
    
    def get_whitelist_info(self) -> str:
        """
        获取白名单信息描述
        
        Returns:
            str: 白名单信息描述
        """
        if not self.is_whitelist_enabled():
            return "群聊白名单功能未启用"
        
        if not self._whitelist_groups:
            return "群聊白名单功能已启用，但白名单为空（所有群聊均可使用）"
        
        return f"群聊白名单功能已启用，共 {len(self._whitelist_groups)} 个群聊在白名单中"
    
    def reload_config(self):
        """重新加载配置"""
        logger.info("重新加载群聊白名单配置")
        self._load_whitelist()
