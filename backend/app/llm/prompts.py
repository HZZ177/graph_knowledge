DATA_ANALYSIS_PROMPT = """
你是一位资深的技术分析专家，擅长从日志和网络抓包中提取有价值的业务技术信息。

**重要：过滤噪声数据**
用户提供的原始数据中可能包含大量无关信息，你必须严格过滤以下噪声：

【必须忽略的请求类型】
- 静态资源：.js, .mjs, .jsx, .ts, .css, .less, .sass, .scss, .map
- 图片文件：.jpg, .jpeg, .png, .gif, .svg, .ico, .webp, .bmp
- 字体文件：.woff, .woff2, .ttf, .eot, .otf
- 媒体文件：.mp4, .mp3, .wav, .webm, .ogg
- 文档文件：.pdf, .doc, .xls

【必须忽略的系统请求】
- 前端框架：webpack, vite, next, nuxt, chunk, bundle, manifest
- 监控埋点：track, log, beacon, collect, analytics, metrics, trace, sentry, bugsnag
- 广告相关：ad, ads, advertisement, banner, pixel
- 第三方SDK：google, facebook, baidu, tencent (除非是业务相关)
- 健康检查：health, ping, alive, ready, status

【只提取以下有价值的信息】
- 实际的业务API接口（如 /api/user/xxx, /api/order/xxx）
- 真实的后端服务调用
- 数据库操作相关的日志
- 消息队列相关的日志
- 缓存操作相关的日志

请分析以下原始技术数据，提取与业务"{business_name}"直接相关的关键信息：

【业务描述】
{business_description}

【结构化日志】
{structured_logs}

【抓包接口】
{api_captures}

【已知系统】
{known_systems}

【已知数据资源】
{known_data_resources}

请提取并整理以下信息，以JSON格式输出：
{{
    "systems": ["系统1", "系统2"],
    "apis": [
        {{"system": "系统名", "path": "/api/xxx", "method": "POST", "description": "描述"}}
    ],
    "data_resources": [
        {{"name": "资源名", "type": "table/cache/mq", "system": "所属系统"}}
    ],
    "call_sequence": ["步骤1的描述", "步骤2的描述"]
}}

注意：
1. 只提取与核心业务流程直接相关的接口和资源，过滤所有噪声
2. 如果原始数据混杂了多个不相关的业务，只提取与"{business_name}"相关的部分
3. 如果某项信息无法从数据中提取，请基于业务描述进行合理推断
"""


FLOW_DESIGN_PROMPT = """
你是一位资深的业务流程设计师，擅长将业务需求转化为清晰的流程图。

请根据以下信息设计业务流程步骤：

【业务名称】
{business_name}

【业务描述】
{business_description}

【渠道】
{channel}

【技术分析结果】
{analysis_result}

请设计流程步骤，以JSON格式输出：
{{
    "steps": [
        {{
            "name": "步骤名称（简短，描述实际业务动作）",
            "description": "步骤详细描述",
            "step_type": "process/decision",
            "order": 1,
            "system_hint": "可能涉及的系统",
            "api_hint": "可能调用的接口",
            "data_hints": ["可能访问的数据"],
            "branches": [
                {{"target_step_name": "目标步骤名", "condition": "条件", "label": "标签"}}
            ]
        }}
    ]
}}

要求：
1. 【重要】不要生成"开始"、"结束"这类虚拟节点，只生成实际的业务步骤
2. 所有步骤的step_type只能是"process"或"decision"
3. decision类型用于有分支判断的步骤，此时填写branches
4. process类型用于普通顺序执行的步骤
5. order从1开始递增
6. 步骤名称应描述实际业务动作，如"展示车卡列表"、"用户选择套餐"、"调用支付接口"等
"""


TECH_ENRICH_PROMPT = """
你是一位资深的技术架构师，擅长为业务流程补充技术实现细节。

请根据以下信息，为每个步骤补充技术实现（Implementation）和数据资源（DataResource）访问关系：

【业务名称】
{business_name}

【业务描述】
{business_description}

【渠道】
{channel}

【流程步骤】
{flow_steps}

【技术分析结果】
{analysis_result}

请输出完整的骨架结构，以JSON格式（严格遵循以下结构）：
{{
    "process": {{
        "name": "业务名称",
        "channel": "app/web/mini_program",
        "description": "业务描述"
    }},
    "steps": [
        {{
            "name": "步骤名称（实际业务动作，不要开始/结束）",
            "description": "步骤描述",
            "step_type": "process/decision"
        }}
    ],
    "edges": [
        {{
            "from_step_name": "源步骤名",
            "to_step_name": "目标步骤名",
            "edge_type": "normal/branch",
            "condition": "分支条件（仅branch时填写）",
            "label": "边标签"
        }}
    ],
    "implementations": [
        {{
            "name": "POST /api/xxx 或 ServiceName.MethodName",
            "type": "http_endpoint/rpc_method/mq_consumer/scheduled_job",
            "system": "服务名称，如 user-service、payment-service",
            "description": "实现功能描述",
            "code_ref": "服务名/controllers/xxx.py:method_name",
            "step_name": "关联的步骤名称"
        }}
    ],
    "step_impl_links": [
        {{
            "step_name": "步骤名称",
            "impl_name": "实现名称"
        }}
    ],
    "data_resources": [
        {{
            "name": "表名或资源名，如 user_card、pay_order",
            "type": "db_table/cache/mq/api",
            "system": "所属服务名称",
            "description": "数据资源描述"
        }}
    ],
    "impl_data_links": [
        {{
            "impl_name": "实现名称",
            "resource_name": "数据资源名称",
            "access_type": "read/write/read_write",
            "access_pattern": "访问模式描述，如'按user_id查询用户信息'"
        }}
    ]
}}

参考示例（Implementation命名规范）：
- HTTP接口: "POST /api/v1/user/verify_identity" 或 "GET /api/v1/card/list"
- RPC方法: "MemberCardService.CheckOpenEligibility"
- 消息队列: "PaymentResultConsumer"
- 定时任务: "CardExpirationJob"

参考示例（DataResource命名规范）：
- 数据库表: user_card, pay_order, card_plate_bind
- 缓存: user_session_cache
- 消息队列: payment_result_queue

要求：
1. 每个步骤（除start/end外）至少关联一个implementation
2. 合理推断数据资源的访问类型（read/write/read_write）
3. 确保所有引用的数据资源都在data_resources中定义
4. step_impl_links和impl_data_links使用名称引用，不要使用ID
5. edges中用步骤名称指定连接关系，按流程顺序排列
"""
