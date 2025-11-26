"""自定义网关 LLM 实现

支持 NewAPI 等兼容 OpenAI API 格式的自建网关。
实现 CrewAI BaseLLM 接口，支持流式输出。
"""

import json
from typing import Any, Dict, Generator, List, Optional, Union

import requests
from crewai import BaseLLM

from backend.app.core.logger import logger


class CustomGatewayLLM(BaseLLM):
    """自定义网关 LLM
    
    支持任何兼容 OpenAI Chat Completions API 的网关（如 NewAPI）。
    
    Features:
        - 完整的 OpenAI API 兼容
        - 流式 SSE 响应支持
        - Stop words 支持
        - 可配置超时和重试
    
    Usage:
        llm = CustomGatewayLLM(
            model="gpt-4",
            api_key="sk-xxx",
            endpoint="https://your-newapi.com/v1/chat/completions",
            temperature=0.7,
        )
    """
    
    def __init__(
        self,
        model: str,
        api_key: str,
        endpoint: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 120,
    ):
        """初始化自定义网关 LLM
        
        Args:
            model: 模型名称，如 "gpt-4", "claude-3-opus" 等
            api_key: API密钥（Bearer Token）
            endpoint: 网关端点URL，如 "https://api.example.com/v1/chat/completions"
            temperature: 温度参数，默认 None（使用模型默认值）
            max_tokens: 最大输出token数，默认 None
            timeout: 请求超时时间（秒），默认 120
        """
        # 必须调用父类构造器
        super().__init__(model=model, temperature=temperature)
        
        self.api_key = api_key
        self.endpoint = endpoint
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        logger.info(f"[CustomGatewayLLM] 初始化: model={model}, endpoint={endpoint}")
    
    def call(
        self,
        messages: Union[str, List[Dict[str, str]]],
        tools: Optional[List[dict]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
        **kwargs,  # 接收 CrewAI 传入的额外参数（如 from_task）
    ) -> Union[str, Any]:
        """非流式调用 LLM
        
        注意：CrewAI 可能传入额外参数，通过 kwargs 接收。
        
        Args:
            messages: 消息列表或单个字符串
            tools: 工具定义列表（function calling）
            callbacks: 回调函数列表（当前未使用）
            available_functions: 可用函数字典（用于执行 function call）
            
        Returns:
            LLM 响应文本
        """
        # 将字符串转换为消息格式
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        # 构建请求体
        payload = self._build_payload(messages, tools, stream=False)
        
        logger.debug(f"[CustomGatewayLLM] 请求: model={self.model}, messages_count={len(messages)}")
        
        try:
            response = requests.post(
                self.endpoint,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            result = response.json()
            message = result["choices"][0]["message"]
            
            # 处理 function calling
            if "tool_calls" in message and message["tool_calls"] and available_functions:
                return self._handle_function_calls(
                    message["tool_calls"],
                    messages,
                    tools,
                    available_functions,
                )
            
            content = message.get("content", "")
            
            # 手动处理 stop words（如果需要）
            if self.stop:
                content = self._apply_stop_words(content)
            
            logger.debug(f"[CustomGatewayLLM] 响应长度: {len(content)}")
            return content
            
        except requests.Timeout:
            logger.error(f"[CustomGatewayLLM] 请求超时: timeout={self.timeout}s")
            raise TimeoutError(f"LLM request timed out after {self.timeout}s")
        except requests.RequestException as e:
            logger.error(f"[CustomGatewayLLM] 请求失败: {e}")
            raise RuntimeError(f"LLM request failed: {str(e)}")
        except (KeyError, IndexError) as e:
            logger.error(f"[CustomGatewayLLM] 响应解析失败: {e}")
            raise ValueError(f"Invalid response format: {str(e)}")
    
    def stream(
        self,
        messages: Union[str, List[Dict[str, str]]],
        tools: Optional[List[dict]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
        **kwargs,  # 接收 CrewAI 传入的额外参数
    ) -> Generator[str, None, None]:
        """流式调用 LLM
        
        使用 SSE (Server-Sent Events) 协议流式获取响应.
        
        Args:
            messages: 消息列表或单个字符串
            tools: 工具定义列表
            callbacks: 回调函数列表
            available_functions: 可用函数字典
            
        Yields:
            每个 token/chunk 的文本内容
        """
        # 将字符串转换为消息格式
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        # 构建请求体（stream=True）
        payload = self._build_payload(messages, tools, stream=True)
        
        logger.debug(f"[CustomGatewayLLM] 流式请求: model={self.model}, messages_count={len(messages)}")
        
        try:
            response = requests.post(
                self.endpoint,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            
            # 解析 SSE 流
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                
                # SSE 格式: "data: {...}"
                if line.startswith("data: "):
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    
                    # 流结束标志
                    if data_str.strip() == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        # 提取 delta 内容
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        
                        if content:
                            yield content
                            
                    except json.JSONDecodeError:
                        # 忽略无法解析的行
                        continue
            
            logger.debug("[CustomGatewayLLM] 流式响应完成")
            
        except requests.Timeout:
            logger.error(f"[CustomGatewayLLM] 流式请求超时: timeout={self.timeout}s")
            raise TimeoutError(f"LLM stream request timed out after {self.timeout}s")
        except requests.RequestException as e:
            logger.error(f"[CustomGatewayLLM] 流式请求失败: {e}")
            raise RuntimeError(f"LLM stream request failed: {str(e)}")
    
    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[dict]],
        stream: bool,
    ) -> dict:
        """构建 API 请求体"""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        
        # 添加 stop words
        if self.stop:
            payload["stop"] = self.stop
        
        # 添加 tools（function calling）
        if tools and self.supports_function_calling():
            payload["tools"] = tools
        
        return payload
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def _apply_stop_words(self, content: str) -> str:
        """应用 stop words 截断"""
        if not self.stop:
            return content
        
        for stop_word in self.stop:
            if stop_word in content:
                content = content.split(stop_word)[0]
                break
        
        return content
    
    def _handle_function_calls(
        self,
        tool_calls: List[dict],
        messages: List[Dict[str, str]],
        tools: Optional[List[dict]],
        available_functions: Dict[str, Any],
    ) -> str:
        """处理 function calling
        
        执行工具调用并将结果添加到上下文中，然后再次调用 LLM。
        """
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            
            if function_name not in available_functions:
                logger.warning(f"[CustomGatewayLLM] 未知函数: {function_name}")
                continue
            
            try:
                # 解析并执行函数
                function_args = json.loads(tool_call["function"]["arguments"])
                function_result = available_functions[function_name](**function_args)
                
                logger.debug(f"[CustomGatewayLLM] 执行函数: {function_name}, 结果长度: {len(str(function_result))}")
                
                # 添加 assistant 消息（包含 tool_calls）
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call],
                })
                
                # 添加 tool 响应消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": function_name,
                    "content": str(function_result),
                })
                
            except Exception as e:
                logger.error(f"[CustomGatewayLLM] 函数执行失败: {function_name}, error={e}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": function_name,
                    "content": f"Error: {str(e)}",
                })
        
        # 再次调用 LLM 获取最终响应
        return self.call(messages, tools, None, available_functions)
    
    def supports_function_calling(self) -> bool:
        """是否支持 function calling
        
        NewAPI 通常支持，但可根据实际情况调整。
        """
        return True
    
    def supports_stop_words(self) -> bool:
        """是否支持 stop words
        
        OpenAI 兼容 API 通常支持。
        """
        return True
    
    def get_context_window_size(self) -> int:
        """返回上下文窗口大小
        
        根据实际使用的模型调整。默认返回 128k（适用于大多数现代模型）。
        """
        return 128000
