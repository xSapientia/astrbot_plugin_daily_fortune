"""
LLM调用和Provider管理模块
"""

import asyncio
import re
from typing import Optional, Dict, Tuple
from astrbot.api.star import Context
from astrbot.api import logger


class LLMManager:
    """LLM管理器"""
    
    def __init__(self, context: Context, config: dict):
        """
        初始化LLM管理器
        
        Args:
            context: AstrBot上下文
            config: 插件配置
        """
        self.context = context
        self.config = config
        self.provider = None
        self.persona_name = ""
        
        # 初始化LLM提供商
        self._init_provider()
            
    def _init_provider(self):
        """初始化LLM提供商"""
        provider_id = self.config.get("llm_provider_id", "")
        
        if provider_id:
            try:
                # 查找指定的provider
                self.provider = self.context.get_provider_by_id(provider_id)
                if self.provider:
                    logger.info(f"[daily_fortune] 找到provider: {provider_id}")
                    asyncio.create_task(self._test_provider_connection())
                else:
                    logger.warning(f"[daily_fortune] 未找到provider_id: {provider_id}")
                    self.provider = None
            except Exception as e:
                logger.error(f"[daily_fortune] 获取provider失败: {e}")
                self.provider = None
        else:
            # 使用第三方接口配置
            api_config = self.config.get("llm_api", {})
            if api_config.get("llm_api_key") and api_config.get("llm_url"):
                logger.info(f"[daily_fortune] 配置了第三方接口: {api_config['llm_url']}")
                # 创建自定义provider
                asyncio.create_task(self._test_third_party_api(api_config))
                self.provider = None
            else:
                self.provider = None
                
        # 获取人格配置
        self.persona_name = self.config.get("persona_name", "")
        if self.persona_name:
            personas = self.context.provider_manager.personas
            found = False
            for p in personas:
                if p.get('name') == self.persona_name:
                    prompt = p.get('prompt', '')
                    logger.info(f"[daily_fortune] 使用人格: {self.persona_name}, prompt前20字符: {prompt[:20]}...")
                    found = True
                    break
            if not found:
                logger.warning(f"[daily_fortune] 未找到人格: {self.persona_name}")
        else:
            # 输出默认人格信息
            default_persona = self.context.provider_manager.selected_default_persona
            if default_persona:
                persona_name = default_persona.get("name", "未知")
                # 查找完整人格信息
                personas = self.context.provider_manager.personas
                for p in personas:
                    if p.get('name') == persona_name:
                        prompt = p.get('prompt', '')
                        logger.info(f"[daily_fortune] 使用默认人格: {persona_name}, prompt前20字符: {prompt[:20]}...")
                        break
                        
    async def _test_provider_connection(self):
        """测试provider连接"""
        try:
            if self.provider:
                # 直接使用配置中的provider_id作为名称
                provider_name = self.config.get("llm_provider_id", "Unknown")
                
                logger.debug(f"Sending 'Ping' to provider: {provider_name}")
                response = await asyncio.wait_for(
                    self.provider.text_chat(prompt="REPLY `PONG` ONLY"), timeout=45.0
                )
                logger.debug(f"Received response from {provider_name}: {response}")
                
                if response and response.completion_text:
                    logger.info(f"[daily_fortune] Provider连接测试成功: {provider_name}")
                else:
                    logger.warning(f"[daily_fortune] Provider连接测试失败：无响应 - {provider_name}")
        except Exception as e:
            provider_name = self.config.get("llm_provider_id", "Unknown")
            logger.error(f"[daily_fortune] Provider连接测试失败: {provider_name} - {e}")
            
    async def _test_third_party_api(self, api_config):
        """测试第三方API连接"""
        try:
            import aiohttp
            
            # 智能处理URL
            url = api_config['llm_url'].rstrip('/')
            if not url.endswith('/chat/completions'):
                if url.endswith('/v1'):
                    url += '/chat/completions'
                else:
                    url += '/v1/chat/completions'
                    
            headers = {
                'Authorization': f"Bearer {api_config['llm_api_key']}",
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': api_config.get('model', 'gpt-3.5-turbo'),
                'messages': [{'role': 'user', 'content': 'REPLY `PONG` ONLY'}],
                'max_tokens': 10
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info(f"[daily_fortune] 第三方API连接测试成功: {api_config['llm_url']}")
                    else:
                        text = await resp.text()
                        logger.warning(f"[daily_fortune] 第三方API连接测试失败: {resp.status} - {text}")
        except Exception as e:
            logger.error(f"[daily_fortune] 第三方API连接测试失败: {e}")
            
    async def generate_fortune_content(self, vars_dict: Dict[str, str]) -> Tuple[str, str]:
        """
        使用LLM生成运势内容（一次调用生成过程和建议）
        独立调用，不触发AstrBot本身的人格功能
        
        Args:
            vars_dict: 包含所有模板变量的字典
            
        Returns:
            (过程描述, 建议) 元组
        """
        # 检查是否启用LLM（通过配置）
        if not self.config.get("enable_llm_calls", True):
            logger.debug("[daily_fortune] LLM调用被配置禁用")
            return "水晶球中浮现出神秘的光芒...", "保持乐观的心态，好运自然来。"
            
        try:
            # 获取Provider - 使用优先级:插件配置的provider_id>第三方api>默认provider
            provider = None
            provider_id = self.config.get("llm_provider_id", "").strip()
            
            # 1. 优先使用插件配置的provider_id
            if provider_id:
                provider = self.context.get_provider_by_id(provider_id)
                if provider:
                    logger.debug(f"[daily_fortune] 使用指定provider: {provider_id}")
                else:
                    logger.warning(f"[daily_fortune] 指定的provider_id不存在: {provider_id}")
            
            # 2. 如果没有指定provider或指定的不存在，检查第三方API配置
            if not provider:
                api_config = self.config.get("llm_api", {})
                if api_config.get("llm_api_key") and api_config.get("llm_url"):
                    logger.debug("[daily_fortune] 配置了第三方API，但暂不支持直接调用")
                    # TODO: 这里可以实现第三方API的直接调用
                    
            # 3. 最后使用默认provider
            if not provider:
                provider = self.context.get_using_provider()
                if provider:
                    logger.debug("[daily_fortune] 使用默认provider")
                
            if not provider:
                logger.warning("[daily_fortune] 没有可用的LLM提供商")
                return "水晶球中浮现出神秘的光芒...", "保持乐观的心态，好运自然来。"
                
            # 获取人格prompt - 使用优先级:插件配置的persona_name>默认persona
            persona_prompt = ""
            persona_name = self.config.get("persona_name", "").strip()
            
            if persona_name:
                # 使用指定的人格
                personas = self.context.provider_manager.personas
                for p in personas:
                    if p.get('name') == persona_name:
                        persona_prompt = p.get('prompt', '')
                        logger.debug(f"[daily_fortune] 使用指定人格: {persona_name}")
                        break
                else:
                    logger.warning(f"[daily_fortune] 未找到指定人格: {persona_name}")
            
            if not persona_prompt:
                # 使用默认人格
                default_persona = self.context.provider_manager.selected_default_persona
                if default_persona and default_persona.get("name"):
                    default_persona_name = default_persona["name"]
                    personas = self.context.provider_manager.personas
                    for p in personas:
                        if p.get('name') == default_persona_name:
                            persona_prompt = p.get('prompt', '')
                            logger.debug(f"[daily_fortune] 使用默认人格: {default_persona_name}")
                            break
                            
            # 获取首次查询结果模板
            result_template = self.config.get("templates", {}).get("resault_template",
                "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}")
            
            # 获取过程模拟prompt和结果prompt
            process_prompt = self.config.get("prompts", {}).get("process_prompt",
                "模拟你使用水晶球缓慢显现的过程，50字以内")
            advice_prompt = self.config.get("prompts", {}).get("advice_prompt",
                "人品值分段为{ranges_jrrp}，对应运势是{ranges_fortune}\n{user_id}今日人品值{jrrp}\n直接给出你的评语和建议，50字以内")
                
            # 格式化提示词
            formatted_process_prompt = process_prompt.format(**vars_dict)
            formatted_advice_prompt = advice_prompt.format(**vars_dict)
            
            # 使用{process_prompt}和{advice_prompt}替换模板中的{process}和{advice}
            template_with_prompts = result_template.replace("{process}", "{process_prompt}").replace("{advice}", "{advice_prompt}")
            
            # 准备模板变量
            template_vars = vars_dict.copy()
            template_vars['process_prompt'] = formatted_process_prompt
            template_vars['advice_prompt'] = formatted_advice_prompt
            
            # 格式化模板
            formatted_template = template_with_prompts.format(**template_vars)
            
            # 构建完整的prompt - 人格prompt和替换后的模板prompt
            full_prompt = ""
            if persona_prompt:
                full_prompt += f"{persona_prompt}\n\n"
            
            full_prompt += f"""用户昵称是'{vars_dict.get('nickname', '用户')}'。

请按照以下模板为该用户生成今日运势内容，请直接按模板格式输出，不要包含额外的标记或说明：

{formatted_template}

注意：
- 请将🔮后面的内容替换为实际的占卜过程描述
- 请将💬建议后面的内容替换为实际的建议内容
- 保持模板的格式和表情符号不变"""
            
            # 使用人格prompt和替换后的模板prompt请求llm
            response = await provider.text_chat(
                prompt=full_prompt,
                session_id=None,  # 不使用会话管理
                contexts=[],      # 不使用历史上下文
                image_urls=[],    # 不传递图片
                func_tool=None,   # 不使用函数工具
                system_prompt=""  # 不使用额外的system_prompt，人格已经在prompt中
            )
                    
            if response and response.completion_text:
                content = response.completion_text.strip()
                logger.debug(f"[daily_fortune] LLM原始回复: {content}")
                
                # 从回复中提取{process}和{advice}
                # 尝试按行分割并识别🔮和💬行
                lines = content.split('\n')
                process = "水晶球中浮现出神秘的光芒..."
                advice = "保持乐观的心态，好运自然来。"
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('🔮'):
                        # 提取🔮后面的内容作为过程
                        process = line[2:].strip()
                    elif line.startswith('💬'):
                        # 提取💬后面的内容，去掉"建议："等前缀
                        advice_content = line[2:].strip()
                        if advice_content.startswith('建议：'):
                            advice = advice_content[3:].strip()
                        else:
                            advice = advice_content
                
                # 清理内容并限制长度
                process = re.sub(r'\s+', ' ', process).strip()
                advice = re.sub(r'\s+', ' ', advice).strip()
                
                process = process[:100] if len(process) > 100 else process
                advice = advice[:100] if len(advice) > 100 else advice
                
                logger.debug(f"[daily_fortune] 提取结果 - 过程: {process[:20]}... 建议: {advice[:20]}...")
                return process, advice
            else:
                logger.warning("[daily_fortune] LLM返回空响应")
                return "水晶球中浮现出神秘的光芒...", "保持乐观的心态，好运自然来。"
                
        except Exception as e:
            logger.error(f"[daily_fortune] LLM生成失败: {e}")
            return "水晶球中浮现出神秘的光芒...", "保持乐观的心态，好运自然来。"
