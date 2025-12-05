"""CrewAI 骨架生成提示词模板"""

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

【服务器日志】
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

==========【核心原则：严禁编造，必须有据】==========

★ systems：【严禁推测，且只能使用指定枚举】
  - 只能填写以下三个系统之一：admin-vehicle-owner, owner-center, vehicle-pay-center
  - 只有在原始数据中明确出现这些系统名称时才能填写
  - 如果原始数据中没有系统信息，数组应为空[]

★ apis：【严禁推测】
  - 只能填写原始数据（抓包/日志）中明确出现的接口路径
  - path 必须是原始数据中的完整接口路径，禁止编造
  - system 只能是以下三个之一：admin-vehicle-owner, owner-center, vehicle-pay-center
  - 如果原始数据中没有接口信息，数组应为空[]
  - 【接口路径规范】：
    * 不要包含协议和域名（去掉 https://xxx.com 部分）
    * 路径不要以斜杠开头（使用 owner-center/xxx 而不是 /owner-center/xxx）
    * 服务前缀只有：admin-vehicle-owner、owner-center、vehicle-pay-center
    * 正确示例：owner-center/backend/pc-fix-order-query

★ data_resources：【严禁推测】
  - 只能填写原始数据中明确出现的表名、缓存键、队列名
  - type 只能是：table 或 redis
  - system 只能是以下四个之一：C端, B端, 路侧, 封闭
  - 禁止根据业务描述猜测可能存在的表名
  - 如果原始数据中没有数据资源信息，数组应为空[]

★ call_sequence：【允许推断】
  - 可以根据接口调用顺序和业务描述合理推断调用流程
  - 这是唯一允许推断的字段

【重要】宁可返回空数组，也不能编造不存在的接口或表名！

为了便于系统解析，你在最终回答时必须严格遵守下面的输出格式：
- 先输出一行以 "Thought:" 开头，用中文简要说明你的分析思路，例如：
  Thought: 我将先过滤噪声请求，再梳理与业务直接相关的系统、接口和数据资源
- 然后输出一行以 "Final Answer:" 开头，后面直接跟本题要求的 JSON 结果，例如：
  Final Answer: 
  ```json
  xxxxxx
  ```
- 不要在 Final Answer 行之后再追加额外的自然语言解释，也不要再输出第二个 JSON。
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
            "step_type": "inner/outer",
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
2. 所有步骤的step_type只能是"inner"或"outer"
3. outer表示用户可见/可操作的步骤（如点击按钮、查看页面、填写表单、接收通知等用户能感知的操作）
4. inner表示用户不可见的后台步骤（如内部判断、调用外部接口、数据库操作、业务逻辑处理等后端操作）
5. order从1开始递增
6. 步骤名称应描述实际业务动作，如"用户点击开通按钮"(outer)、"校验用户资格"(inner)、"调用支付接口"(inner)、"展示支付结果页"(outer)
7. 在输出时必须先给出一行以 "Thought:" 开头的中文思考说明，概述你是如何设计这些步骤的。
8. 紧接着给出一行以 "Final Answer:" 开头的最终结果，该行后面直接跟上完整的 JSON 对象（即上面定义的 steps 结构），不要再追加其它自然语言解释。例如：
Final Answer: 
  ```json
  xxxxxx
  ```
"""


TECH_ENRICH_PROMPT = """
你是一位资深的技术架构师，擅长为业务流程补充技术实现细节。

【非常重要!!!!!】
1. 在输出时必须先给出一行以 "Thought:" 开头的中文思考说明，概述你是如何根据输入信息设计整体技术骨架的。
2. 紧接着给出一行以 "Final Answer:" 开头的最终结果，后面直接跟上完整最终回答，严格禁止在没有Final Answer字样的情况下输出最终内容！！！！！！例如：
Final Answer: 
  ```json
  xxxxxx
  ```

请根据以下信息，为每个步骤补充技术实现（Implementation）和数据资源（DataResource）访问关系：

【业务名称】
{business_name}

【业务描述】
{business_description}

【渠道】
{channel}

【流程步骤】
{flow_steps}

【技术分析摘要】
{analysis_result}

【原始技术数据 - 抓包接口】
{api_captures}

【原始技术数据 - 服务器日志】
{structured_logs}

==========【核心原则：严格区分"可推断"与"必须有据"】==========

★ 步骤（steps）：【允许推断】
  - 可以根据业务描述合理分析和推断步骤流程
  - 步骤名称、描述、类型可以基于业务逻辑推理

★ 实现单元（implementations）：【严禁推测，必须有据】
  - 必须从【原始技术数据】或【技术分析摘要】中找到明确的接口/方法信息才能填写
  - name：必须是原始数据中明确出现的接口路径或方法名（如日志中的URL、抓包中的路径），禁止编造
  - type：只能是 api / function / job
  - system：只能是以下三个之一：admin, owner-center, pay-center
  - code_ref：必须是原始数据中明确出现的代码路径，如无明确信息则填空字符串""
  - 如果原始数据中没有任何明确的技术信息，implementations数组应为空[]

★ 数据资源（data_resources）：【严禁推测，必须有据】
  - 必须从【原始技术数据】或【技术分析摘要】中找到明确的表名/资源名才能填写
  - name：必须是原始数据中明确出现的表名或资源名，禁止编造
  - type：只能是 table / redis
  - system：只能是以下四个之一：C端, B端, 路侧, 封闭
  - 如果原始数据中没有任何明确的数据资源信息，data_resources数组应为空[]

★ 关联关系（step_impl_links, impl_data_links）：
  - 只能关联上述已生成的实际节点，不能凭空创建关联

【重要提示】请仔细查阅【原始技术数据】，从中提取精确的接口路径和资源名称。

==========【输出格式】==========

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
            "step_type": "inner/outer（outer=用户可见步骤，inner=后台不可见步骤）"
        }}
    ],
    "edges": [
        {{
            "from_step_name": "源步骤名",
            "to_step_name": "目标步骤名",
            "edge_type": "normal/branch"
        }}
    ],
    "implementations": [
        {{
            "name": "【必须来自分析结果】POST /api/xxx 或 ServiceName.MethodName",
            "type": "api/function/job（api=接口，function=内部方法，job=定时任务）",
            "system": "【必须来自分析结果】服务名称",
            "description": "实现功能描述",
            "code_ref": "【必须来自分析结果，无则填空】",
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
            "name": "【必须来自分析结果】表名或资源名",
            "type": "table/redis（table=数据库表，redis=缓存）",
            "system": "【必须来自分析结果】所属服务名称",
            "description": "数据资源描述"
        }}
    ],
    "impl_data_links": [
        {{
            "impl_name": "实现名称",
            "resource_name": "数据资源名称",
            "access_type": "read/write/read_write",
            "access_pattern": "访问模式描述"
        }}
    ]
}}

==========【要求】==========

1. 步骤可以根据业务逻辑推断，但实现单元和数据资源必须严格基于【技术分析结果】中的明确信息
2. 宁可不填，也不能编造：如果分析结果中没有具体的接口/表名/服务名，对应数组留空
3. edges中用步骤名称指定连接关系，按流程顺序排列
4. step_impl_links和impl_data_links使用名称引用，不要使用ID
5. 只有明确存在的实现和数据资源才能建立关联关系

==========【接口命名规范】==========

实现单元（implementations）的 name 字段必须严格遵循以下格式：

**格式**：`{{METHOD}} {{service-prefix}}/{{path}}`

**规范**：
1. 不要包含协议和域名（去掉 https://xxx.com、http://xxx.com 部分）
2. 路径不要以斜杠开头（使用 `owner-center/xxx` 而不是 `/owner-center/xxx`）
3. 服务前缀只允许以下三种：
   - `admin-vehicle-owner`
   - `owner-center`  
   - `vehicle-pay-center`

**正确示例**：
- `POST owner-center/backend/pc-fix-order-query`
- `GET vehicle-pay-center/urlCode/unlicensedCarOut`
- `PUT admin-vehicle-owner/api/user/bindCard`

**错误示例**（禁止）：
- `POST https://xxx.com/owner-center/xxx`（包含了域名）
- `POST /owner-center/xxx`（以斜杠开头）
- `POST api/xxx`（缺少服务前缀）
"""
