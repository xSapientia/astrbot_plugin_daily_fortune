import aiohttp
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from bs4 import BeautifulSoup
import re

# 确保从正确的API导入 AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
# AstrBotConfig 通常在初始化时由核心传入，如果需要类型提示，可以从 astrbot.api 导入，但具体实现可能在 core
try:
    from astrbot.api import AstrBotConfig
except ImportError:
    # 兼容不同版本的导入路径
    from astrbot.config import AstrBotConfig

import astrbot.api.message_components as Comp

# Steam Tag ID 映射 (常用中文标签到ID的映射)
STEAM_TAG_MAP = {
    "角色扮演": 122, "RPG": 122,
    "策略": 9,
    "冒险": 21,
    "独立": 492,
    "动作": 19,
    "模拟": 599,
    "休闲": 597,
    "大型多人在线": 128, "MMO": 128,
    "竞速": 699,
    "体育": 701,
    "免费": 113, "Free to Play": 113,
    "射击": 1774, "FPS": 1663,
    "开放世界": 1695,
    "生存": 1662,
    "恐怖": 1667,
    "科幻": 3942,
    "沙盒": 1718,
    "合作": 1685,
}

# 更新注册信息以匹配文件名（如果需要）
@register(
    "astrbot_plugin_steam_search",
    "MAAI_Claude", # 更新作者
    "一个用于响应LLM调用，查询Steam游戏信息的插件(高级版)",
    "1.1.0" # 更新版本
)
class AdvancedSteamSearchPlugin(Star):
    # ... (__init__ 和 terminate 方法保持不变)
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.session = aiohttp.ClientSession()
        self.config = config
        # 从配置中读取最大结果数，如果未配置则默认为3
        self.max_results = self.config.get("max_results", 3)
        logger.info(f"[Steam Plugin] 插件已加载，最大返回结果数: {self.max_results}")

    async def terminate(self):
        await self.session.close()

    # ... (_map_tags, _advanced_steam_search, _parse_search_results 方法保持不变)
    def _map_tags(self, tag_names: List[str]) -> List[int]:
        """将自然语言标签映射为 Steam Tag ID。"""
        tag_ids = []
        for name in tag_names:
            if name in STEAM_TAG_MAP:
                tag_ids.append(STEAM_TAG_MAP[name])
        return tag_ids

    async def _advanced_steam_search(self, query: str, tag_ids: List[int], sort_by_reviews: bool) -> List[Dict[str, Any]]:
        """
        使用 Steam 商店搜索接口进行高级搜索并解析结果。
        """
        search_url = "https://store.steampowered.com/search/results"
        params = {
            "term": query,
            "l": "schinese",
            "cc": "cn",
            "infinite": 1,
            "supportedlang": "schinese",
        }

        if tag_ids:
            params["tags"] = ",".join(map(str, tag_ids))

        if sort_by_reviews:
            params["sort_by"] = "Reviews_DESC"

        try:
            async with self.session.get(search_url, params=params, timeout=15) as response:
                if response.status != 200:
                    logger.warning(f"Steam Advanced Search API 请求失败，状态码: {response.status}")
                    return []

                data = await response.json()
                results_html = data.get("results_html")
                if not results_html:
                    return []

                return self._parse_search_results(results_html)

        except Exception as e:
            logger.error(f"Steam Advanced Search API 请求异常: {e}")
            return []

    def _parse_search_results(self, html_content: str) -> List[Dict[str, Any]]:
        """使用 BeautifulSoup 解析搜索结果的 HTML 片段。"""
        soup = BeautifulSoup(html_content, "html.parser")
        results = []
        rows = soup.find_all("a", class_="search_result_row")

        count = 0
        for row in rows:
            if count >= self.max_results:
                break

            try:
                app_id = row.get("data-ds-appid")
                link = row.get("href")

                title_span = row.find("span", class_="title")
                title = title_span.text if title_span else "未知名称"

                img_tag = row.find("img")
                cover_url = img_tag['src'] if img_tag else None

                review_summary = row.find("span", class_=re.compile("search_review_summary"))
                review_text = "N/A"
                if review_summary and 'data-tooltip-html' in review_summary.attrs:
                     tooltip = review_summary['data-tooltip-html'].replace("<br>", " (") + ")"
                     review_text = tooltip

                results.append({
                    "app_id": app_id,
                    "title": title,
                    "link": link,
                    "cover_url": cover_url,
                    "review": review_text
                })
                count += 1
            except Exception as e:
                logger.warning(f"解析单个 Steam 搜索结果失败: {e}")
                continue

        return results

    @filter.llm_tool(name="search_steam_games_filtered")
    async def search_steam_games_filtered(self, event: AstrMessageEvent, query: str, genres_or_tags: List[str], require_high_reviews: bool) -> MessageEventResult:
        '''
        根据查询词、类型/标签和好评要求，在Steam上筛选游戏列表。
        用于当用户想查找特定类型且评价好的游戏时，例如“推荐几个好评的RPG游戏”。

        Args:
            query(string): 游戏的搜索关键词，可以是游戏名片段或空字符串（如果只按类型搜索）。
            genres_or_tags(array): 用户要求的游戏类型或标签列表（例如：["RPG", "开放世界"]）。
            require_high_reviews(boolean): 是否要求游戏必须是好评（高评分）的。
        '''
        logger.info(f"[Steam Plugin] LLM 触发高级筛选查询. Query: '{query}', Tags: {genres_or_tags}, High Reviews: {require_high_reviews}")

        # 1. 映射标签
        tag_ids = self._map_tags(genres_or_tags)

        if not query and not tag_ids:
             yield event.plain_result("请提供更具体的搜索条件，例如游戏名称或类型（如RPG、策略等）。")
             return

        # 2. 执行高级搜索
        results = await self._advanced_steam_search(query, tag_ids, sort_by_reviews=require_high_reviews)

        if not results:
            yield event.plain_result(f"抱歉，没有找到符合条件（关键词:'{query}', 类型:{genres_or_tags}）的Steam游戏。")
            return

        # 3. 构建回复消息链
        message_chain = [
            Comp.Plain(f"为您找到前 {len(results)} 个符合条件的Steam游戏：\n\n")
        ]

        for i, game in enumerate(results):
            # 添加游戏信息文本
            text_part = (
                f"#{i+1} 【{game['title']}】\n"
                f"评价: {game['review']}\n"
                f"链接: {game['link']}\n"
            )
            message_chain.append(Comp.Plain(text_part))

            # 添加封面图
            if game['cover_url']:
                # 尝试替换 CDN URL
                cover_url = game['cover_url'].replace("https://cdn.akamai.steamstatic.com", "https://cdn.steamstatic.com.8686c.com")
                message_chain.append(Comp.Image.fromURL(cover_url))

            # !!! 修复此处的 SyntaxError !!!
            message_chain.append(Comp.Plain("\n" + "=" * 20 + "\n")) # 分隔符

        yield event.chain_result(message_chain)
