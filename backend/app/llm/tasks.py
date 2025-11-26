"""预设 Task 工厂模块

提供各业务场景下预配置的 CrewAI Task，接收 Agent 和 prompt，返回可直接使用的 Task 对象。
"""

from crewai import Agent, Task


class CrewAiTasks:
    """预设 Task 工厂类
    
    Usage:
        agent = CrewAiAgents.create_data_analyst_agent(llm)
        task = CrewAiTasks.create_data_analysis_task(agent, prompt)
    """
    
    @staticmethod
    def create_data_analysis_task(agent: Agent, prompt: str) -> Task:
        """创建数据分析任务
        
        分析原始技术数据，提取系统、接口、数据资源线索。
        
        Args:
            agent: 数据分析师 Agent
            prompt: 已格式化的分析提示词
        """
        return Task(
            description=prompt,
            agent=agent,
            expected_output=(
                "请提取并整理以下信息，以JSON格式输出：\n"
                "1. systems: 涉及的系统列表\n"
                "2. apis: API接口列表，包含system/path/method/description\n"
                "3. data_resources: 数据资源列表，包含name/type/system\n"
                "4. call_sequence: 调用顺序描述"
            ),
        )
    
    @staticmethod
    def create_flow_design_task(agent: Agent, prompt: str) -> Task:
        """创建流程设计任务
        
        根据业务描述和技术线索，设计业务流程步骤。
        
        Args:
            agent: 流程设计师 Agent
            prompt: 已格式化的设计提示词
        """
        return Task(
            description=prompt,
            agent=agent,
            expected_output=(
                "请设计流程步骤，以JSON格式输出：\n"
                "steps数组，每个step包含：name/description/step_type/order\n"
                "注意：不要生成开始/结束虚拟节点，只生成实际业务步骤"
            ),
        )
    
    @staticmethod
    def create_tech_enrich_task(agent: Agent, prompt: str) -> Task:
        """创建技术充实任务
        
        为业务流程补充技术实现细节和数据资源访问关系。
        
        Args:
            agent: 技术架构师 Agent
            prompt: 已格式化的充实提示词
        """
        return Task(
            description=prompt,
            agent=agent,
            expected_output=(
                "请输出完整的骨架结构，以JSON格式严格遵循以下结构：\n"
                "1. process: 流程基本信息\n"
                "2. steps: 步骤列表\n"
                "3. edges: 步骤连接关系\n"
                "4. implementations: 技术实现列表\n"
                "5. step_impl_links: 步骤-实现关联\n"
                "6. data_resources: 数据资源列表\n"
                "7. impl_data_links: 实现-数据资源关联"
            ),
        )
