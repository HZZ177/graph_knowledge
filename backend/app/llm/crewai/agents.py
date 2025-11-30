"""预设 Agent 工厂模块（CrewAI）

提供各业务场景下预配置的 CrewAI Agent，接收 LLM 实例，返回可直接使用的 Agent 对象。
"""

from crewai import Agent, LLM


class CrewAiAgents:
    """预设 Agent 工厂类
    
    Usage:
        llm = get_crewai_llm(db)
        agent = CrewAiAgents.create_data_analyst_agent(llm)
    """

    # Agent 元信息（供前端展示、日志等使用）
    AGENT_META = [
        {"name": "数据分析师", "index": 0, "description": "分析原始技术数据，提取系统、接口、数据资源线索"},
        {"name": "流程设计师", "index": 1, "description": "根据业务描述和技术线索，设计业务流程步骤"},
        {"name": "技术架构师", "index": 2, "description": "补充实现细节、数据资源访问关系，生成完整骨架"},
    ]

    @staticmethod
    def create_data_analysis_agent(llm: LLM) -> Agent:
        """创建数据分析师 Agent
        
        负责从日志、抓包数据中提取系统、接口、数据资源线索。
        """
        return Agent(
            role="数据分析师",
            goal="分析原始技术数据，提取系统、接口、数据资源线索",
            backstory="你是一位资深的技术分析专家，擅长从日志和网络抓包中提取有价值的业务技术信息。"
                      "你能够识别并过滤噪声数据，只提取与核心业务流程直接相关的接口和资源。"
                      "你的任何输出都必须是中文，无论是思考，返回解释，内容还是任何其他输出。",
            llm=llm,
            verbose=False,
        )

    @staticmethod
    def create_flow_design_agent(llm: LLM) -> Agent:
        """创建流程设计师 Agent
        
        负责将业务描述和技术线索转化为清晰的流程步骤。
        """
        return Agent(
            role="流程设计师",
            goal="根据业务描述和技术线索，设计业务流程步骤",
            backstory="你是一位资深的业务流程设计师，擅长将业务需求转化为清晰的流程图。"
                      "你设计的步骤名称简洁明确，描述实际业务动作，不会生成虚拟的开始/结束节点。"
                      "你的任何输出都必须是中文，无论是思考，返回解释，内容还是任何其他输出。",
            llm=llm,
            verbose=False,
        )

    @staticmethod
    def create_tech_architect_agent(llm: LLM) -> Agent:
        """创建技术架构师 Agent
        
        负责为业务流程补充技术实现细节和数据资源访问关系。
        """
        return Agent(
            role="技术架构师",
            goal="补充实现细节、数据资源访问关系，生成完整骨架",
            backstory="你是一位资深的技术架构师，擅长为业务流程补充技术实现细节。"
                      "你能够合理推断每个步骤涉及的 API 接口、服务调用和数据资源访问模式。"
                      "你的任何输出都必须是中文，无论是思考，返回解释，内容还是任何其他输出。",
            llm=llm,
            verbose=False,
        )
    
    @classmethod
    def get_meta(cls, index: int) -> dict:
        """获取指定索引的 Agent 元信息"""
        if 0 <= index < len(cls.AGENT_META):
            return cls.AGENT_META[index]
        return {"name": f"Agent-{index}", "index": index, "description": ""}
