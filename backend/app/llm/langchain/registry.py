"""Agent 注册表

管理多类型 Agent 的缓存、懒加载、配置变更检测。
核心功能：
- 单例模式：全局唯一注册表实例
- 懒加载：首次请求时才编译 Agent
- 配置变更检测：LLM 配置变更时自动重建 Agent
- 预热支持：可选在启动时预编译关键 Agent
"""

import hashlib
from threading import Lock
from typing import Dict, Optional, TYPE_CHECKING

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ToolCallLimitMiddleware,
    ModelCallLimitMiddleware,
)

from backend.app.llm.langchain.configs import (
    AgentConfig,
    AGENT_CONFIGS,
    get_agent_config,
    get_knowledge_qa_system_prompt,
)
from backend.app.llm.factory import get_langchain_llm
from backend.app.services.ai_model_service import AIModelService
from backend.app.core.logger import logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from langgraph.graph.state import CompiledGraph


class AgentRegistry:
    """Agent 注册表 - 管理多类型 Agent 的 LLM 和工具缓存
    
    线程安全的单例模式，支持：
    - 按 agent_type 缓存 LLM 实例和工具列表（这些是初始化开销较大的部分）
    - LLM 配置变更时自动重建
    - 可选预热
    
    Usage:
        registry = AgentRegistry.get_instance()
        agent = registry.get_agent("knowledge_qa", db)
    """
    
    _instance: Optional["AgentRegistry"] = None
    _lock: Lock = Lock()
    
    def __init__(self):
        """Private constructor. Use get_instance() instead."""
        # 缓存 LLM 实例和工具列表（这些是初始化开销较大的部分）
        self._llm_cache: Dict[str, any] = {}  # LLM 实例缓存
        self._tools_cache: Dict[str, list] = {}  # 工具列表缓存
        self._config_hashes: Dict[str, str] = {}
        self._cache_lock = Lock()
    
    @classmethod
    def get_instance(cls) -> "AgentRegistry":
        """获取全局单例实例（双重检查锁定）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger.info("[AgentRegistry] 单例实例已创建")
        return cls._instance
    
    def get_agent(self, agent_type: str, db: "Session", checkpointer=None) -> "CompiledGraph":
        """获取指定类型的 Agent
        
        缓存 LLM 实例和工具列表，每次请求重新编译 Agent 并绑定 checkpointer。
        
        Args:
            agent_type: Agent 类型标识
            db: 数据库会话（用于读取 LLM 配置）
            checkpointer: 检查点存储（用于持久化对话历史）
            
        Returns:
            编译后的 CompiledGraph 实例
            
        Raises:
            ValueError: 未知的 agent_type
        """
        # 获取 Agent 配置
        config = get_agent_config(agent_type)
        
        # 计算当前 LLM 配置的 hash
        current_hash = self._compute_llm_config_hash(db)
        
        # 检查是否需要重新创建 LLM 和 Tools
        need_refresh = (
            agent_type not in self._llm_cache or
            self._config_hashes.get(agent_type) != current_hash
        )
        
        if need_refresh:
            with self._cache_lock:
                # Double-check
                if (agent_type not in self._llm_cache or 
                    self._config_hashes.get(agent_type) != current_hash):
                    
                    logger.info(f"[AgentRegistry] {'创建' if agent_type not in self._llm_cache else '刷新'} LLM/Tools 缓存: {agent_type}")
                    
                    # 缓存 LLM 和 Tools
                    self._llm_cache[agent_type] = get_langchain_llm(db)
                    self._tools_cache[agent_type] = config.tools_factory()
                    self._config_hashes[agent_type] = current_hash
                    
                    logger.info(f"[AgentRegistry] LLM/Tools 缓存已就绪: {agent_type}, tools={len(self._tools_cache[agent_type])}, hash={current_hash[:16]}...")
        
        # 每次请求都重新编译 Agent 并绑定 checkpointer
        return self._create_agent(config, agent_type, checkpointer)
    
    def _create_agent(self, config: AgentConfig, agent_type: str, checkpointer=None) -> "CompiledGraph":
        """创建 Agent（使用缓存的 LLM 和 Tools，绑定 checkpointer）
        
        Args:
            config: Agent 配置
            agent_type: Agent 类型标识
            checkpointer: 检查点存储
            
        Returns:
            编译后的 CompiledGraph
        """
        # 使用缓存的 LLM 和 Tools
        llm = self._llm_cache.get(agent_type)
        tools = self._tools_cache.get(agent_type, [])
        
        # 配置中间件
        middleware: list[AgentMiddleware] = [
            ModelCallLimitMiddleware(
                run_limit=config.model_call_limit,
                exit_behavior="end"
            ),
            ToolCallLimitMiddleware(
                run_limit=config.tool_call_limit,
                exit_behavior="continue"
            ),
        ]
        
        # 获取 System Prompt（knowledge_qa 使用动态生成的 prompt，包含工作区信息）
        if agent_type == "knowledge_qa":
            system_prompt = get_knowledge_qa_system_prompt()
        else:
            system_prompt = config.system_prompt
        
        # 创建 Agent（绑定 checkpointer 以支持持久化）
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            middleware=middleware,
            checkpointer=checkpointer,
        )
        
        return agent
    
    def _compute_llm_config_hash(self, db: "Session") -> str:
        """计算当前 LLM 配置的 hash 值
        
        用于检测 LLM 配置是否变更，决定是否需要重建 Agent。
        """
        try:
            active_model = AIModelService.get_active_model(db)
            if not active_model:
                return "no_active_model"
            
            # 组合关键字段生成 hash
            hash_input = f"{active_model.id}:{active_model.model_name}:{active_model.provider_type}:{active_model.temperature}"
            return hashlib.md5(hash_input.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"[AgentRegistry] 计算配置 hash 失败: {e}")
            return "error"
    
    def warmup(self, agent_type: str, db: "Session") -> None:
        """预热指定类型的 Agent
        
        用于在应用启动时预编译关键 Agent，减少首次请求延迟。
        
        Args:
            agent_type: Agent 类型标识
            db: 数据库会话
        """
        logger.info(f"[AgentRegistry] 预热 Agent: {agent_type}")
        self.get_agent(agent_type, db)
        logger.info(f"[AgentRegistry] Agent {agent_type} 预热完成")
    
    def warmup_all(self, db: "Session") -> None:
        """预热所有已注册的 Agent"""
        for agent_type in AGENT_CONFIGS.keys():
            self.warmup(agent_type, db)
    
    def invalidate(self, agent_type: Optional[str] = None) -> None:
        """手动失效缓存
        
        用于 LLM 配置变更后强制重建 Agent。
        
        Args:
            agent_type: 指定类型，为 None 时清除所有缓存
        """
        with self._cache_lock:
            if agent_type:
                self._llm_cache.pop(agent_type, None)
                self._tools_cache.pop(agent_type, None)
                self._config_hashes.pop(agent_type, None)
                logger.info(f"[AgentRegistry] 已失效缓存: {agent_type}")
            else:
                self._llm_cache.clear()
                self._tools_cache.clear()
                self._config_hashes.clear()
                logger.info("[AgentRegistry] 已清除所有缓存")
    
    def get_cached_agent_types(self) -> list:
        """获取当前已缓存的 Agent 类型列表（调试用）"""
        return list(self._llm_cache.keys())
    
    def get_stats(self) -> dict:
        """获取注册表统计信息（调试用）"""
        return {
            "cached_llm": list(self._llm_cache.keys()),
            "cached_tools": {k: len(v) for k, v in self._tools_cache.items()},
            "total_registered": len(AGENT_CONFIGS),
            "config_hashes": {k: v[:16] + "..." for k, v in self._config_hashes.items()},
        }


def get_agent_run_config(thread_id: str) -> dict:
    """获取 Agent 运行时配置
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        Agent 运行配置字典
    """
    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 150,
    }
