"""
组件3: LLM配置模块

核心职责:
- 统一管理LLM连接配置
- 提供可复用的LLM调用接口
- 支持多模型切换

支持的LLM:
- OpenAI (gpt-4o, gpt-4-turbo, gpt-3.5-turbo)
- 通义千问 (qwen-max, qwen-plus, qwen-turbo)
"""

from __future__ import annotations
import logging
import json
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class LLMConfigurator:
    """LLM配置器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: LLM配置字典 (来自config.yaml的llm部分)
        """
        self.llm_type = config['type'].lower()
        self.api_key = config['api_key']
        self.model = config['model']
        self.base_url = config.get('base_url')
        self.timeout = config.get('timeout', 30)
        self.temperature = config.get('temperature', 0.3)
        self.max_tokens = config.get('max_tokens', 2000)
        self.retry = config.get('retry', 2)
        self.is_tongyi_intl = (
            self.llm_type == "tongyi" and 
            self.base_url and 
            "dashscope-intl" in self.base_url
        )
        
        # 初始化客户端
        self.client = self._init_client()
        
        logger.info(f"✅ LLM初始化成功: {self.llm_type} / {self.model}")
    
    def _init_client(self):
        """初始化LLM客户端"""
        if self.llm_type == "openai":
            return self._init_openai()
        elif self.llm_type == "tongyi":
            if self.is_tongyi_intl:
                return self._init_tongyi_intl()
            return self._init_tongyi()
        else:
            raise ValueError(f"不支持的LLM类型: {self.llm_type}")
    
    def _init_openai(self):
        """初始化OpenAI客户端"""
        try:
            from openai import OpenAI
            
            kwargs = {
                "api_key": self.api_key,
                "timeout": self.timeout
            }
            
            if self.base_url:
                kwargs["base_url"] = self.base_url
            
            client = OpenAI(**kwargs)
            
            # 测试连接
            logger.debug("测试OpenAI连接...")
            client.models.list()
            
            return client
            
        except ImportError:
            raise ImportError("请安装OpenAI SDK: pip install openai>=1.0.0")
        except Exception as e:
            raise RuntimeError(f"OpenAI初始化失败: {e}")
    
    def _init_tongyi(self):
        """初始化通义千问客户端"""
        try:
            import dashscope
            from dashscope import Generation
            
            # 设置API密钥
            dashscope.api_key = self.api_key
            
            # 测试连接
            logger.debug("测试通义千问连接...")
            response = Generation.call(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                result_format="message"
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"通义API测试失败: {response.message}")
            
            # 返回Generation类(而非实例)
            return Generation
            
        except ImportError:
            raise ImportError("请安装通义SDK: pip install dashscope")
        except Exception as e:
            raise RuntimeError(f"通义千问初始化失败: {e}")
    
    def _init_tongyi_intl(self):
        """初始化通义千问国际版客户端（OpenAI兼容模式）"""
        try:
            from openai import OpenAI
            
            # ⭐ 使用 OpenAI SDK 连接通义国际版
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
            
            # 测试连接
            logger.debug("测试通义千问国际版连接...")
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10
            )
            
            logger.info("✅ 通义千问国际版连接成功")
            return client
            
        except ImportError:
            raise ImportError("请安装OpenAI SDK: pip install openai>=1.0.0")
        except Exception as e:
            raise RuntimeError(f"通义千问国际版初始化失败: {e}")

    # ===========================
    # 统一调用接口
    # ===========================
    
    def call_json(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        调用LLM并返回JSON格式结果
        
        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词(可选)
            temperature: 温度参数(可选,覆盖配置)
            max_tokens: 最大token数(可选,覆盖配置)
        
        Returns:
            解析后的JSON字典
        
        Raises:
            ValueError: JSON解析失败
            RuntimeError: API调用失败
        """
        # 使用配置的默认值
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # 根据LLM类型调用不同方法
        if self.llm_type == "openai" or self.is_tongyi_intl:
            response = self._call_openai_json(
                user_prompt, system_prompt, temperature, max_tokens
            )
        elif self.llm_type == "tongyi":
            response = self._call_tongyi_json(
                user_prompt, system_prompt, temperature, max_tokens
            )
        else:
            raise ValueError(f"不支持的LLM类型: {self.llm_type}")
        
        return response
    
    def call_text(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        调用LLM并返回纯文本结果
        
        Args:
            (同call_json)
        
        Returns:
            文本响应
        """
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        if self.llm_type == "openai" or self.is_tongyi_intl:
            response = self._call_openai_text(
                user_prompt, system_prompt, temperature, max_tokens
            )
        elif self.llm_type == "tongyi":
            response = self._call_tongyi_text(
                user_prompt, system_prompt, temperature, max_tokens
            )
        else:
            raise ValueError(f"不支持的LLM类型: {self.llm_type}")
        
        return response
    
    # ===========================
    # OpenAI实现(or 通义国际版)
    # ===========================
    
    def _call_openai_json(
        self,
        user_prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """OpenAI JSON模式调用"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        
        for attempt in range(self.retry + 1):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
                if not self.is_tongyi_intl:
                    kwargs["response_format"] = {"type": "json_object"}
                else:
                    # 通义国际版：在 system prompt 中要求 JSON
                    if system_prompt:
                        messages[0]["content"] += "\n\n⚠️ 请严格返回有效的JSON格式，不要包含任何其他文本或markdown标记。"
                    else:
                        messages.insert(0, {
                            "role": "system",
                            "content": "请严格返回有效的JSON格式，不要包含任何其他文本或markdown标记。"
                        })

                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                
                # 清理可能的 Markdown 代码块
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                return json.loads(content)
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 (尝试{attempt+1}/{self.retry+1}): {e}")
                if attempt == self.retry:
                    raise ValueError(f"LLM返回非有效JSON: {content[:200]}")
            
            except Exception as e:
                logger.error(f"OpenAI调用失败 (尝试{attempt+1}/{self.retry+1}): {e}")
                if attempt == self.retry:
                    raise RuntimeError(f"OpenAI API调用失败: {e}")
    
    def _call_openai_text(
        self,
        user_prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """OpenAI文本模式调用"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        
        for attempt in range(self.retry + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                logger.error(f"OpenAI调用失败 (尝试{attempt+1}/{self.retry+1}): {e}")
                if attempt == self.retry:
                    raise RuntimeError(f"OpenAI API调用失败: {e}")
    
    # ===========================
    # 通义千问实现
    # ===========================
    
    def _call_tongyi_json(
        self,
        user_prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """通义千问JSON模式调用"""
        # ⚠️ 通义不支持原生JSON模式,需在prompt中明确要求
        enhanced_system = (system_prompt or "") + "\n\n请严格按照JSON格式返回结果,不要包含任何其他文本。"
        
        messages = []
        if enhanced_system:
            messages.append({"role": "system", "content": enhanced_system})
        messages.append({"role": "user", "content": user_prompt})
        
        for attempt in range(self.retry + 1):
            try:
                response = self.client.call(
                    model=self.model,
                    messages=messages,
                    result_format="message",  # 通义固定格式
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if response.status_code != 200:
                    raise RuntimeError(f"通义API错误: {response.message}")
                
                content = response.output.choices[0].message.content
                
                # 清理可能的Markdown代码块标记
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                return json.loads(content)
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 (尝试{attempt+1}/{self.retry+1}): {e}")
                logger.debug(f"原始内容: {content[:500]}")
                if attempt == self.retry:
                    raise ValueError(f"通义返回非有效JSON: {content[:200]}")
            
            except Exception as e:
                logger.error(f"通义调用失败 (尝试{attempt+1}/{self.retry+1}): {e}")
                if attempt == self.retry:
                    raise RuntimeError(f"通义API调用失败: {e}")
    
    def _call_tongyi_text(
        self,
        user_prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """通义千问文本模式调用"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        
        for attempt in range(self.retry + 1):
            try:
                response = self.client.call(
                    model=self.model,
                    messages=messages,
                    result_format="message",
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if response.status_code != 200:
                    raise RuntimeError(f"通义API错误: {response.message}")
                
                return response.output.choices[0].message.content
                
            except Exception as e:
                logger.error(f"通义调用失败 (尝试{attempt+1}/{self.retry+1}): {e}")
                if attempt == self.retry:
                    raise RuntimeError(f"通义API调用失败: {e}")