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
• 查看自己的历史记录
    - jrrp history
    - jrrp hi
    - jrrphistory
    - jrrphi
• 查看他人历史记录
    - jrrp history @某人
    - jrrp hi @某人
    - jrrphistory @某人
    - jrrphi @某人

🗑️ 数据管理：
• 删除除今日外的历史记录
    - jrrp delete --confirm
    - jrrp del --confirm
    - jrrpdelete --confirm
    - jrrpdel --confirm

⚙️ 管理员指令：
• 初始化自己今日记录
    - jrrp initialize --confirm
    - jrrp init --confirm
    - jrrpinitialize --confirm
    - jrrpinit --confirm
• 初始化他人今日记录
    - jrrp initialize @某人 --confirm
    - jrrp init @某人 --confirm
    - jrrpinitialize @某人 --confirm
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
                # 使用配置的未查询提示信息，有@对象时{card}{nickname}{title}显示被@用户信息
                not_queried_template = self.config.get("others_not_queried_message",
                    "{card} 今天还没有查询过人品值呢~")
                    
                # 准备变量字典，有@对象时{card}{nickname}{title}为被@用户信息
                vars_dict = {
                    "nickname": target_nickname,  # 被@用户昵称
                    "card": target_user_info["card"] or target_nickname,  # 被@用户群名片，fallback到昵称
                    "title": target_user_info["title"],  # 被@用户头衔
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
            
            # 构建查询模板，有@对象时{card}{nickname}{title}显示被@用户信息
            query_template = self.config.get("templates", {}).get("query_template",
                "📌 今日人品\n{card}，今天已经查询过了哦~")
                
            # 准备变量字典，有@对象时{card}{nickname}{title}为被@用户信息
            vars_dict = {
                "nickname": target_nickname,  # 被@用户昵称
                "card": target_user_info["card"] or target_nickname,  # 被@用户群名片，fallback到昵称
                "title": target_user_info["title"],  # 被@用户头衔
                "jrrp": jrrp,
                "fortune": fortune,
                "femoji": femoji,
                "date": today,
                "process": cached.get("process", ""),
                "advice": cached.get("advice", ""),
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
            if self.config.get("show_others_cached_result", False):
                replay_template = self.config.get("replay_template", "-----以下为{card}的今日运势测算场景还原-----")
                replay_text = replay_template.format(**vars_dict)
                
                # 优先使用pure_result（不包含tip_template），如果没有则使用result
                replay_content = cached.get("pure_result", cached.get("result", ""))
                if replay_content:
                    result += f"\n\n{replay_text}\n{replay_content}"
                
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
                "已经在努力获取 {card} 的命运了哦~")
            # 无@对象时{card}{nickname}{title}为发送者信息
            vars_dict = {
                "nickname": nickname, 
                "card": user_info["card"] or nickname,
                "title": user_info["title"]
            }
            yield event.plain_result(processing_msg.format(**vars_dict))
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
                "📌 今日人品\n{card}，今天已经查询过了哦~")
                
            # 准备变量字典
            vars_dict = {
                "nickname": nickname,
                "card": user_info["card"] or nickname,  # 添加fallback机制
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
                "神秘的能量汇聚，{card}，你的命运即将显现，正在祈祷中...")
            # 无@对象时{card}{nickname}{title}为发送者信息
            vars_dict = {
                "nickname": nickname, 
                "card": user_info["card"] or nickname,
                "title": user_info["title"]
            }
            yield event.plain_result(detecting_msg.format(**vars_dict))
            
            # 计算人品值
            jrrp = self.algorithm.calculate_jrrp(user_id)
            fortune, femoji = self.algorithm.get_fortune_info(jrrp)
            
            # 准备LLM生成的变量
            vars_dict = {
                "user_id": user_id,
                "nickname": nickname,
                "card": user_info["card"] or nickname,  # 添加fallback机制
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
            
            # 为@查询他人场景还原准备的纯净结果（不包含tip_template）
            pure_result = result
            
            # 检查是否需要添加提示模板
            if self.config.get("templates", {}).get("enable_tip_template", False):
                tip_template = self.config.get("templates", {}).get("tip_template", "-----以下为{card}的今日运势测算结果-----")
                tip_text = tip_template.format(**vars_dict)
                result = f"{tip_text}\n{result}"
            
            # 缓存结果（包含群聊信息），保存两个版本
            fortune_data = {
                "jrrp": jrrp,
                "fortune": fortune,
                "process": process,
                "advice": advice,
                "result": result,          # 包含tip_template的完整结果
                "pure_result": pure_result, # 不包含tip_template的纯净结果
                "nickname": nickname,
                "group_id": event.get_group_id() or "",  # 记录查询时的群聊ID
                "timestamp": datetime.now().isoformat()
            }
            self.storage.save_today_fortune(today, user_id, fortune_data)
            
            yield event.plain_result(result)
            
        finally:
            # 确保在处理完成后从集合中移除用户
            self.storage.remove_processing_user(user_id)
            
    async def handle_jrrprank(self, event: AstrMessageEvent):
        """处理 /jrrprank 指令 - 群聊内成员排行榜"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        if event.is_private_chat():
            yield event.plain_result("排行榜功能仅在群聊中可用")
            return
            
        today = self.algorithm.get_today_key()
        current_group_id = event.get_group_id()
        
        # 获取今日所有运势数据
        today_fortunes = self.storage.get_today_all_fortunes(today)
        if not today_fortunes:
            yield event.plain_result("今天还没有人查询过人品值呢~")
            return
            
        # 使用高效的群成员缓存机制
        group_data = await self._get_group_ranking_data(event, today_fortunes, current_group_id)
            
        if not group_data:
            yield event.plain_result("本群今天还没有人查询过人品值呢~")
            return
            
        # 排序
        group_data.sort(key=lambda x: x["jrrp"], reverse=True)
        
        # 获取奖牌配置
        medals = self._parse_list_string(self.config.get("medals", "🥇, 🥈, 🥉, 🏅, 🏅"))
        if not medals:
            medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
            
        # 构建排行榜
        rank_template = self.config.get("templates", {}).get("rank_template",
            "{medal} {card}: {jrrp} ({fortune})")
            
        ranks = []
        
        for i, user in enumerate(group_data[:10]):  # 只显示前10名
            medal = medals[i] if i < len(medals) else medals[-1] if medals else "🏅"
            rank_line = rank_template.format(
                medal=medal,
                nickname=user["nickname"],
                card=user.get("card", ""),
                jrrp=user["jrrp"],
                fortune=user["fortune"]
            )
            ranks.append(rank_line)
            
        # 构建完整排行榜
        board_template = self.config.get("templates", {}).get("rank_board_template",
            "📊【本群今日人品排行榜】{date}\n━━━━━━━━━━━━━━━\n{ranks}")
            
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
            
        # 获取用户信息以支持{card}变量（有@对象时显示被@用户信息）
        if target_user_id != event.get_sender_id():
            target_user_info = await self.user_info.get_user_info(event, target_user_id)
            display_card = target_user_info["card"] or target_nickname
        else:
            sender_info = await self.user_info.get_user_info(event)
            display_card = sender_info["card"] or target_nickname
            
        # 获取完整的历史记录（用于统计）
        full_user_history = self.storage.get_user_history(target_user_id, 999)  # 获取所有记录用于统计
        
        if not full_user_history:
            yield event.plain_result(f"{display_card} 还没有任何人品记录呢~")
            return
            
        # 获取统计数据（基于全部记录）
        stats = self.storage.get_user_statistics(target_user_id)
        total_count = len(full_user_history)
        
        # 获取配置的显示条数
        display_count = self.config.get("history_days", 10)
        if display_count > total_count:
            display_count = total_count
            
        # 构建历史记录列表（显示最近的记录）
        history_lines = []
        displayed_items = list(full_user_history.items())[:display_count]
        
        for date, data in displayed_items:
            history_lines.append(f"{date}: {data['jrrp']} ({data['fortune']})")
            
        # 构建显示内容
        history_content = "\n".join(history_lines)
        
        # 如果显示数量少于总数量，添加...
        if display_count < total_count:
            history_content += "\n..."
            
        # 使用插件配置的历史记录模板
        history_template = self.config.get("templates", {}).get("history_template",
            "📚 {card} 的人品历史记录\n[显示 {display_count}/{total_count}]\n{history_content}\n\n📊 统计信息:\n平均人品值: {avgjrrp}\n最高人品值: {maxjrrp}\n最低人品值: {minjrrp}")
            
        # 准备变量字典（有@对象时{card}{nickname}为被@用户信息）
        vars_dict = {
            "nickname": target_nickname,
            "card": display_card,
            "display_count": display_count,
            "total_count": total_count,
            "history_content": history_content,
            "avgjrrp": stats['avg'],
            "maxjrrp": stats['max'],
            "minjrrp": stats['min']
        }
        
        result = history_template.format(**vars_dict)
        
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
            # 获取用户信息以支持{target_card}变量
            if is_target_others:
                target_user_info = await self.user_info.get_user_info(event, target_user_id)
                target_card = target_user_info["card"] or target_nickname
                action_desc = f"{target_card} 的"
                cmd_example = f"/jrrpinit @{target_card} --confirm"
            else:
                action_desc = "您的"
                cmd_example = "/jrrpinit --confirm"
            yield event.plain_result(f"⚠️ 警告：此操作将删除 {action_desc}今日人品记录，使其可以重新随机！\n如确认初始化，请使用：{cmd_example}")
            return
            
        today = self.algorithm.get_today_key()
        deleted = self.storage.clear_today_fortune(today, target_user_id)
        
        # 获取用户信息以支持{target_card}变量
        if is_target_others:
            target_user_info = await self.user_info.get_user_info(event, target_user_id)
            target_card = target_user_info["card"] or target_nickname
            action_desc = f"{target_card} 的"
        else:
            action_desc = "您的"
            
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
    
    async def _get_group_ranking_data(self, event: AstrMessageEvent, today_fortunes: dict, current_group_id: str) -> list:
        """
        高效获取群排行榜数据
        使用群成员缓存机制，避免逐个API调用
        """
        group_data = []
        
        # 如果是aiocqhttp平台，使用高效的批量获取
        if event.get_platform_name() == "aiocqhttp":
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            if isinstance(event, AiocqhttpMessageEvent):
                client = event.bot
                
                try:
                    # 一次性获取整个群的成员列表
                    group_members = await client.get_group_member_list(group_id=int(current_group_id))
                    
                    # 建立群成员ID集合，快速查找
                    member_ids = {str(member.get("user_id")) for member in group_members}
                    
                    # 只处理群成员的数据
                    for user_id, data in today_fortunes.items():
                        if user_id in member_ids:
                            # 从群成员列表中找到对应的详细信息
                            member_info = next((m for m in group_members if str(m.get("user_id")) == user_id), {})
                            card = member_info.get("card", "") or member_info.get("nickname") or data.get("nickname", "未知")
                            nickname = member_info.get("nickname") or data.get("nickname", "未知")
                            
                            group_data.append({
                                "user_id": user_id,
                                "nickname": nickname,
                                "card": card,
                                "jrrp": data["jrrp"],
                                "fortune": data.get("fortune", "未知")
                            })
                            
                    logger.debug(f"[jrrprank] 高效模式：群成员{len(group_members)}人，有人品数据{len(group_data)}人")
                    
                except Exception as e:
                    logger.warning(f"[jrrprank] 批量获取群成员失败，回退到逐个检查: {e}")
                    # 回退到原来的逐个检查方式
                    group_data = await self._fallback_group_ranking_data(event, today_fortunes, current_group_id)
        else:
            # 其他平台，使用通用逻辑（可能不够精确）
            group_data = await self._fallback_group_ranking_data(event, today_fortunes, current_group_id)
            
        return group_data
    
    async def _fallback_group_ranking_data(self, event: AstrMessageEvent, today_fortunes: dict, current_group_id: str) -> list:
        """
        降级的群排行榜数据获取方式
        当批量获取失败时使用
        """
        group_data = []
        
        if event.get_platform_name() == "aiocqhttp":
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            if isinstance(event, AiocqhttpMessageEvent):
                client = event.bot
                
                for user_id, data in today_fortunes.items():
                    try:
                        # 逐个检查用户是否为当前群成员
                        member_info = await client.get_group_member_info(
                            user_id=int(user_id), group_id=int(current_group_id)
                        )
                        # 如果API调用成功，说明是群成员
                        card = member_info.get("card", "") or member_info.get("nickname") or data.get("nickname", "未知")
                        nickname = member_info.get("nickname") or data.get("nickname", "未知")
                        group_data.append({
                            "user_id": user_id,
                            "nickname": nickname,
                            "card": card,
                            "jrrp": data["jrrp"],
                            "fortune": data.get("fortune", "未知")
                        })
                    except Exception as e:
                        logger.debug(f"[jrrprank] 用户{user_id}不是当前群成员或API调用失败: {e}")
                        # API失败说明不是群成员，跳过
                        continue
        else:
            # 其他平台，使用通用逻辑（可能不够精确）
            for user_id, data in today_fortunes.items():
                try:
                    user_info = await self.user_info.get_user_info(event, user_id)
                    # 简单检查，可能需要根据具体平台调整
                    if user_info.get("group_id") == current_group_id:
                        nickname = user_info.get("nickname", data.get("nickname", "未知"))
                        group_data.append({
                            "user_id": user_id,
                            "nickname": nickname,
                            "jrrp": data["jrrp"],
                            "fortune": data.get("fortune", "未知")
                        })
                except Exception as e:
                    logger.debug(f"[jrrprank] 获取用户{user_id}信息失败: {e}")
                    continue
                    
        return group_data
