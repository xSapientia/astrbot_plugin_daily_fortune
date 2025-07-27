"""
指令处理核心模块
"""

from typing import Optional, Tuple, TYPE_CHECKING
from datetime import datetime
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

if TYPE_CHECKING:
    from ..main import DailyFortunePlugin


class CommandHandler:
    """指令处理器"""
    
    def __init__(self, plugin: 'DailyFortunePlugin'):
        """
        初始化指令处理器
        
        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.config = plugin.config
        self.context = plugin.context
        self.storage = plugin.storage
        self.algorithm = plugin.algorithm
        self.user_info = plugin.user_info
        self.llm = plugin.llm
        
    def _has_confirm_param(self, event: AstrMessageEvent) -> bool:
        """检查消息中是否包含 --confirm 参数"""
        return "--confirm" in event.message_str.lower()
        
    def _parse_list_string(self, list_str: str) -> list:
        """解析逗号分隔的字符串列表"""
        try:
            return [item.strip() for item in list_str.split(',') if item.strip()]
        except Exception as e:
            logger.error(f"[daily_fortune] 解析字符串列表失败: {e}")
            return []
            
    async def handle_jrrp(self, event: AstrMessageEvent, subcommand: str = ""):
        """处理 /jrrp 指令"""
        # 处理help子命令
        if subcommand.lower() == "help":
            # help不需要LLM
            event.should_call_llm(False)
            help_text = """📖 每日人品插件指令帮助

🎲 基础指令：
• 查询自己的今日人品值
    - jrrp
• 查询他人的今日人品值
    - jrrp @某人
• 显示帮助信息
    - jrrp help

📊 排行榜：
• 查看群内今日人品排行榜
    - jrrp rank
    - jrrprank

📚 历史记录：
• 查看历史记录
    - jrrp history
    - jrrp hi
    - jrrphistory
    - jrrphi
• 查看他人历史记录
    - jrrp history @某人
    - jrrphistory @某人

🗑️ 数据管理：
• 删除除今日外的历史记录
    - jrrp delete --confirm
    - jrrp del --confirm
    - jrrpdelete --confirm
    - jrrpdel --confirm

⚙️ 管理员指令：
• 初始化今日记录
    - jrrp init --confirm
    - jrrp initialize --confirm
    - jrrpinit --confirm
    - jrrpinitialize --confirm
• 初始化他人今日记录
    - jrrp init @某人 --confirm
    - jrrpinit @某人 --confirm
• 重置所有数据
    - jrrp reset --confirm
    - jrrp re --confirm
    - jrrpreset --confirm
    - jrrpre --confirm

💡 提示：带 --confirm 的指令需要确认参数才能执行"""
            yield event.plain_result(help_text)
            return
            
        # 处理其他子命令
        if subcommand.lower() == "rank":
            # 直接调用排行榜处理
            async for result in self.handle_jrrprank(event):
                yield result
            return
        
        elif subcommand.lower() in ["history", "hi"]:
            # 直接调用历史记录处理
            async for result in self.handle_jrrphistory(event):
                yield result
            return
        
        elif subcommand.lower() in ["init", "initialize"]:
            # 初始化指令需要管理员权限
            if not event.is_admin():
                yield event.plain_result("❌ 此操作需要管理员权限")
                return
            # 检查是否有 --confirm 参数
            confirm_param = "--confirm" if self._has_confirm_param(event) else ""
            # 直接调用初始化处理
            async for result in self.handle_jrrpinitialize(event, confirm_param):
                yield result
            return
        
        elif subcommand.lower() in ["delete", "del"]:
            # 检查是否有 --confirm 参数
            confirm_param = "--confirm" if self._has_confirm_param(event) else ""
            async for result in self.handle_jrrpdelete(event, confirm_param):
                yield result
            return
            
        elif subcommand.lower() in ["reset", "re"]:
            # 重置指令需要管理员权限
            if not event.is_admin():
                yield event.plain_result("❌ 此操作需要管理员权限")
                return
            # 检查是否有 --confirm 参数
            confirm_param = "--confirm" if self._has_confirm_param(event) else ""
            async for result in self.handle_jrrpreset(event, confirm_param):
                yield result
            return
            
        # 检查是否有@某人
        target_user_id, target_nickname = self.user_info.get_target_user_from_event(event)
        
        # 如果是查询他人 - 不需要LLM
        if target_user_id:
            event.should_call_llm(False)
            
            today = self.algorithm.get_today_key()
            sender_info = await self.user_info.get_user_info(event)
            sender_nickname = sender_info["nickname"]
            
            # 获取被查询者的用户信息
            target_user_info = await self.user_info.get_user_info(event, target_user_id)
            target_nickname = target_user_info["nickname"]
            
            # 检查对方是否已经查询过
            cached = self.storage.get_today_fortune(today, target_user_id)
            if not cached:
                # 使用配置的未查询提示信息，支持所有变量
                not_queried_template = self.config.get("others_not_queried_message",
                    "{target_nickname} 今天还没有查询过人品值呢~")
                    
                # 准备变量字典，包含所有可能的变量
                vars_dict = {
                    "target_nickname": target_nickname,
                    "target_user_id": target_user_id,
                    "sender_nickname": sender_nickname,
                    "nickname": target_nickname,  # 兼容原有变量
                    "card": target_user_info["card"],
                    "title": target_user_info["title"],
                    "date": today,
                    # 由于对方未查询，这些值为空或默认值
                    "jrrp": "未知",
                    "fortune": "未知",
                    "femoji": "❓",
                    "process": "",
                    "advice": "",
                    "avgjrrp": 0,
                    "maxjrrp": 0,
                    "minjrrp": 0,
                    "ranks": "",
                    "medal": "",
                    "medals": self.config.get("medals", "🥇, 🥈, 🥉, 🏅, 🏅"),
                    **self.algorithm.get_fortune_variables()
                }
                
                result = not_queried_template.format(**vars_dict)
                yield event.plain_result(result)
                return
                
            # 获取对方的查询结果
            jrrp = cached["jrrp"]
            fortune, femoji = self.algorithm.get_fortune_info(jrrp)
            target_nickname = cached.get("nickname", target_nickname)
            
            # 构建查询模板，支持所有变量
            query_template = self.config.get("templates", {}).get("query_template",
                "📌 今日人品\n{nickname}，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}")
                
            # 准备变量字典
            vars_dict = {
                "nickname": target_nickname,
                "card": target_user_info["card"],
                "title": target_user_info["title"],
                "jrrp": jrrp,
                "fortune": fortune,
                "femoji": femoji,
                "date": today,
                "process": cached.get("process", ""),
                "advice": cached.get("advice", ""),
                "target_nickname": target_nickname,
                "target_user_id": target_user_id,
                "sender_nickname": sender_nickname,
                # 统计信息（如果需要的话）
                "avgjrrp": jrrp,  # 单个用户的平均值就是当前值
                "maxjrrp": jrrp,
                "minjrrp": jrrp,
                "ranks": "",
                "medal": "",
                "medals": self.config.get("medals", "🥇, 🥈, 🥉, 🏅, 🏅"),
                **self.algorithm.get_fortune_variables()
            }
            
            result = query_template.format(**vars_dict)
            
            # 检查是否显示对方的缓存完整结果
            if self.config.get("show_others_cached_result", False) and "result" in cached:
                result += f"\n\n-----以下为{target_nickname}的今日运势测算场景还原-----\n{cached['result']}"
                
            yield event.plain_result(result)
            return
            
        # 查询自己的人品
        user_info = await self.user_info.get_user_info(event)
        user_id = user_info["user_id"]
        nickname = user_info["nickname"]
        today = self.algorithm.get_today_key()
        
        # 检查用户是否正在处理中
        if self.storage.is_user_processing(user_id):
            # 用户正在处理中，彻底阻止事件传播和LLM调用
            event.should_call_llm(False)
            event.stop_event()
            processing_msg = self.config.get("processing_message",
                "已经在努力获取 {nickname} 的命运了哦~")
            yield event.plain_result(processing_msg.format(nickname=nickname))
            return
            
        # 检查是否已经查询过
        cached = self.storage.get_today_fortune(today, user_id)
        if cached:
            # 已查询，返回缓存结果 - 不需要LLM
            event.should_call_llm(False)
            
            jrrp = cached["jrrp"]
            fortune, femoji = self.algorithm.get_fortune_info(jrrp)
            
            # 构建查询模板
            query_template = self.config.get("templates", {}).get("query_template",
                "📌 今日人品\n{nickname}，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}")
                
            # 准备变量字典
            vars_dict = {
                "nickname": nickname,
                "card": user_info["card"],
                "title": user_info["title"],
                "jrrp": jrrp,
                "fortune": fortune,
                "femoji": femoji,
                "date": today,
                "process": cached.get("process", ""),
                "advice": cached.get("advice", ""),
                # 统计信息
                "avgjrrp": jrrp,
                "maxjrrp": jrrp,
                "minjrrp": jrrp,
                "ranks": "",
                "medal": "",
                "medals": self.config.get("medals", "🥇, 🥈, 🥉, 🏅, 🏅"),
                **self.algorithm.get_fortune_variables()
            }
            
            result = query_template.format(**vars_dict)
            
            # 如果配置启用了显示缓存结果
            if self.config.get("show_cached_result", True) and "result" in cached:
                result += f"\n\n-----以下为今日运势测算场景还原-----\n{cached['result']}"
                
            yield event.plain_result(result)
            return
            
        # 首次查询，阻止默认的LLM调用（我们自己控制LLM调用）
        event.should_call_llm(False)
        
        # 将用户添加到正在处理的集合中
        self.storage.add_processing_user(user_id)
        
        try:
            # 显示检测中消息
            detecting_msg = self.config.get("detecting_message",
                "神秘的能量汇聚，{nickname}，你的命运即将显现，正在祈祷中...")
            yield event.plain_result(detecting_msg.format(nickname=nickname))
            
            # 计算人品值
            jrrp = self.algorithm.calculate_jrrp(user_id)
            fortune, femoji = self.algorithm.get_fortune_info(jrrp)
            
            # 准备LLM生成的变量
            vars_dict = {
                "user_id": user_id,
                "nickname": nickname,
                "card": user_info["card"],
                "title": user_info["title"],
                "jrrp": jrrp,
                "fortune": fortune,
                "femoji": femoji,
                "date": today,
                "medals": self.config.get("medals", "🥇, 🥈, 🥉, 🏅, 🏅"),
                **self.algorithm.get_fortune_variables()
            }
            
            # 生成内容（一次调用生成过程和建议）
            process, advice = await self.llm.generate_fortune_content(vars_dict)
            
            # 构建结果
            result_template = self.config.get("templates", {}).get("resault_template",
                "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}")
                
            result = result_template.format(
                process=process,
                jrrp=jrrp,
                fortune=fortune,
                advice=advice
            )
            
            # 缓存结果
            fortune_data = {
                "jrrp": jrrp,
                "fortune": fortune,
                "process": process,
                "advice": advice,
                "result": result,
                "nickname": nickname,
                "timestamp": datetime.now().isoformat()
            }
            self.storage.save_today_fortune(today, user_id, fortune_data)
            
            yield event.plain_result(result)
            
        finally:
            # 确保在处理完成后从集合中移除用户
            self.storage.remove_processing_user(user_id)
            
    async def handle_jrrprank(self, event: AstrMessageEvent):
        """处理 /jrrprank 指令"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        if event.is_private_chat():
            yield event.plain_result("排行榜功能仅在群聊中可用")
            return
            
        today = self.algorithm.get_today_key()
        
        # 获取今日所有运势数据
        today_fortunes = self.storage.get_today_all_fortunes(today)
        if not today_fortunes:
            yield event.plain_result("今天还没有人查询过人品值呢~")
            return
            
        # 获取群成员的人品值
        group_data = []
        for user_id, data in today_fortunes.items():
            group_data.append({
                "user_id": user_id,
                "nickname": data.get("nickname", "未知"),
                "jrrp": data["jrrp"],
                "fortune": data.get("fortune", "未知")
            })
            
        # 排序
        group_data.sort(key=lambda x: x["jrrp"], reverse=True)
        
        # 获取奖牌配置
        medals = self._parse_list_string(self.config.get("medals", "🥇, 🥈, 🥉, 🏅, 🏅"))
        if not medals:
            medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
            
        # 构建排行榜
        rank_template = self.config.get("templates", {}).get("rank_template",
            "{medal} {nickname}: {jrrp} ({fortune})")
            
        ranks = []
        
        for i, user in enumerate(group_data[:10]):  # 只显示前10名
            medal = medals[i] if i < len(medals) else medals[-1] if medals else "🏅"
            rank_line = rank_template.format(
                medal=medal,
                nickname=user["nickname"],
                jrrp=user["jrrp"],
                fortune=user["fortune"]
            )
            ranks.append(rank_line)
            
        # 构建完整排行榜
        board_template = self.config.get("templates", {}).get("rank_board_template",
            "📊【今日人品排行榜】{date}\n━━━━━━━━━━━━━━━\n{ranks}")
            
        result = board_template.format(
            date=today,
            ranks="\n".join(ranks)
        )
        
        yield event.plain_result(result)
        
    async def handle_jrrphistory(self, event: AstrMessageEvent):
        """处理 /jrrphistory 指令"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        # 检查是否有@某人
        target_user_id, target_nickname = self.user_info.get_target_user_from_event(event)
        
        if not target_user_id:
            target_user_id = event.get_sender_id()
            target_nickname = event.get_sender_name()
        else:
            # 获取被@用户的信息
            target_user_info = await self.user_info.get_user_info(event, target_user_id)
            target_nickname = target_user_info["nickname"]
            
        # 获取历史天数配置
        history_days = self.config.get("history_days", 30)
        user_history = self.storage.get_user_history(target_user_id, history_days)
        
        if not user_history:
            yield event.plain_result(f"{target_nickname} 还没有任何人品记录呢~")
            return
            
        # 获取统计数据
        stats = self.storage.get_user_statistics(target_user_id)
        
        # 构建历史记录列表
        history_lines = []
        for date, data in list(user_history.items())[:10]:  # 只显示最近10条
            history_lines.append(f"{date}: {data['jrrp']} ({data['fortune']})")
            
        # 使用模板
        history_template = self.config.get("templates", {}).get("history_template",
            "📚 {nickname} 的人品历史记录\n{history}\n\n📊 统计信息:\n平均人品值: {avgjrrp}\n最高人品值: {maxjrrp}\n最低人品值: {minjrrp}")
            
        result = history_template.format(
            nickname=target_nickname,
            history="\n".join(history_lines),
            avgjrrp=stats["avg"],
            maxjrrp=stats["max"],
            minjrrp=stats["min"]
        )
        
        yield event.plain_result(result)
        
    async def handle_jrrpdelete(self, event: AstrMessageEvent, confirm: str = ""):
        """处理 /jrrpdelete 指令"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        # 只能删除自己的数据
        target_user_id = event.get_sender_id()
        target_nickname = event.get_sender_name()
        
        # 检查确认参数
        if confirm != "--confirm" and not self._has_confirm_param(event):
            yield event.plain_result(f"⚠️ 警告：此操作将删除您的除今日以外的所有人品历史记录！\n如确认删除，请使用：/jrrpdelete --confirm")
            return
            
        today = self.algorithm.get_today_key()
        deleted_count = self.storage.delete_user_history(target_user_id, today)
        
        yield event.plain_result(f"✅ 已删除您的除今日以外的人品历史记录（共 {deleted_count} 条）")
        
    async def handle_jrrpinitialize(self, event: AstrMessageEvent, confirm: str = ""):
        """处理 /jrrpinitialize 指令（仅管理员）"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        # 检查是否有@某人
        target_user_id, target_nickname = self.user_info.get_target_user_from_event(event)
        is_target_others = target_user_id is not None
        
        if not target_user_id:
            target_user_id = event.get_sender_id()
            target_nickname = event.get_sender_name()
        else:
            # 获取被@用户的信息
            target_user_info = await self.user_info.get_user_info(event, target_user_id)
            target_nickname = target_user_info["nickname"]
            
        # 检查确认参数
        if confirm != "--confirm" and not self._has_confirm_param(event):
            action_desc = f"{target_nickname} 的" if is_target_others else "您的"
            cmd_example = f"/jrrpinit @{target_nickname} --confirm" if is_target_others else "/jrrpinit --confirm"
            yield event.plain_result(f"⚠️ 警告：此操作将删除 {action_desc}今日人品记录，使其可以重新随机！\n如确认初始化，请使用：{cmd_example}")
            return
            
        today = self.algorithm.get_today_key()
        deleted = self.storage.clear_today_fortune(today, target_user_id)
        
        action_desc = f"{target_nickname} 的" if is_target_others else "您的"
        if deleted:
            yield event.plain_result(f"✅ 已初始化 {action_desc}今日人品记录，现在可以重新使用 /jrrp 随机人品值了")
        else:
            yield event.plain_result(f"ℹ️ {action_desc}今日还没有人品记录，无需初始化")
            
    async def handle_jrrpreset(self, event: AstrMessageEvent, confirm: str = ""):
        """处理 /jrrpreset 指令（仅管理员）"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        # 检查确认参数
        if confirm != "--confirm" and not self._has_confirm_param(event):
            yield event.plain_result("⚠️ 警告：此操作将删除所有用户的人品数据！\n如确认重置，请使用：/jrrpreset --confirm")
            return
            
        # 清空所有数据
        self.storage.reset_all_data()
        
        yield event.plain_result("✅ 所有人品数据已重置")
