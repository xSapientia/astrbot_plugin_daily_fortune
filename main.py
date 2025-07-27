"""
每日人品值和运势查询插件 - 主入口
"""

from pathlib import Path
from functools import wraps
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

# 导入核心模块
from .core import FortuneAlgorithm, Storage, UserInfoManager, LLMManager, GroupWhitelistManager
from .command import CommandHandler


@register(
    "astrbot_plugin_daily_fortune",
    "xSapientia",
    "每日人品值和运势查询插件，支持排行榜和历史记录",
    "0.1.1",
    "https://github.com/xSapientia/astrbot_plugin_daily_fortune"
)
class DailyFortunePlugin(Star):
    """每日人品插件主类"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        """
        初始化插件
        
        Args:
            context: AstrBot上下文
            config: 插件配置
        """
        super().__init__(context)
        self.config = config
        
        # 获取插件元数据
        try:
            # 尝试从注册信息中获取
            star_metadata = self.context.get_registered_star("astrbot_plugin_daily_fortune")
            self.plugin_name = star_metadata.name if star_metadata else "astrbot_plugin_daily_fortune"
        except:
            # 如果获取失败，使用默认名称
            self.plugin_name = "astrbot_plugin_daily_fortune"
        
        # 初始化核心模块
        self.storage = Storage(plugin_name=self.plugin_name)
        self.algorithm = FortuneAlgorithm(config)
        self.user_info = UserInfoManager(context)
        self.llm = LLMManager(context, config)
        self.whitelist = GroupWhitelistManager(config)
        
        # 初始化指令处理器
        self.handler = CommandHandler(self)
        
        logger.info(f"{self.plugin_name} 插件已加载")
    
    def _check_whitelist_permission(self, event: AstrMessageEvent) -> bool:
        """
        检查群聊白名单权限
        
        Args:
            event: AstrMessageEvent 事件对象
            
        Returns:
            bool: 是否有权限使用插件
        """
        return self.whitelist.can_use_plugin(event)
        
    @filter.command("jrrp")
    async def jrrp(self, event: AstrMessageEvent, subcommand: str = ""):
        """今日人品查询"""
        if not self._check_whitelist_permission(event):
            event.stop_event()  # 终止事件传播，阻止AstrBot本身的LLM调用
            return
            
        async for result in self.handler.handle_jrrp(event, subcommand):
            yield result
            
    @filter.command("jrrprank")
    async def jrrprank(self, event: AstrMessageEvent):
        """群内今日人品排行榜"""
        if not self._check_whitelist_permission(event):
            event.stop_event()  # 终止事件传播，阻止AstrBot本身的LLM调用
            return
            
        async for result in self.handler.handle_jrrprank(event):
            yield result
            
    @filter.command("jrrphistory", alias={"jrrphi"})
    async def jrrphistory(self, event: AstrMessageEvent):
        """查看人品历史记录"""
        if not self._check_whitelist_permission(event):
            event.stop_event()  # 终止事件传播，阻止AstrBot本身的LLM调用
            return
            
        async for result in self.handler.handle_jrrphistory(event):
            yield result
            
    @filter.command("jrrpdelete", alias={"jrrpdel"})
    async def jrrpdelete(self, event: AstrMessageEvent, confirm: str = ""):
        """删除个人人品历史记录（保留今日）"""
        if not self._check_whitelist_permission(event):
            event.stop_event()  # 终止事件传播，阻止AstrBot本身的LLM调用
            return
            
        async for result in self.handler.handle_jrrpdelete(event, confirm):
            yield result
            
    @filter.command("jrrpinitialize", alias={"jrrpinit"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def jrrpinitialize(self, event: AstrMessageEvent, confirm: str = ""):
        """初始化今日人品记录（仅管理员）"""
        if not self._check_whitelist_permission(event):
            event.stop_event()  # 终止事件传播，阻止AstrBot本身的LLM调用
            return
            
        async for result in self.handler.handle_jrrpinitialize(event, confirm):
            yield result
            
    @filter.command("jrrpreset", alias={"jrrpre"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def jrrpreset(self, event: AstrMessageEvent, confirm: str = ""):
        """重置所有人品数据（仅管理员）"""
        if not self._check_whitelist_permission(event):
            event.stop_event()  # 终止事件传播，阻止AstrBot本身的LLM调用
            return
            
        async for result in self.handler.handle_jrrpreset(event, confirm):
            yield result
            
    @filter.command("jrrpwhitelist", alias={"jrrpwl"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def jrrpwhitelist(self, event: AstrMessageEvent, action: str = ""):
        """群聊白名单管理（仅管理员）"""
        if not self._check_whitelist_permission(event):
            event.stop_event()  # 终止事件传播，阻止AstrBot本身的LLM调用
            return
            
        if action == "status":
            # 查看白名单状态
            status_info = self.whitelist.get_whitelist_info()
            groups = self.whitelist.get_whitelist_groups()
            
            response = f"📋 群聊白名单状态\n{status_info}"
            if groups:
                response += f"\n\n🏠 白名单群聊列表:\n"
                for i, group_id in enumerate(groups, 1):
                    response += f"{i}. {group_id}\n"
            yield event.plain_result(response)
            
        elif action == "reload":
            # 重新加载白名单配置
            self.whitelist.reload_config()
            yield event.plain_result("✅ 群聊白名单配置已重新加载")
            
        else:
            # 显示帮助信息
            help_text = (
                "📋 群聊白名单管理命令\n\n"
                "/jrrpwhitelist status - 查看白名单状态\n"
                "/jrrpwhitelist reload - 重新加载配置\n\n"
                "💡 提示：白名单配置请在插件管理页面进行修改"
            )
            yield event.plain_result(help_text)
            
    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info(f"{self.plugin_name} 插件正在卸载...")
        
        # 调用存储模块的清理方法
        self.storage.cleanup_data(
            delete_data=self.config.get("delete_data_on_uninstall", False),
            delete_config=self.config.get("delete_config_on_uninstall", False),
            config_name=self.plugin_name
        )
        
        logger.info(f"{self.plugin_name} 插件已卸载")
