"""
LLM prompts for different tasks
"""
################################################################
# Prompt 1：科研流程图分类器（中文注释：仅输出JSON + 示例）
# flowchart_classifier_prompt = r"""
# 你是一个多模态AI模型，需要根据用户提供的图片进行判断。请严格遵循以下规则：

# 判断规则：
# 1) 输出 true（是流程图/架构图）的条件：若图片为科研或工程领域的流程图、框架图、系统架构图、算法流程图或数据流向图。
# 2) 输出 false（非流程图/架构图）的条件：
#    - 实验数据图（如折线图、柱状图、散点图等）
#    - 实物或风景照片
#    - 含 emoji 或卡通元素
#    - 主要为文字截图或纯文本

# 输出要求（务必严格遵守）：
# - 仅输出严格的 JSON 对象，不要包含任何多余文字；不要使用 Markdown 代码围栏（禁止 ```json ... ```）、不要任何语言标签或包裹性文本
# - JSON 字段为：{"is_flowchart": true/false}

# 示例：
# - 示例1（是流程图）：
#   输入：一张包含多个模块与箭头、展示系统组件交互的架构图
#   输出：{"is_flowchart": true}
# - 示例2（不是流程图）：
#   输入：一张显示不同月份销售额的柱状图
#   输出：{"is_flowchart": false}

# 请分析该图片并仅输出 JSON：
# """

################################################################
# flowchart_classifier_prompt = r"""
# 你是一个专注学术场景的多模态分类器。
# 你的任务是分析给定图片，判断其是否为科研/工程语境下的“架构图/流程图”。

# --- 强制前置条件（必须满足） ---
# 必须可用 Draw.io/XML 矢量方式“完全复现”。若无法仅用标准图元（矩形/椭圆/菱形/文本标签/连线）忠实重建，则输出 false。
# 人物/卡通禁入：若包含任何具象或拟人化的图标/插画（如人头/人脸、人物剪影、机器人、吉祥物、emoji、卡通形象），无论是否矢量化，一律判定为 false。

# --- 核心判断标准 ---
# 是否由离散“功能模块”（方框/节点）与明确“连接箭头/线条”表达系统、模型、数据流、控制流或算法步骤？

# --- 否决条件（任一命中 → 输出 false） ---
# 1) 实验/数据可视化：折线/柱状/直方/散点/箱线/小提琴/雷达图、热力图、饼图、词云、谱图、显著性图、分割掩码等。
# 2) 截图或栅格化 UI：App/网页/IDE/终端截图、仪表盘、设置页面、代码编辑器等。
# 3) 照片或相机内容：人物/物体/场景、显微/医学影像、白板/纸张/PDF 的拍照扫描。
# 4) 以大段文本或纯表格为主。
# 5) 拼贴/组合：若图中图表/照片占据显著面积，或矢量节点/连线不是主要载体。
# 6) 栅格底图叠加：在截图/照片/图表上加箭头或标注；任何需要位图背景的情况。
# 7) 信息图/卡通化、装饰性插画，且非技术系统/流程示意。
# 8) 任何具象/拟人化图标/人物或机器人等角色（包括将其作为节点形状使用）。

# --- 正例判定（需全部满足 → 输出 true） ---
# a) 至少包含 ≥2 个离散模块/组件（清晰边界的形状）且 ≥1 条明确连线/箭头跨模块。
# b) 连线表达模块间的关系/流向（坐标轴、网格线、表格边框不算连线）。
# c) 主题为科研、工程或软件开发中的系统/流程。
# d) XML 复现检查清单（全部通过）：
#    - 关键信息均可用矢量形状/文本表达（不依赖照片/纹理）。
#    - 不需要任何位图/照片/截图层来传达语义。
#    - 仅用 Draw.io 基元与连线重绘，语义与结构仍完整可信。
# e) 仅允许非具象几何形状或中性技术图标（如数据库圆柱）；不允许人/机器人/吉祥物/emoji 等形象。

# --- 边界指导 ---
# - 神经网络架构、状态机、UML/ER/数据流图 → 若为纯矢量且存在连线，多为 true。
# - 以时间轴/坐标轴为主的甘特/时间线、桑基/统计图、热力图 → false。
# - UI 线框/原型或任何叠加在截图/照片上的箭头标注 → false。
# - 将人头/人脸或机器人卡通作为节点参与连线的流程图 → false。

# --- 输出要求（严格） ---
# 1) 仅输出严格 JSON 对象。
# 2) 绝不包含解释、注释、Markdown 代码围栏（禁止 ```json ... ```）、语言标签或任何包裹文本。
# 3) 字段：{"is_flowchart": true/false}

# --- 示例 ---
# 示例 1（true）：
# 输入：展示多个 Agent（如 Section Agent）与 Paper 的交互并生成 Poster 的系统架构图，包含模块与箭头。
# 输出：{"is_flowchart": true}

# 示例 2（false - 关键）：
# 输入：包含词云与两张柱状图（# of tokens, # of figures）的组合图。
# 输出：{"is_flowchart": false}

# 示例 3（false）：
# 输入：一个移动 App 设置页截图上画了箭头的说明图。
# 输出：{"is_flowchart": false}

# 示例 4（false）：
# 输入：一张显微照片/医学影像，上面加了箭头和标签。
# 输出：{"is_flowchart": false}

# 示例 5（false）：
# 输入：节点包含卡通人头与机器人图标，并以箭头相连的流程图。
# 输出：{"is_flowchart": false}

# 请分析该图片并仅输出 JSON：
# """
################################################################
# Prompt：基于上下文的学术图片描述器（中文注释：仅输出JSON + 示例）
# image_descriptor_prompt_template = r"""
# 你是一个精通计算机视觉和图论的专家研究员，擅长解构（Deconstruct）学术和工程图像。
# 你的任务是基于图片本身以及提供的上下文，按照**重要性优先**的顺序，对图片的视觉结构进行深入、详细的分析。

# --- 上下文使用策略 (Context Policy) ---
# 1.  **{context_text} 优先**：必须利用 {context_text}（例如图注或摘要，可能不完整）来理解图像的**“整体目的” (`overview`)** 和**“核心组件命名” (`components.name`)**。
# 2.  **视觉为准**：所有关于**“空间布局” (`spatial_layout`)**、**“流向与拓扑” (`flow_and_topology`)** 和**“箭头样式” (`arrows`)** 的分析，必须 100% 严格基于图像本身的视觉证据。
# 3.  **冲突处理**：如果上下文与图像视觉发生冲突（例如上下文说 A->B，但图上画的是 A->C），**必须以图像视觉为准**。

# --- 分析层级与规则 (优先级排序) ---
# 你必须按照以下三个优先级（P1 > P2 > P3）的顺序来集中注意力进行分析：

# ### 优先级 1：流程本意与核心关系 (Intent & Core Relations)
# (这是理解“图想说什么”的最重要部分。你必须在这一步完成自我审查。)

# * **1.1 容器与核心组件 (Containers & Core Components)**：(最高重点)
#     * **识别容器 (Identify Containers)**：**立即**识别所有视觉上的分组框/背景框（例如用不同颜色、虚线或实线边框包围多个元素的方框）。**这是追踪拓扑的关键**。将它们作为组件记录在 `components` 中，并（如果可能）在 `containment_hierarchy` 中重建父子关系。
#     * **识别核心组件**：识别容器*内部*和*外部*的所有关键矢量模块、文本块。
#     * **详细样式**：立即分析这些核心组件和容器的详细视觉样式 (用于 `component_styles`)，例如 `fillColor`, `strokeColor`, `shape`, `dashed=1` (虚线)。
#     * **识别背景形状 (Identify Background Shapes)**：(重点) **仔细检查**并识别那些明显位于其他元素（尤其是文本块）*后方*的彩色方框（如本图中的橙色、紫色、蓝色框）。在 `component_styles` 中为它们添加一个明确的标记，例如 `is_background: true` 或 `zIndex: -1`，以表明它们必须被渲染在图层底部。
#     * **文本与背景的强制分离 (Mandatory Text vs. Background Separation)**：
#        * 检查【原始图片】。如果你看到一个**文本标签**（例如 `X^T`, `H^-1_-q`, `L`）**位于**一个**彩色/带网格的背景形状**（例如黄色网格、蓝色网格）*之上*。
#        * 你**必须**将它们识别为**两个独立的组件**：
#        * 1. **文本标签**：例如 `{"name": "X^T", "description": "转置矩阵"}`。在 `component_styles` 中，它**必须**是 `fill="none"`, `stroke="none"` (无填充、无边框)。
#        * 2. **背景形状**：例如 `{"name": "X^T (背景网格)", "description": "黄色网格"}`。在 `component_styles` 中，它**必须**有 `fillColor`, `strokeColor`，并且**必须**标记为 `is_background: true`。
#        * 在 `spatial_layout.relative_positions` 中，你**必须**添加一个条目，例如 `"文本 'X^T' 位于 'X^T (背景网格)' 的上方"`。
#        * **(关键禁令)**：**严禁**将文本和背景合并为*一个*组件（例如 `{"name": "X^T", "fill": "#FFFFE0"}`）。这将导致 XML 渲染失败。
#     * **矢量化决心**：对于所有识别出的“核心组件”，如果原始图片中它是一个**矢量图形**组成的（无论多么复杂，例如分子结构图、树状图、神经网络结构图、复杂的坐标系等），**绝不允许**仅用文本描述来代替原始**矢量图形**。即使复杂到难以描述，也**必须尝试提供其主要构成元素和布局线索**。
#     * **子图（Graph-in-Graph）的结构化描述**：(重点) 当一个“核心组件”（例如 “Input Graph (A)”）的*内部*本身就是一个矢量图（如节点-链接图）时，你**必须**在 `relationships_extended` 字段中，使用 `type: "describes_subgraph"` 来**结构化地**描述这个子图。`note` 字段必须包含该子图的**节点列表 (nodes)** 和**边列表 (edges)** 的文字描述。例如：`"note": "子图包含: [nodes: 5 个蓝色圆形节点], [edges: 7 条黑色实线边], [topology: 节点1连接2, 1连接3... (如果可读)]"`。**绝不能**只说“包含一个图”而不提供其结构。
#     * **识别括号与括弧 (Identify Brackets & Braces)**：(重点) **立即**扫描所有用于*分组*的独立括号 `()`、方括号 `[]` 或大括弧 `{}`。
#        * 1. **视为组件**：你**必须**将这些括弧本身视为一个**核心组件**（例如 `name: "分组括弧 {"`）。
#        * 2. **描述样式**：在 `component_styles` 中记录其样式，尤其是 `shape`（例如：`shape: "curlyBrace"` 或 `shape: "bracket"`）。
#        * 3. **描述分组**：在 `relationships_extended` 中使用新增的 `type: "groups"` 来明确描述它“罩住”了哪些其他组件。
#     * **内部矩阵模式 (Internal Matrix Patterns)**：(重点) 当一个组件是矩阵（如 `H^-1`, `L`, `M_U`）并显示出**内部结构**时（例如：单元格网格、三角形状、块状着色，如“0-valued”和“1-valued”的组合），你**必须**：
#        * 1. 在 `relationships_extended` 中使用 `type: "describes_structure"`。
#        * 2. 在 `note` 字段中**详细描述这个模式**。例如：`"note": "一个 n x n 网格。下三角区域被标记为 '0-valued' (浅灰色)，对角线被标记为 '1-valued' (深灰色)。"`
#        * 3. **(关键禁令)** **严禁**将此结构信息仅放入 `components.description` 字段。`description` 字段仅用于高级功能描述（例如：“...的逆矩阵”），而 `relationships_extended` **必须**用于*视觉重建指令*。
#     * **识别核心组件**：识别容器*内部*和*外部*的所有关键矢量模块、文本块。
#     * **ID/名称唯一性 (ID/Name Uniqueness)**：(关键) 在 `components` 列表中，**必须**确保*每一个*组件的 `name` 字段都是**唯一的**。如果两个组件在视觉上是独立的（例如图例中的两个不同文本标签），它们绝不能共享同一个 `name`。例如，如果图例中有两个 "text" 标签，它们应该被命名为 "legend_text_1" 和 "legend_text_2" 或 "legend_result" 和 "legend_telemetry"，而不是两个都叫 "legend_text"。

# * **1.2 流向、拓扑与箭头 (Flow, Topology & Arrows)**：(最高重点)
#     * **追踪与拓扑 (Trace & Topology)**：(最高重点) 你**必须**追踪*每一条*从一个 `from` 到一个 `to` 的*独立*箭头路径。
#         * **分裂与共用主干 (Splitting & Shared Trunks)**：(关键升级)
#           虽然 A->B 和 A->C 是两个逻辑箭头，但如果它们在视觉上**共用了一段路径**（例如：从 A 出来是一条线，在中间分叉指向 B 和 C），你必须：
#           1. 在 `arrows.details` 中为这两个箭头分配相同的 `visual_group_id` (例如 "group_branch_1")。
#           2. 在 `path_description` 中明确描述这种分叉结构。例如："与 A->C 共用垂直主干，在 Y 轴中心处向左分叉连接 B"。
#           3. **绝对禁止**将这种结构描述为两条完全独立的平行线，除非图上真的画了两条线。
#         * **汇聚 (Merging)**：(关键) 同理，如果 `A` 和 `B` 都指向 `C`，这也是**两个独立的箭头**：`{"from": "A", "to": "C", ...}` 和 `{"from": "B", "to": "C", ...}`。
#         * **双向 (Bidirectional)**：(关键) 仔细检查箭头是*单向* (`A -> B`) 还是*双向* (`A <-> B`)。**如果一个连接是双向的**，你**必须**在 `arrows.details` 中将其标记为 `is_bidirectional: true` 和 `heads: "double arrow"`。
#     * **特殊连接 (关键点)**：
#       * **括弧与箭尾 (Braces & Tails)**： 仔细检查箭头的*尾部* (source) 连接到了什么。如果它连接到了一个括弧（如 `{`）或有特殊的 T 型（`T-bar`）连接，你**必须**在 `arrows.details.tails` 字段中记录它，并将 `from` 字段正确指向该括弧组件（如 `from: "分组括弧 {"`）。
#       * **详细样式与路由**：
#           * **节点到节点 (Node-to-Node)**：追踪从一个形状到另一个形状的箭头。
#           * **节点到容器 (Node-to-Container)**：(重点) **仔细检查是否存在从一个节点出发，最终指向一个“容器”边界的箭头**（例如，原图中的 'Opinion' 箭头指向黄色方框）。你**必须**将这个容器的名称（或ID）记录在 `arrows.details.to` 字段中。
#           * **节点到括弧 (Node-to-Brace)**：(新增重点) 仔细检查是否有箭头（尤其是箭头尾部）**直接连接到括弧或括号符号本身**。如果是，你**必须**在 `arrows.details` 的 `from` 或 `to` 字段中，使用该括弧的组件名称（例如 `from: "分组括弧 {"`）。
#           * **路由 (Routing)**：(关键) 明确描述箭头的布线风格。**必须**从以下选项中选择：
#             * `routing: "straight"` (直线)
#             * `routing: "orthogonal"` (正交/直角线，用于 draw.io 的 `edgeStyle=orthogonalEdgeStyle`)
#             * `routing: "curved"` (曲线)
#     * **箭头头部样式 (Arrowhead Styling)**：(新增重点) 详细描述箭头*头部* (`endArrow`) 和*尾部* (`startArrow`) 的视觉样式。
#         * `heads: "single arrow"` (默认, 例如 `endArrow=classic`)
#         * `heads: "double arrow"` (双向, 例如 `endArrow=classic;startArrow=classic`)
#         * `heads: "no head"` (仅为线条, 例如 `endArrow=none;`)
#         * `tails: "none" | "T-bar" | "circle"` (描述箭尾的特殊样式)
#     * **路径交互与穿越 (Path Interactions & Crossings)**：(关键新字段)
#       你必须检查每条箭头在从 Source 到 Target 的路途中，是否与其他元素发生了**空间交互**。
#       在 `arrows.details` 中添加 `interacts_with` 列表：
#       - 格式: `[{"component": "中间的模块B", "type": "passes_through" | "passes_behind" | "jumps_over" | "touches_boundary"}]`
#       - **Passes Through**: 线条直接穿过了该组件的内部（通常意味着该组件是透明背景或线条位于顶层）。
#       - **Passes Behind**: 线条被该组件遮挡（虚线或中断）。
#       - **Jumps Over**: 线条画了一个“拱门”跨越了另一条线。
#       - **Touches Boundary**: 线条仅接触了组件的边界（例如，箭头尾部连接到模块的左边界）。
#     * **箭头样式严格性 (Arrow Style Strictness)**：你的任务是*描述*视觉上存在的箭头，**严禁*发明*或*替换*样式**。如果原图中的箭头是`细`、`黑色`、`虚线` (dashed)，你的 JSON 描述**必须**反映 `style="dashed"`, `color="黑色(#000000)"`, `thickness="thin"`。**绝不能**将其替换为 `shape=flexArrow` (块箭头) 或其他任何原图不存在的样式（如本例中的蓝色粗箭头）。
#     * **几何与坐标系描述 (Geometric & Coordinate System Description)**：(重点) 如果图片包含**几何图形、坐标系（如三维坐标轴）、或者带有明确数值标记的点**，你必须：
#         * 在 `components.description` 或 `relationships_extended` 中详细描述其组成元素（例如：“X、Y、Z轴”、“球坐标的径向向量”）。
#         * 在 `arrows.details.notes` 或 `relationships_extended` 中描述其连接或指示关系。
#         * **对于文本描述的坐标或数值**（例如：`(-0.01, -0.77, 1.26)`），将其视为关键文本在 `components.name` 中捕获，并确保其布局位置能够被 XML 生成器重现。        
#     * **连接端口 (Connection Ports)**：为了消除布局混乱，你**必须**描述箭头连接到其源和目标形状的**精确相对位置**。
#         * 在 `arrows.details` 对象中添加一个名为 `connection_ports` 的**新对象**。
#         * 此对象包含两个键：`source_port` 和 `target_port`。
#         * `source_port`：描述箭头*离开* `from` 组件的位置。
#         * `target_port`：描述箭头*进入* `to` 组件的位置。
#         * **值示例**：使用描述性术语，如 `"middle_left"`, `"middle_right"`, `"top_center"`, `"bottom_center"`, `"top_left_corner"`, `"bottom_right_corner"` 等。
#         * **JSON 示例**: `..., "connection_ports": {"source_port": "middle_right", "target_port": "middle_left"}`
#     * **详细空间关系 (Path Description)**：(重点) 将 `notes` 字段升级为 `path_description`。
#         * (错误示例 - 语义)：`"notes": "Represents Q1 being sent..."`
#         * (正确示例 - 视觉)：`"path_description": "一条笔直的水平线，从 rank1 的右侧连接到 rank0 的左侧。"`
#         * (正确示例 - 正交)：`"path_description": "从 rank0 底部出发，向下，然后右转90度，再向下，连接到 rank3 的顶部。"`
#     * **捕捉所有结构性线条 (Capture All Structural Lines)**：(关键新规) 你不仅要追踪代表“流向”的箭头，还**必须**捕捉所有用于指示“关系”或“分组”的线条。
#         * 例如，连接 `x_0`, `x_i'`, `x_N-1` 的**垂直虚线**是“批处理”关系的一部分。
#         * 你**必须**将这些线条作为 `arrows.details` 中的独立条目来描述。
#         * **示例 (对于垂直虚线)**：
#           `{"from": "Input Sample x_0", "to": "Backdoored Input Sample x_i'", "direction": "上->下", "color": "灰色(#808080)", "style": "dotted", "thickness": "细", "heads": "no head", ... "path_description": "连接批处理中 x_0 和 x_i' 的垂直虚线。"}`
#           `{"from": "Backdoored Input Sample x_i'", "to": "Input Sample x_N-1", "direction": "上->下", "color": "灰色(#808080)", "style": "dotted", "thickness": "细", "heads": "no head", ... "path_description": "连接批处理中 x_i' 和 x_N-1 的垂直虚线。"}`

# * **1.3 关键文本 (Key Text)**：
#     * 识别并转录流程框体、箭头标签上的**所有文本** (用于 `arrows.details.label` 和 `components.name`)。
#     * **所有细节文本捕获 (Capture All Detailed Text)**：除了流程框体和箭头标签上的文本，你还必须识别并转录所有**图示中的微小但具有语义的文本**，例如：数值、数学表达式、坐标点、特定标签（如“Atom 1”）。这些文本是矢量化图形的关键组成部分。

# * **1.4 栅格图像 (Raster Images - 原'非矢量图形')**：(范围已严格缩小) 此规则**仅**适用于**真正的栅格图像 (Raster Images)**，例如：
#     * **照片 (Photos)**：真实世界的人、物体、风景的照片。
#     * **用户界面截图 (UI Screenshots)**：软件、App或网站的界面截图。
# * (重点) 如果一个元素是*示意图*、*图表*、*草图*或*图示*（无论多复杂，如分子图或手绘风格的*流程图*），它**不**属于这里，而**必须**在 P1.1 和 P1.2 中被强制解构为矢量。

# * **1.5 文件与工件 (Files & Artifacts)**：
#     * 识别数据流中涉及的文档、数据集、代码文件等 (用于 `files_and_artifacts`)。

# ### 优先级 2：全局布局与次要样式 (Global Layout & Secondary Styles)
# (这是关于“图是怎么画的”的全局和次要细节。)
# * **全局空间布局 (Global Spatial Layout)**：描述**整体**布局（左->右、上->下）、**全局对齐**、等距分布 (用于 `spatial_layout`)。
# * **次要组件样式 (Secondary Component Styling)**：分析 P1 未覆盖的次要组件（如背景框）的样式。
# * **颜色与字体 (Color & Typography)**：提取**全局**色板；识别有语义的字体（如代码体）(用于 `color_palette`, `typography`)。
# * **其他结构 (Other Structures)**：识别结构模式（重复、对称）、图例、多面板布局 (用于 `structural_patterns`, `legend_and_symbols`, `panel_layout`)。

# ### 优先级 3：装饰性元素 (Decorative)
# (这是最后需要考虑的、不影响核心流程本意的元素。)
# * **装饰性内容 (Decorative Content)**：识别并统计 Emoji、贴纸、吉祥物、装饰性象形图（非流程图标）等 (用于 `non_diagram_elements`)。

# --- 预备思考步骤 (分层校对) ---
# 在生成最终 JSON 之前，你必须在“脑海中”按顺序执行以下步骤：

# 1.  **思考 (P1 - 流程本意)**：
#     * 结合 {context_text} 和图像，分析上述 P1 规则（核心组件、**详细样式**、**包含关系**、**详细箭头分析**、关键文本、非矢量截图）。
#     * 形成关于“流程本意”的草稿。

# 2.  **校对 (P1 - 流程本意审查)**：
#     * **自我审查（双重检查）**：
#         * "我是否准确理解了 {context_text}？"
#         * "P1 的流程拓扑是否完整？"
#         * "核心组件的**颜色、包含关系**是否分析准确？"
#。       * "**箭头清点 (Arrow Count)**：(关键自检) 我在“脑海中”视觉清点图像，确认图上**总共有 18 条箭头**（包括所有带标签的、不带标签的、以及 'permute' 和 'all2all' 的箭头）。我的 `arrows.details` 列表的**最终长度**是否也等于 18？如果数量不匹配，我必须重新分析图像，直到找出所有被遗漏的箭头。"
#         * "箭头的**路由（弧形/直线/正交）、虚实、分裂、以及 notes 中的空间关系（是否穿过模块、是否接触边界、与文本/箭头关系）**是否都已详细描述？"
#         * "是否遗漏了关键的**非矢量截图**？"
#         * "文本是否转录准确？"
#     * 修正 P1 的草稿，直到它 100% 准确反映流程。

# 3.  **思考 (P2 - 全局布局)**：
#     * 基于 P1 的结果，分析 P2 规则（全局布局、次要样式、全局色板）。
#     * 形成关于“矢量实现”的草稿。

# 4.  **校对 (P2 - 全局布局审查)**：
#     * **自我审查**：“P2 的全局布局描述（如对齐）是否与图像一致？”
#     * 修正 P2 的草稿。

# 5.  **思考 (P3 - 装饰元素)**：
#     * 分析 P3 规则（Emoji、贴纸等）。

# 6.  **最终生成 (Combine & Format)**：
#     * 将 P1, P2, P3 的所有思考结果，**合并并填充**到下面 `--- 输出要求 ---` 指定的**单一、完整**的 JSON 结构中。

# --- 输出要求（务必严格遵守） ---
# 1. 仅输出严格的 JSON 对象。
# 2. 严禁在 JSON 外包含任何解释、注释或文字；禁止使用 Markdown 代码围栏（禁止 ```json ... ```）、语言标签或任何包裹性文本。
# 3. JSON 必须包含以下字段（Schema 已更新）：
#    - "image_type": (字符串) 图片的最高级别分类。
#    - "overview": (字符串) 对图片功能或目的的 1-2 句话总结。
#    - "components": (对象列表) 识别、计数和描述关键组件。
#      - 格式: [{"name": "组件名", "count": 数量, "description": "组件的简要功能描述"}]
#    - "spatial_layout": (对象) 描述空间、投影和度量关系。
#      - "primary_layout": "整体布局描述(例如：左到右流程，垂直堆叠)"
#      - "relative_positions": ["组件A 在 组件B 的上方", "组件C 在 组件D 的左侧"]
#      - "alignment": ["组件A, B, C 垂直对齐"]
#    - "flow_and_topology": (对象) 描述流向和拓扑结构。 (P1.2 中关于"汇聚"、"循环"、"多重边"的总结性分析结果应填入此处的 `structures` 列表)
#      - "primary_flow": "描述主要的A->B->C流向"
#      - "structures": ["拓扑结构：汇聚（Convergence）。'数据源 A' 和 '数据源 B' 的输出汇聚到 '处理模块 C'。", "拓扑结构：反馈循环（Loop）。'模块C' 与 '模块D' 之间存在双向箭头。", "拓扑结构：多重边（Multi-Edge）。'模块A' 与 '模块B' 之间同时存在一条实线和一条虚线。"]
#    - "structural_patterns": (字符串列表) 描述重复、对称等模式。
#      - 格式: ["模式描述1 (如: 'Agent <-> Checker' 的配对模式重复了3次)"]
#    - "non_diagram_elements": (对象列表，可选) 列出截图/照片/卡通/emoji/贴纸/信息图等非图示元素。(此字段现在会优先填充 P1.4 中的截图/照片，其次是 P3 中的 Emoji)
#      - 格式: [{"category": "screenshot|photo|cartoon|emoji|infographic|decorative|other", "count": 2, "examples": ["移动UI截图", "标签中的emoji"]}]
#    - "arrows": (对象，可选) 汇总连线样式与代表性样例。(此字段现在由 P1.2 的分析结果填充，**注意 `routing` 和 `notes` 字段**)
#        - "summary": {"total": 4, "bidirectional": 1, "styles": ["solid green", "dashed gray"], "multi_edge_pairs": 1}
#    -"details": [
#             {"from": "模块A", "to": "模块B", "visual_group_id": "branch_group_1", "direction": "左->右", "color": "绿色(#00A000)", "style": "solid", "thickness": "中", "heads": "single arrow", "tails": "none", "is_bidirectional": false, "label": "forward pass", "routing": "straight", "connection_ports": {"source_port": "middle_right", "target_port": "middle_left"},  "interacts_with": [{"component": "Background Layer 1", "type": "passes_over"}], "path_description": "一条笔直的水平线，接触 '模块B' 边界。"},
#             {"from": "模块A", "to": "模块C", "visual_group_id": "branch_group_1", "direction": "双向", "color": "灰色(#808080)", "style": "dashed", "thickness": "细", "heads": "double arrow", "tails": "none", "is_bidirectional": true, "label": null, "routing": "curved", "connection_ports": {"source_port": "top_center", "target_port": "top_center"},  "interacts_with": [{"component": "Background Layer 1", "type": "passes_over"}], "path_description": "一条穿过 '模块D' 的曲线。"},
#             {"from": "模块F", "to": "模块G", "visual_group_id": "branch_group_1", "direction": "上->下", "color": "黑色(#000000)", "style": "solid", "thickness": "细", "heads": "single arrow", "tails": "none", "is_bidirectional": false, "label": null, "routing": "orthogonal", "connection_ports": {"source_port": "bottom_center", "target_port": "top_center"},  "interacts_with": [{"component": "Background Layer 1", "type": "passes_over"}], "path_description": "这是分裂箭头的第一条路径，为正交走线。"},
#             {"from": "模块X", "to": "模块Y", "visual_group_id": "branch_group_1", "direction": "上->下", "color": "灰色(#808080)", "style": "dotted", "thickness": "细", "heads": "no head", "tails": "none", "is_bidirectional": false, "label": null, "routing": "straight", "connection_ports": {"source_port": "bottom_center", "target_port": "top_center"},  "interacts_with": [{"component": "Background Layer 1", "type": "passes_over"}], "path_description": "一条结构性虚线，用于表示批处理关系。"}
#           ]
#    - "color_palette": (对象，可选) 全局色板摘要。
#      - "colors": [{"name": "蓝色", "hex": "#3A7BD5", "proportion": 0.35}]
#    - "component_styles": (列表，可选) 组件级样式摘要。(此字段现在由 P1.1 的分析结果填充)
#      - 例如: [{"component": "模块A", "shape": "rounded rectangle|ellipse|curlyBrace|bracket", "fill": "#dae8fc", "stroke": "#6c8ebf", "text": "#000000", "radius": 10, "icon": "database|cloud|gear|null", "shadow": false, "is_background": false}]
#    - "containment_hierarchy": (对象，可选) 容器/子元素树。(此字段现在由 P1.1 的分析结果填充)
#      - "root": {"name": "Canvas", "children": [{"name": "分组1", "children": ["模块A", "模块B"]}]}
#    - "relationships_extended": (列表，可选) 超越边的关系，或对复杂组件内部结构的描述。
#      - 例如: [
#          {"type": "contains|adjacent|overlay|references|reads_from|writes_to|calls|produces|layout_detail|groups", "source": "模块A", ...},
#          {"type": "describes_structure", "source": "组件B", ... "note": "组件内部包含一个带 X, Y, Z 轴的3D坐标系。"},
#          {"type": "layout_detail", "source": "GPT Block #1", ... "note": "内部子模块布局非常紧凑..."},
#          {"type": "describes_subgraph", "source": "组件C", ... "note": "子图包含: [nodes: 5 个节点]..."},
#          {"type": "groups", "source": "分组括弧 {", "target": null, "evidence": "visual", "note": "此括弧在视觉上罩住了 [模块A, 模块B]。"}
#          {"type": "describes_subgraph", "source": "组件C", ... "note": "子图包含: [nodes: 5 个节点]..."},
#          {"type": "groups", "source": "分组括弧 {", ... "note": "此括弧在视觉上罩住了 [模块A, 模块B]。"},
#          {"type": "describes_structure", "source": "矩阵 L", "target": null, "evidence": "visual", "note": "n x n 网格。下三角区域为 '0-valued' (浅灰)。"}
#        ]
#    - "files_and_artifacts": (列表，可选) 检测到的文件/文档及其关联。
#      - 例如: [{"name": "report.pdf", "kind": "document|dataset|code|config|log", "linked_to": ["模块C"], "relation": "produces"}]
#    - "panel_layout": (对象，可选) 多面板描述。
#      - {"panels": 1, "layout": "single|grid|row|column", "labels": []}
#    - "legend_and_symbols": (对象，可选) 图例信息。
#      - {"has_legend": false, "items": []}
#    - "typography": (对象，可选) 重要排印信息。
#      - {"monospace_used": false, "bold_italic_used": false}
#    - "ports_and_edge_semantics": (对象，可选) 端口与边语义。
#      - {"has_ports": false, "edge_types": ["data"]}
#    - "background_layers": (对象，可选) 背景/分层信息。
#      - {"has_raster_background": false, "z_order_notes": null}

# 4. 空字段处理 (Handling of Empty/Optional Fields):
#    - 对于所有在 Schema 中标记为 `(可选)` 的字段：
#    - 如果在图像中**未找到**任何对应内容，你**必须**在 JSON 中保留该键（Key）。
#    - 如果该字段的期望值是**列表 (List)**，则输出一个**空列表 `[]`**。
#    - 如果该字段的期望值是**对象 (Object)**，则输出 `null` 或一个符合其结构但内容为空的对象（例如：`{"has_legend": false, "items": []}`）。
#    - 这样可以确保输出的 JSON 始终具有一致的顶层结构。

# --- 最终指令（严格遵守） ---
# 1.  分析以上图片。
# 2.  你的唯一输出必须是且仅是一个 JSON 对象。
# 3.  严禁在 JSON 之前或之后包含任何文本、注释、解释或 Markdown 标记（如 ```json ... ```）。

# 请基于以上规则和上下文，分析该图片并仅输出 JSON：
# """
################################################################
# image_to_xml_prompt_template = r"""
# 你是一个极其精确和细致的 Draw.io 图表生成专家。
# 你的任务是基于一个【JSON 描述草稿】和【原始图片】，生成一个单一、完整、语法正确且可解析的 Draw.io XML 文件。

# --- 核心输入 ---

# 【JSON 描述草稿】:
# (这是一个高质量的草稿，用于提供组件名称、样式和基本拓扑的“提示”)
# {json_description}

# 【原始图片】:
# (这是唯一的“事实来源”。你必须用它来进行最终的视觉核查)

# --- 核心规则 (图片优先) ---

# 1) 核心任务 (以图为主，以 JSON 为辅)
# - **图片是最终裁决者 (Image is Ground Truth)**：你**必须**将【原始图片】作为验证所有事实的最高标准。
# - **JSON 是高质量草稿**：你**应该**首先使用【JSON 描述草稿】来快速理解图表的结构、组件名称 (`components.name`)、样式 (`component_styles`) 和标签 (`arrows.label`)。
# - **禁止重新分析文本上下文**：你不再需要处理 `{context_text}`，你的所有信息来源仅限于【JSON 描述草稿】和【原始图片】。

# 2) XML 输出规范 (STRICT)
# - **单一文件**：回复必须只有 XML 内容，严禁任何解释文字/前后缀/Markdown 围栏。
# - **禁止围栏与前后缀**：不得出现任何 Markdown 代码围栏（包括 ```xml、```html、``` 与 ~~~ 形式）。
# - **根与结构**：以 `<mxfile ...>` 开头，以 `</mxfile>` 结尾。
# - **画布设置**：`<mxGraphModel>` 必含 `grid="1" gridSize="10" guides="1" page="1"`...
# - **元素规范**：
#     - 所有可见元素（形状、线条、文本）均为 `<mxCell>`。
#     - 每个 `<mxCell>` 必含 `id`, `value`, `style`, `parent`，并包含 `<mxGeometry ... as=\"geometry\"/>`。
#     - **id 全局唯一 (CRITICAL)**：你**必须**确保*每一个* `<mxCell>` 上的 `id` 属性都是**全局唯一的**。**在从【JSON 描述草稿】的 `components.name` 字段生成 `id` 时，你必须负起最终责任**：如果 JSON 草稿*意外地*提供了重复的 `name`，你**必须**在生成 XML 时主动为它们添加后缀（例如 `_1`, `_2`）或以其他方式去重，以确保 XML 输出中**绝不**包含重复的 `id`。
#     - 禁止悬挂 `source/target`；字符串需 XML 转义；禁止 DOCTYPE/外部实体与控制字符；属性引号必须是标准双引号（"）。
#     - **属性语法 (CRITICAL ERROR CHECK)**：你必须确保*每一个* `<mxCell>` 标签上的*所有*属性都遵循 `name="value"` 的格式。**禁止**出现 `name="value name="value"` 这种因缺少引号而导致的属性错误。`parent="1" vertex="1"` 是正确的。`parent="1 vertex="1"` 是**错误的**，会导致 "attributes construct error"。
#     - **边单元格 (Edge) 语法 (CRITICAL)**：**严禁**使用自闭合的边标签（例如 `<mxCell edge="1" ... />`）。每一个 `edge="1"` 的 `<mxCell>` 都**必须**是一个父标签，并且**必须**在其内部包含一个 `<mxGeometry relative="1" as="geometry" />` 子标签。`</mxCell>`。省略这个子标签将导致边无法渲染，这是一个严重的失败。
# - **XML 转义 (CRITICAL ERROR CHECK)**：
#   - 这是你报告的“非绘图文件”错误。你**必须**遵循此规则以防止该错误。
#   - 当你对一个单元格使用 `style="...html=1;..."` 时，你应该在 `value` 属性中使用 HTML 标签（如 `<b>` 或 `<font>`）来添加格式。
#   - **但是**：`value` 属性本身仍然是 XML 的一部分。因此，这些 HTML 标签**必须被 XML 转义**。
#   - **规则 (尖括号)**：属性值中的**所有** `<` 字符**必须**写成 `&lt;`。所有 `>` 字符**必须**写成 `&gt;`。**此规则适用于所有 HTML 标签，包括 `<b>`, `<font>`, `<i>`, `<u>`, 以及 `<br>`。**
#   - **规则 (Ampersand &)**：(新增重点) 同理，属性值中的所有 `&` 字符 (ampersand) **必须**写成 `&amp;`。
#   - **此规则对 HTML 实体（如 &nbsp;）的转义至关重要！**
#   - **示例 (错误 - 导致解析器失败):**
#     `value="<b>Positive:</b> <font ...>red</font>"` (错误: 未转义的 <)
#     `value="Line 1<br>Line 2"` (错误: 未转义的 <br> 标签，这是你遇到的失败)
#     `value="Text &nbsp; spacing"` (错误: 未转义的 & 字符)
#     `value="Text &ampnbsp; spacing"` (错误: 缺少分号，导致 'ampnbsp' 错误)
#   - **示例 (正确 - XML 安全):**
#     `value="&lt;b&gt;Positive:&lt;/b&gt; &lt;font color='#ff0000'&gt;red&lt;/font&gt;"`
#     `value="Line 1&lt;br&gt;Line 2"` (正确: <br> 被正确转义)
#     `value="Text &amp;nbsp; spacing"` (正确: &nbsp; 被正确转义为 &amp;nbsp;)
# - **禁止使用外部图片 (CRITICAL: No External Images)
#   - 你绝不能在你的 XML 输出中使用 `style="...shape=image;..."` 并链接到外部 URL (如 `image=https://...`) 来作为矢量化的快捷方式。
#   - 这是一种被严厉禁止的“作弊”行为。
    

# 3) 布局与样式指南 (JSON 辅助)
# - **布局 (图片辅助)**：
#   - **对齐**：所有 `x`, `y`, `width`, `height` 值必须是 `gridSize` (10) 的倍数。
#   - **定位**：严格参考【原始图片】的视觉布局来规划你的网格布局（`x`, `y` 坐标）。
#   - **间距**：保持组件间距均匀（例如 40–60 单位）。避免重叠。
# - **形状与颜色 (JSON 辅助)**：
#   - **优先使用**【JSON 描述草稿】中 `component_styles` 字段提供的样式信息（如 `fillColor`, `strokeColor`, `shape`）。
#   - 如果 JSON 未提供样式，则使用以下专业、高对比度的默认配色：
#   - 推荐：组件蓝色 (`fillColor=#dae8fc;strokeColor=#6c8bf;`)、流程绿色 (`fillColor=#d5e8d4;strokeColor=#82b366;`)。
# - **括弧/括号的强制渲染 (CRITICAL: Mandatory Brace/Bracket Rendering)**：
#   - * 【JSON 描述草稿】在其 `component_styles` 和 `relationships_extended` 中**已经正确地**识别了 `shape: "curlyBrace"` (大括弧) 或 `shape: "bracket"` (方括号) 的组件。
#   - * 你的任务是**无条件执行** (unconditionally execute) 这些指令。
#   - * 你**必须**在 `<mxCell>` 的 `style` 中使用 Draw.io 对应的括弧形状 (例如 `style="shape=brace;...` 或 `style="shape=bracket;...`)。
#   - * 你**必须**使用【原始图片】来精确调整其 `direction`（例如 `direction=south` 使其开口朝下或 `direction=west` 使其开口朝右）和 `width`/`height`，使其正确地罩住 JSON `relationships_extended` 中 `note` 字段所描述的元素。
#   - * **(失败点检查)**：**绝不允许**跳过或忽略 `shape: "curlyBrace"` 指令。这被视为严重的功能性失败。
# - **连接线 (JSON 辅助, 图片核查)**：
#     - **拓扑**：你**必须**为【JSON 描述草稿】中 `arrows.details` 列表中的*每一个*对象创建一个*独立*的 `<mxCell edge="1">`。如果 JSON 包含两条 `from: "A"` 的记录，你就必须创建两条从 `A` 出发的边。
#     - **样式 (虚实)**：优先使用 JSON 中的 `style` 字段（例如 `style="dashed"`），并用【原始图片】核查。
#     - **头部/尾部样式 (Head/Tail Styling)**：(关键) 你**必须**读取 JSON 中的 `heads` 和 `tails` 字段来构建样式：
#       - 如果 `is_bidirectional` 为 `true` 或 `heads` 为 `"double arrow"`，你**必须**在 style 中添加 `startArrow=classic;endArrow=classic;`。
#       - 如果 `heads` 为 `"no head"`，你**必须**添加 `endArrow=none;`。
#       - 如果 `tails` 字段提供了特殊样式（例如 `"T-bar"`），你**必须**添加对应的 `startArrow` 样式 (例如 `startArrow=block;...`)。
#     - **路由 (Routing) (关键新规则)**：
#       - 优先使用 `routing` 字段。如果为 `curved`，**必须**使用 `<Array as="points">`。
#       - 如果为 `orthogonal`，你**必须**在 `style` 中添加 `edgeStyle=orthogonalEdgeStyle;`。
#       - 如果为 `straight`，则不添加 `edgeStyle`。
#     - **连接端口 (Connection Ports) (关键新规则)**：
#       - 你**必须**读取 `connection_ports` 对象 (`source_port` 和 `target_port`)。
#       - 基于这些值（例如 `"middle_right"` 或 `"top_center"`），你**必须**在 `<mxCell edge="1">` 的 `style` 属性中计算并添加**精确的 Draw.io `exitX`, `exitY`, `entryX`, `entryY` 锚点**。
#       - **示例 (style 中)**：
#         - `...source_port: "middle_right"` 对应 `exitX=1;exitY=0.5;`
#         - `...target_port: "top_center"` 对应 `entryX=0.5;entryY=0;`
#         - `...source_port: "bottom_left_corner"` 对应 `exitX=0;exitY=1;`
#       - **这是消除箭头混乱的最重要指令。**
#     - **边标签**：优先使用 `label` 字段的文本。
#     - **路径描述 (辅助)**：使用 `path_description` 字段作为辅助线索，来帮助你规划正交 (`orthogonal`) 或曲线 (`curved`) 路径的 `points`。
#     - **布局 (图片辅助)**：
#       - **对齐**：所有 `x`, `y`, `width`, `height` 值必须是 `gridSize` (10) 的倍数。
#       - **画布居中 (Canvas Centering) (CRITICAL)**：**禁止**将所有元素堆积在画布的左上角（例如 `x=10, y=10`）。你**必须**利用 `<mxGraphModel>` 中定义的 `pageWidth` 和 `pageHeight`（例如 1200x800）来规划布局。**必须**为你的绘图计算一个“全局偏移量”（例如，一个 `offsetX=100`, `offsetY=150` 的边距），并将此偏移量添加到所有组件的 `x` 和 `y` 坐标上，以确保图表在画布上大致居中且易于查看。
#       - **合理缩放 (Reasonable Scaling)**：使用【原始图片】的布局作为比例指南。如果【JSON】草稿中有 3 个水平排列的组件，不要将它们挤在 200 像素内；将它们分布在 600-800 像素的宽度上，以匹配原始图像的观感和比例。
#       - **间距**：(此条保留) 保持组件间距均匀（例如 40–60 单位）。避免重叠。

# 4) 关键：1:1 箭头完备性指令 (强制)
# - 【JSON 描述草稿】中的 `arrows.details` 列表是拓扑结构的绝对事实来源。
# - 你必须遍历此列表，并为该列表中的*每一个*对象*精确地*创建一个 `<mxCell edge="1">`。
# - 如果 JSON `arrows.details` 列表包含 14 个条目，你的最终 XML 输出必须精确包含 14 个 `<mxCell edge="1">` 元素。
# - 如果 JSON 包含 4 个条目，你的输出必须包含 4 条边。
# - 生成不完整的边集（例如，14 条中只生成了 12 条）被视为严重的功能性失败和“摆烂”。你必须生成所有 14 条。

# 5) Z-Order (图层) 管理 (CRITICAL)
# - **识别背景**：检查【JSON 描述草稿】的 `component_styles` 中是否有 `is_background: true` 或 `zIndex: -1` 的组件。
# - **渲染顺序（关键）**：在生成 XML 时，你**必须**遵守 Draw.io 的图层规则。所有被标记为背景的 `<mxCell>`（例如本图中的橙色、紫色、蓝色方框）**必须首先**在 `<root>` 标签内被定义。
# - **渲染前景**：所有其他元素（尤其是**文本节点**）**必须**在这些背景方框*之后*被定义。
# - **(规则总结：XML 中越早出现的 <mxCell>，在图层上越靠后。)

# 6) 复杂矢量图的强制重建 (CRITICAL: Re-build Complex Vectors)
# - 【JSON 描述草稿】中的 `relationships_extended` 字段（尤其是 `type: "describes_structure"` 和 `type: "describes_subgraph"`）是“建筑师” (Prompt 1) 提供的、用于重建复杂矢量图（如坐标系、神经网络、**节点-链接图**）的**关键重建指令**。
# - 当你看到这些条目时，你必须使用 `note` 中的描述，并**结合【原始图片】**，来*从头开始* (from scratch) 使用 `<mxCell>` 基元（方框、圆形、文本、线条）**重新绘制** (re-draw) 这些复杂的内部结构。
# - **严厉禁止**在这一步对这些复杂结构使用文本占位符来“摆烂”或跳过。

#   * **子图 (Node-Link) 重建 (施工指令)**：
#     * 1. **识别子图指令**：如果 `type` 是 `describes_subgraph` 且 `note` 描述了一个“节点-链接图”（例如本图中的“3x3x3 全连接网络”）。
#     * 2. **循环创建节点**：你**必须**使用 `note` 中的描述（例如：“第一层有 3 个节点”），循环创建**所有**单独的节点（例如，使用 `shape=ellipse` 的 `<mxCell>`）。
#     * 3. **循环创建边**：你**必须**使用 `note` 中的描述（例如：“全连接”），循环创建**所有**内部连接线（作为 `<mxCell edge="1">`）。
#     * 4. **禁止偷懒 (CRITICAL)**：**严厉禁止**将此 `describes_subgraph` 组件画成一个单一的、空白的占位符方框或省略其内部连线。这被视为“摆烂”并且是严重的失败。

#   * **矩阵网格 (Matrix Grids) - (施工指令)**：
#     * 1. **识别网格指令**：如果 `type` 是 `describes_structure` 且 `note` 描述了一个“网格”(grid) 或“三角矩阵”(triangular matrix)。
#     * 2. **强制使用 Table 形状 (CRITICAL)**：你**必须**使用 Draw.io 的 `shape=table` 作为父容器、`shape=tableRow` 作为行、以及 `shape=tableCell` 作为单元格来*真实地*重建这个网格。
#     * 3. **禁止手动组装 (CRITICAL FAILURE)**：**严厉禁止**通过创建大量单独的 `<mxCell vertex="1">` 方块并手动排列它们来“伪造”一个网格。这是一种“摆烂”行为，会导致箭头连接和布局彻底失败。你**必须**使用 `shape=table` 结构。
#     * 4. **单元格着色**：你**必须**读取 `note` 中的描述（例如：“下三角区域为 '0-valued' (浅灰)”），并为**每一个** `<mxCell type="tableCell">` 赋予正确的 `fillColor`，以 100% 复现原始图片中的模式。

# 7) 装饰/特殊元素处理 (JSON 辅助, 图片核查)
# - **语义图标 (❄️, 🔥)**：
#   - (此规则不变) 像 ❄️ 和 🔥 这样的图标是**关键的语义信息**...
#   - 你**必须**复现它们。
#   - 最好的方法是创建一个小的、独立的**文本节点** `<mxCell>` (使用 emoji 字符 ❄️ 或 🔥 作为 `value`)。
#   - 将这个文本节点放置在它所属组件的一个角落上（**根据【原始图片】确认位置**）。
# - **非矢量图形 (截图等)**：
#   - 如果【JSON 描述草稿】的 `non_diagram_elements` 提到了 `category: "screenshot"`，并且**你能在【原始图片】中确认**该截图的存在：
#   - 你**必须**在图表对应位置创建一个**高亮（黄色）的、带虚线边框的**矩形节点 `<mxCell>`。
#   - 将 JSON 中的描述（如 "移动UI截图"）作为这个矩形节点的 `value`。

# 8) 内部验证流程 (自检；不输出此清单)
# 1.  **解析草稿 (Parse Draft)**：
#     * 读取【JSON 描述草稿】的 `components`, `arrows`, `styles`, `containment_hierarchy`。
#     * 形成一个“草稿计划”。
# 2.  **视觉核查与修正 (Visual Verification & Correction)**：
#     * **节点与容器核查**：看着【原始图片】，检查“草稿计划”中的*每一个*组件（包括JSON `containment_hierarchy` 中暗示的**容器**）是否都在图上？图上是否有多余的组件？**（以图片为准修正清单）**
#     * **边核查 (关键)**：看着【原始图片】，**重新独立计数**所有的箭头。
#     * **冲突修正**：“草稿计划”中的箭头数量/拓扑是否与【原始图片】匹配？
#     * **容器连接核查 (重点)**：**仔细核对【原始图片】！JSON 草稿可能遗漏了指向“容器”边界的箭头（例如 'Opinion' 箭头）。你必须独立重新检查，并补上任何缺失的“节点到容器”的边。**
# 3.  **规划布局 (Layout)**：
#     * 看着【原始图片】，在 10x10 网格上为**修正后清单**中的所有节点和**容器**规划 `x, y, width, height` 坐标。
# 4.  **创建节点与容器 (Nodes & Containers)**：
#     * **首先 (Z-Order 关键)**：遍历清单，**优先创建所有**被标记为 `is_background: true` 的**背景** `<mxCell>`。
#     * **然后**：再次遍历清单，创建所有**前景** `<mxCell>` 节点（如文本、箭头标签等），并将它们的 `parent` 设置为 1 或其容器 ID。
#     * **(此顺序确保背景在 XML 中首先出现，因此位于图层底部。) **
#     * (规则5) 创建所有语义图标 (❄️, 🔥) 和非矢量占位符（截图）。
# 5.  **创建边 (Edges)**：
#     * 遍历**修正后**的边清单（**确保包含了你补上的'节点到容器'的边**）。
#     * 确保创建了与【原始图片】**数量完全匹配**的 `<mxCell>` 边。
#     * **样式核查**：再次核对图片，应用正确的样式。
#     * **边标签**：添加 JSON 中提供的 `label`。
# 6.  **组装与验证 (Assemble & Validate)**：
#     - 组装 XML。
#     - **运行最终验证检查**:
#       - 1. 格式是否良好？
#       - 2. `id` 是否都唯一？
#       - 3. 是否有悬挂的 `source/target` 引用？
#       - 4. (XML 转义检查): ...
#       - 5. (父子关系检查 - CRITICAL): ...
#       - 6. **(子图施工核查 - CRITICAL):** 我是否检查了 JSON 中的 `relationships_extended`？如果我找到了 `type: "describes_subgraph"` 的指令（比如“神经网络”），我是否**真的**在我的 XML 草稿中为它创建了所有的*内部节点*和*内部边*？我是否只是“摆烂”画了几个节点而省略了边？**必须**在输出前返回并补全所有缺失的内部连线。
# 7.  **最后，仅输出 XML 内容。**
# """

from typing import Optional, Dict, Any
import json


def get_classification_prompt(context_text: Optional[str] = None) -> str:
    """Get prompt for diagram classification.

    保持输出 JSON 结构与本项目一致：
    {"is_candidate": bool, "score": float, "diagram_type": str|null, "reason": str}
    规则与判定标准参考 academic-figure-dataset 中的 flowchart_classifier_prompt。
    """
    # 中文说明（仅供阅读，不会发送给模型）：
    # - 这是一个“学术场景流程图/架构图筛选器”的 Prompt。
    # - 判定是否是可用 Draw.io/XML 复现的流程图/架构图：
    #   - 必须由矢量形状（矩形/椭圆/菱形/文本/连线）构成；
    #   - 必须有多个功能模块 + 清晰箭头/连线表示数据流或控制流；
    #   - 若包含截图/照片/统计图/卡通人物/emoji，则一律视为非候选图。
    # - 与 academic-figure-dataset 不同的是，这里最终仍需要输出本项目使用的四个字段：
    #   is_candidate / score / diagram_type / reason。
    prompt = r"""You are a specialized, academic-focused multimodal classifier.
Your task is to analyze the provided image and decide whether it is an "architecture diagram" or "flowchart" in a scientific/engineering context, and whether it is suitable for faithful Draw.io/XML reconstruction.

--- Primary Gate (MANDATORY) ---
XML-reproducibility is REQUIRED. If the diagram cannot be faithfully reconstructed as a Draw.io/XML vector diagram using ONLY standard primitives (rectangles, ellipses, diamonds, text labels, connectors), you MUST treat it as NOT a candidate.
Figurative-character ban: If the image contains any figurative or anthropomorphic icons or illustrations (e.g., human heads/faces, people silhouettes, robots, mascots, emojis, cartoon characters), classify it as NOT a candidate regardless of vector nature.

--- Core Judgment Criterion ---
Does the image use discrete "functional modules" (boxes/nodes) and explicit "connecting arrows/lines" to describe a system, model, data flow, control flow, or algorithmic steps?

--- Disqualifiers → Treat as NOT a candidate if ANY apply ---
1) Experimental/data visualizations: line/bar/histogram/scatter/box/violin/radar charts, heatmaps, pie charts, word clouds, spectrograms, saliency maps, segmentation masks.
2) Screenshots or raster UIs: app/web/IDE/terminal screenshots, dashboards, settings pages, code editors.
3) Photographs or camera-captured content: people/objects/scenes, microscopy/medical images, camera photos of whiteboards/paper/PDF scans.
4) Text-first or table-first images: long text paragraphs, code blocks, or pure tables as the main content.
5) Collages/composites where plots/photos occupy substantial area, or where vector nodes/edges are not the dominant semantic carriers.
6) Overlays on raster backgrounds: flow arrows or labels drawn on top of screenshots/photos/plots; any background bitmap layer present.
7) Infographic/cartoonish or decorative illustrations that are not technical system/process diagrams.
8) Any figurative/anthropomorphic icons or characters (human/animal/robot faces or bodies, mascots, emojis), including when used as node shapes.

--- Positive Requirements → Treat as a candidate ONLY if ALL hold ---
a) Contains ≥2 discrete modules/components (clearly bounded shapes) and ≥1 explicit connector (arrow/line) between them.
b) Connectors represent relationships/flows between modules (axes, gridlines, table borders do NOT count).
c) Topic is a technical system/process in research, engineering, or software development.
d) XML-reproducibility checklist (all must pass):
   - All essential elements are expressible as vector shapes or text (no photo/texture-dependent semantics).
   - No raster/photo/screenshot layer is required to convey meaning.
   - The diagram would remain complete and faithful if recreated solely with Draw.io primitives and connectors.
e) Non-figurative shapes only: nodes are utilitarian geometric shapes or neutral technical icons (e.g., database cylinder), not human/robot/mascot/emoji illustrations.

--- Edge Case Guidance ---
- Neural network architectures, state machines, UML/ER/data-flow diagrams → usually candidates (if vector-only and connected).
- Gantt/timeline with time axes, Sankey/plots/heatmaps as primary content → NOT candidates.
- UI wireframes/mockups or any diagram overlaid on screenshots/photos → NOT candidates.
- Flowcharts that include human heads, faces, or robot/mascot icons as nodes → NOT candidates.

--- Output format (STRICT JSON) ---
Return ONLY a strict JSON object with the following fields:
{
  "is_candidate": true/false,
  "score": 0.0-1.0,
  "diagram_type": "flowchart|architecture|network|dataflow|other|null",
  "reason": "Brief explanation in English"
}

- "is_candidate" MUST be true if and only if, according to all rules above, the image is an architecture / flowchart style diagram that can be faithfully reconstructed in Draw.io/XML.
- "score" is your confidence that this image is such a candidate diagram.
- "diagram_type" is a coarse type label (e.g., "flowchart", "architecture", "network") or null if unclear.
- "reason" is a 1–2 sentence justification summarizing the key evidence (in English).
"""

    if context_text:
        # 将 PDF 图注/上下文追加到提示词末尾，作为 {context_text} 参考
        prompt += f"\nAdditional context (caption or surrounding text):\n{context_text}\n"

    return prompt


def get_description_prompt(context_text: Optional[str] = None) -> str:
    """Get prompt for **free-form** diagram description.

    这一版不再要求 LLM 输出 JSON，仅要求输出自然语言段落；
    后续代码会把整段文本塞进 `StructuredDescription.summary`，其它字段留空/默认，
    然后在生成 XML 时把这段文本作为语义上下文提供给下一个阶段。

    提示词的分析思路仍然可以参考 academic-figure-dataset 中的 image_descriptor_prompt_template：
    - 先用 {context_text} 把握整体意图与命名，再以图像视觉为准抽取结构；
    - 按优先级依次关注：核心组件与容器 → 流向与拓扑 → 关键文本 → 全局布局与配色 → 装饰元素。
    """
    prompt = r"""
You are an expert researcher specializing in computer vision and graph theory, skilled at deconstructing academic and engineering images.
Your task is to perform an in-depth, detailed analysis of the image's visual structure, based on the image itself and the provided context, following a **priority-first** order.

--- Context Policy ---
1.  **{context_text} Priority**: You must use the {context_text} (e.g., caption or abstract, which may be incomplete) to understand the image's **"overall purpose" (`overview`)** and **"core component naming" (`components.name`)**.
2.  **Visuals as Ground Truth**: All analyses regarding **"spatial layout" (`spatial_layout`)**, **"flow and topology" (`flow_and_topology`)**, and **"arrow styling" (`arrows`)** must be 100% strictly based on the visual evidence in the image itself.
3.  **Conflict Resolution**: If the context conflicts with the visual evidence (e.g., context says A->B, but the image shows A->C), **you must follow the visual evidence**.

--- Analysis Hierarchy & Rules (Prioritized) ---
You must focus your analysis in the following order of priority (P1 > P2 > P3):

### Priority 1: Flow Intent & Core Relations
(This is the most critical part for understanding "what the diagram is trying to say." You must self-correct at this step.)

* **1.1 Containers & Core Components**: (Highest Focus)
    * **Identify Containers**: **Immediately** identify all visual grouping boxes / background boxes (e.g., boxes surrounding multiple elements with different colors, dashed, or solid borders). **This is critical for tracing topology**. Record them as components in `components` and (if possible) rebuild the parent-child relationship in `containment_hierarchy`.
    * **Identify Core Components**: Identify all key vector modules and text blocks *inside* and *outside* the containers.
    * **Detailed Styles**: Immediately analyze the detailed visual styles of these core components and containers (for `component_styles`), e.g., `fillColor`, `strokeColor`, `shape`, `dashed=1` (for dashed lines).
    * **Identify Background Shapes**: (Focus) **Carefully check** and identify colored boxes that are clearly positioned *behind* other elements (especially text blocks), like the orange, purple, and blue boxes in this image. In `component_styles`, add a clear flag for them, such as `is_background: true` or `zIndex: -1`, to indicate they must be rendered at the bottom layer.
    * **Mandatory Text vs. Background Separation**:
       * Check the [Original Image]. If you see a **text label** (e.g., `X^T`, `H^-1_-q`, `L`) positioned *on top of* a **colored/gridded background shape** (e.g., a yellow grid, a blue grid).
       * You **must** identify them as **two separate components**:
       * 1. **The Text Label**: e.g., `{"name": "X^T", "description": "Transpose matrix"}`. In `component_styles`, it **must** be `fill="none"`, `stroke="none"` (no fill, no border).
       * 2. **The Background Shape**: e.g., `{"name": "X^T (Background Grid)", "description": "Yellow grid"}`. In `component_styles`, it **must** have the `fillColor`, `strokeColor`, and **must** be flagged as `is_background: true`.
       * In `spatial_layout.relative_positions`, you **must** add an entry, e.g., `"Text 'X^T' is positioned on top of 'X^T (Background Grid)'"`.
       * **(Critical Prohibition)**: **It is strictly forbidden** to merge the text and its background into *one* component (e.g., `{"name": "X^T", "fill": "#FFFFE0"}`). This will cause the XML to render incorrectly.
    * **Vectorization Mandate**: For any 'core component' that is composed of vector graphics in the original image (regardless of complexity, such as molecular structure diagrams, tree diagrams, neural network architectures, or complex coordinate systems), it is strictly forbidden to replace the original vector graphic with a mere text description. Even if the component is highly complex and difficult to describe, you must make every effort to detail its main constituent elements and provide layout clues.
    * **Structured Sub-graph Description (Graph-in-Graph)**: (Focus) When a 'core component' (e.g., "Input Graph (A)") *internally* contains a vector graph (like a node-link diagram), you **must** use `type: "describes_subgraph"` in the `relationships_extended` field to **structurally** describe this sub-graph. The `note` field must contain a textual description of the sub-graph's **node list (nodes)** and **edge list (edges)**. Example: `"note": "Subgraph contains: [nodes: 5 blue circles], [edges: 7 black solid lines], [topology: node 1 connects 2, 1 connects 3... (if legible)]"`. **You must not** simply say "contains a graph" without providing its structure.
    * **Identify Brackets & Braces**: (Focus) **Immediately** scan for all standalone grouping parentheses `()`, square brackets `[]`, or curly braces `{}`.
       * 1. **Treat as Component**: You **must** treat these braces themselves as a **core component** (e.g., `name: "Grouping Brace {"`).
       * 2. **Describe Style**: In `component_styles`, record their style, especially `shape` (e.g., `shape: "curlyBrace"` or `shape: "bracket"`).
       * 3. **Describe Grouping**: In `relationships_extended`, use the new `type: "groups"` to explicitly describe which other components it "groups" or "spans".
    * **Internal Matrix Patterns**: (Focus) When a component is a matrix (e.g., `H^-1`, `L`, `M_U`) and displays **internal structure** (e.g., a grid of cells, triangular patterns, block-coloring, like a mix of '0-valued' and '1-valued' cells), you **must**:
       * 1. Use `type: "describes_structure"` in the `relationships_extended` field.
       * 2. **Detail this pattern** in the `note` field. Example: `"note": "An n x n grid. The lower-triangular area is marked '0-valued' (light gray), and the diagonal is '1-valued' (dark gray)."`
       * 3. **(Critical Prohibition)** **It is strictly forbidden** to put this structural information *only* in the `components.description` field. The `description` field is for high-level function (e.g., "The inverse of..."), while `relationships_extended` **must** be used for *visual re-build instructions*.
    * **Identify Core Components**: Identify all key vector modules and text blocks *inside* and *outside* the containers.
    * **ID/Name Uniqueness (Critical)**: In the `components` list, you **must** ensure that the `name` field for *every single* component is **unique**. If two components are visually distinct (e.g., two different text labels in a legend), they must never share the same `name`. For example, they should be named "legend_text_1" and "legend_text_2" or "legend_result" and "legend_telemetry", not "legend_text" for both.

* **1.2 Flow, Topology & Arrows**: (Highest Focus)
    * **Trace & Topology**: (Highest Focus) You **must** trace *every single independent* arrow path from a `from` to a `to`.
        * **Splitting & Shared Trunks (Critical Upgrade)**:
          While A->B and A->C are logically distinct arrows, if they visually **share a path segment** (e.g., a single line exiting A that forks later into branches for B and C), you must:
          1. Assign the same `visual_group_id` (e.g., "branch_group_1") to both distinct arrow objects in `arrows.details`.
          2. Explicitly describe this branching structure in the `path_description`. Example: "Shares a vertical trunk with the A->C arrow; forks left at the Y-axis center to connect to B."
          3. **Strictly prohibit** describing these as two parallel, independent lines originating from the source, unless the image explicitly draws them that way.
        * **Merging**: (Critical) Likewise, if `A` and `B` both point to `C`, this is **two independent arrows**: `{"from": "A", "to": "C", ...}` and `{"from": "B", "to": "C", ...}`.
        * **Bidirectional**: (Critical) Carefully check if arrows are *uni-directional* (`A -> B`) or *bi-directional* (`A <-> B`). **If a connection is bidirectional**, you **must** mark it in `arrows.details` with `is_bidirectional: true` and `heads: "double arrow"`.
    * **Special Connections (Critical Point)**:
      * **Braces & Tails**: Carefully check what the *tail* (source) of the arrow connects to. If it connects to a brace (like `{`) or has a special T-bar connector, you **must** record this in the `arrows.details.tails` field and point the `from` field to the correct brace component (e.g., `from: "Grouping Brace {"`).
      * **Detailed Styling & Routing**:
          * **Node-to-Node**: Trace arrows from one shape to another.
          * **Node-to-Container**: (Focus) **Carefully check for arrows that start from a node and terminate on the *boundary* of a "container"** (e.g., the 'Opinion' arrow in the original image pointing to the yellow box). You **must** record the container's name (or ID) in the `arrows.details.to` field.
          * **Node-to-Brace (New Focus)**: Carefully check if any arrows (especially arrow tails) **connect directly to the brace or bracket symbol itself**. If so, you **must** use that brace's component name in the `arrows.details` `from` or `to` field (e.g., `from: "Grouping Brace {"`).
          * **Routing (Critical)**: Explicitly describe the arrow's path style. **Must** choose from:
            * `routing: "straight"`
            * `routing: "orthogonal"` (For draw.io's `edgeStyle=orthogonalEdgeStyle`)
            * `routing: "curved"`
    * **Arrowhead Styling (New Focus)**: Describe the visual style of the arrow *head* (`endArrow`) and *tail* (`startArrow`).
        * `heads: "single arrow"` (Default, e.g., `endArrow=classic`)
        * `heads: "double arrow"` (Bidirectional, e.g., `endArrow=classic;startArrow=classic`)
        * `heads: "no head"` (Line only, e.g., `endArrow=none;`)
        * `tails: "none" | "T-bar" | "circle"` (Describe special tail styles)

    * **Path Interactions & Crossings (critical new field)**  
      You must check whether each arrow, on its path from source to target, has any **spatial interactions** with other elements.  
      In `arrows.details`, add an `interacts_with` list:  
      - Format: `[{"component": "Intermediate module B", "type": "passes_through" | "passes_behind" | "jumps_over" | "touches_boundary"}]`  
      - **Passes Through**: The line passes directly through the interior of that component (usually meaning the component has a transparent background or the line is on the top layer).  
      - **Passes Behind**: The line is occluded by that component (dashed or interrupted).  
      - **Jumps Over**: The line draws a “bridge/arch” to cross another line.  
      - **Touches Boundary**: The line only touches the boundary of the component (for example, the arrow tail connects to the left edge of the module).

    * **Arrow Style Strictness**: Your task is to *describe* the visually existing arrows. **It is strictly forbidden to *invent* or *replace* styles**. If the arrow in the original image is `thin`, `black`, and `dashed`, your JSON description **must** reflect `style="dashed"`, `color="Black (#000000)"`, `thickness="thin"`. **You must never** replace it with `shape=flexArrow` (block arrow) or any other style not present in the original (like the blue thick arrows in this example).
    * **Geometric & Coordinate System Description**: (Focus) If the image contains **geometric shapes, coordinate systems (e.g., 3D axes), or points with explicit numerical labels**, you must:
        * Describe their constituent elements in detail within `components.description` or `relationships_extended` (e.g., "X, Y, Z axes," "radial vector for spherical coordinates").
        * Describe their connections or indicative relationships in `arrows.details.notes` or `relationships_extended`.
        * **For text-based coordinates or numerical values** (e.g., `(-0.01, -0.77, 1.26)`), capture them as key text in `components.name` and ensure their layout position can be reproduced by the XML generator.
   * **Connection Ports**: To eliminate chaotic layouts, you **must** describe the **precise relative position** where the arrow attaches to its source and target shapes.
        * Add a **new object** named `connection_ports` inside the `arrows.details` object.
        * This object must contain two keys: `source_port` and `target_port`.
        * `source_port`: Describes where the arrow *exits* the `from` component.
        * `target_port`: Describes where the arrow *enters* the `to` component.
        * **Value Examples**: Use descriptive terms like `"middle_left"`, `"middle_right"`, `"top_center"`, `"bottom_center"`, `"top_left_corner"`, `"bottom_right_corner"`, etc.
        * **JSON Example**: `..., "connection_ports": {"source_port": "middle_right", "target_port": "middle_left"}`
  * **Detailed Spatial Relations (Path Description)**: (Focus) Upgrade the `notes` field to `path_description`.
        * (Bad Example - Semantic): `"notes": "Represents Q1 being sent..."`
        * (Good Example - Visual): `"path_description": "A straight horizontal line from the right side of rank1 to the left side of rank0."`
        * (Good Example - Orthogonal): `"path_description": "Exits the bottom of rank0, goes down, turns 90-degrees right, then goes down again to enter the top of rank3."`
  * **Capture All Structural Lines (Critical New Rule)**: You must not only trace arrows representing "flow," but you **must** also capture all lines used to indicate "relationships" or "grouping."
        * For example, the **vertical dotted lines** connecting `x_0`, `x_i'`, and `x_N-1` are part of a "batch" relationship.
        * You **must** describe these lines as separate entries in `arrows.details`.
        * **Example (for vertical dotted lines)**:
          `{"from": "Input Sample x_0", "to": "Backdoored Input Sample x_i'", "direction": "Top->Bottom", "color": "Gray (#808080)", "style": "dotted", "thickness": "thin", "heads": "no head", ... "path_description": "Vertical dotted line connecting x_0 and x_i' in the batch."}`
          `{"from": "Backdoored Input Sample x_i'", "to": "Input Sample x_N-1", "direction": "Top->Bottom", "color": "Gray (#808080)", "style": "dotted", "thickness": "thin", "heads": "no head", ... "path_description": "Vertical dotted line connecting x_i' and x_N-1 in the batch."}`

* **1.3 Key Text**:
    * Identify and transcribe **all text** on flow components and arrow labels (for `arrows.details.label` and `components.name`).
    * **Capture All Detailed Text**: In addition to text on flow components and arrow labels, you must also identify and transcribe all **small but semantically meaningful text within graphics**, such as: numerical values, mathematical expressions, coordinate points, and specific labels (e.g., "Atom 1"). These texts are crucial components for vectorizing the graphics.

* **1.4 Raster Images (formerly 'Non-Vector Graphics')**: (Scope Strictly Narrowed) This rule applies **only** to **true raster images**, such as:
    * **Photos**: Real-world photographs of people, objects, or scenery.
    * **User Interface Screenshots**: Screenshots of software, apps, or websites.
* (Focus) If an element is a *schematic*, *diagram*, *chart*, or *sketch* (no matter how complex, e.g., a molecular diagram or even a sketch-style *flowchart*), it does **not** belong here and **must** be forcibly deconstructed as vectors under P1.1 and P1.2.

* **1.5 Files & Artifacts**:
    * Identify documents, datasets, code files, etc., involved in the data flow (for `files_and_artifacts`).

### Priority 2: Global Layout & Secondary Styles
(This is about the global and secondary details of "how the diagram is drawn".)
* **Global Spatial Layout**: Describe the **overall** layout (left-to-right, top-to-bottom), **global alignment**, and equidistant distribution (for `spatial_layout`).
* **Secondary Component Styling**: Analyze the styles of secondary components not covered in P1 (e.g., background boxes).
* **Color & Typography**: Extract the **global** color palette; identify semantically meaningful fonts (e.g., monospace/code) (for `color_palette`, `typography`).
* **Other Structures**: Identify structural patterns (repetition, symmetry), legends, and multi-panel layouts (for `structural_patterns`, `legend_and_symbols`, `panel_layout`).

### Priority 3: Decorative Elements
(These are the last elements to consider, which do not affect the core flow intent.)
* **Decorative Content**: Identify and count Emojis, stickers, mascots, and decorative pictograms (non-flow icons) (for `non_diagram_elements`).

--- Preparatory Thinking Steps (Layered Self-Correction) ---
Before generating the final JSON, you must execute the following steps in your "mind" in order:

1.  **Think (P1 - Flow Intent)**:
    * Combine {context_text} and the image to analyze all P1 rules (Core Components, **Detailed Styles**, **Containment**, **Detailed Arrow Analysis**, Key Text, Non-Vector Screenshots).
    * Form a draft of the "flow intent."

2.  **Correct (P1 - Flow Intent Review)**:
    * **Self-Correction (Double-Check)**:
        * "Did I accurately understand the {context_text}?"
        * "Is the P1 flow topology complete?"
        * "Are the core components' **color, containment** analyzed correctly?"
        * "**Arrow Count (Critical Self-Check)**: I visually count **18 arrows** in my 'mind' (including all labeled, unlabeled, 'permute', and 'all2all' arrows). Is the final length of my `arrows.details` list also 18? If the count does not match, I must re-analyze the image to find all missing arrows."
        * "Are the arrows' **routing (curved/straight/orthogonal), style (dashed/solid), splitting, and spatial relations in `notes` (e.g., passes through module, touches boundary, relation to text/arrows)** all described in detail?"
        * "Did I miss any critical **non-vector screenshots**?"
        * "Is the text transcribed accurately?"
    * Revise the P1 draft until it is 100% accurate to the flow.

3.  **Think (P2 - Global Layout)**:
    * Based on the P1 results, analyze P2 rules (global layout, secondary styles, global palette).
    * Form a draft of the "vector implementation."

4.  **Correct (P2 - Global Layout Review)**:
    * **Self-Correction**: "Is the P2 global layout description (e.g., alignment) consistent with the image?"
    * Revise the P2 draft.

5.  **Think (P3 - Decorative Elements)**:
    * Analyze P3 rules (Emojis, stickers, etc.).

6.  **Final Generation (Combine & Format)**:
    * Combine and populate all P1, P2, and P3 findings into the **single, complete** JSON structure specified in the `--- Output Requirements ---` below.

--- Output Requirements (Strictly Follow) ---
1. Output ONLY a strict JSON object.
2. It is strictly forbidden to include any explanations, comments, or text outside the JSON; do not use Markdown code fences (no ```json ... ```), language tags, or any wrapping text.
3. The JSON must contain the following fields (Schema has been updated):
   - "image_type": (String) The highest-level classification of the image.
   - "overview": (String) A 1-2 sentence summary of the image's function or purpose.
   - "components": (List of Objects) Identify, count, and describe key components.
     - Format: [{"name": "Component Name", "count": 1, "description": "Brief functional description of the component"}]
   - "spatial_layout": (Object) Describe spatial, projection, and metric relations.
     - "primary_layout": "Overall layout description(e.g., Left-to-right flow, vertically stacked)"
     - "relative_positions": ["Component A is above Component B", "Component C is to the left of Component D"]
     - "alignment": ["Component A, B, C are vertically aligned"]
   - "flow_and_topology": (Object) Describe flow and topological structures. (Summary-level analysis from P1.2 like "convergence", "loop", "multi-edge" should go in the `structures` list here)
     - "primary_flow": "Describes the main A->B->C flow"
     - "structures": ["Topology: Convergence. Outputs from 'Data Source A' and 'Data Source B' merge into 'Processing Module C'.", "Topology: Feedback Loop. A bidirectional arrow exists between 'Module C' and 'Module D'.", "Topology: Multi-Edge. A solid line and a dashed line connect 'Module A' and 'Module B' simultaneously."]
   - "structural_patterns": (List of Strings) Describe repeating, symmetric, etc., patterns.
     - Format: ["Pattern Description 1 (e.g., The 'Agent <-> Checker' pairing pattern repeats 3 times)"]
   - "non_diagram_elements": (List of Objects, optional) List screenshots, photos, cartoons, emojis, stickers, infographics, etc. (This field will be populated first by screenshots/photos from P1.4, then by Emojis from P3)
     - Format: [{"category": "screenshot|photo|cartoon|emoji|infographic|decorative|other", "count": 2, "examples": ["Mobile UI screenshot", "Emoji in label"]}]
   - "arrows": (Object, optional) Summary of connection styles and representative examples. (This field is now populated by P1.2 analysis, **note the `routing` and `notes` fields**)
       - "summary": {"total": 4, "bidirectional": 1, "styles": ["solid green", "dashed gray"], "multi_edge_pairs": 1}
       - "details": [
            {"from": "Module A", "to": "Module B", "visual_group_id": "branch_group_1", "direction": "Left->Right", "color": "Green (#00A000)", "style": "solid", "thickness": "medium", "heads": "single arrow", "tails": "none", "is_bidirectional": false, "label": "forward pass", "routing": "straight", "connection_ports": {"source_port": "middle_right", "target_port": "middle_left"}, "interacts_with": [{"component": "Background Layer 1", "type": "passes_over"}], "path_description": "A straight horizontal line that touches the boundary of 'Module B'."},
            {"from": "Module A", "to": "Module C", "visual_group_id": "branch_group_1", "direction": "Bidirectional", "color": "Gray (#808080)", "style": "dashed", "thickness": "thin", "heads": "double arrow", "tails": "none", "is_bidirectional": true, "label": null, "routing": "curved", "connection_ports": {"source_port": "top_center", "target_port": "top_center"}, "interacts_with": [{"component": "Background Layer 1", "type": "passes_over"}], "path_description": "A curved line that passes through 'Module D'."},
            {"from": "Module F", "to": "Module G", "visual_group_id": "branch_group_1", "direction": "Top->Bottom", "color": "Black (#000000)", "style": "solid", "thickness": "thin", "heads": "single arrow", "tails": "none", "is_bidirectional": false, "label": null, "routing": "orthogonal", "connection_ports": {"source_port": "bottom_center", "target_port": "top_center"}, "interacts_with": [{"component": "Background Layer 1", "type": "passes_over"}], "path_description": "This is the first path of the splitting arrow, routed orthogonally."},
            {"from": "Module X", "to": "Module Y", "visual_group_id": "branch_group_1", "direction": "Top->Bottom", "color": "Gray (#808080)", "style": "dotted", "thickness": "thin", "heads": "no head", "tails": "none", "is_bidirectional": false, "label": null, "routing": "straight", "connection_ports": {"source_port": "bottom_center", "target_port": "top_center"}, "interacts_with": [{"component": "Background Layer 1", "type": "passes_over"}], "path_description": "A structural dotted line, indicating a batch relationship."}
          ]
   - "color_palette": (Object, optional) Global color palette summary.
     - "colors": [{"name": "Blue", "hex": "#3A7BD5", "proportion": 0.35}]
   - "component_styles": (List, optional) Component-level style summary. (This field is now populated by P1.1 analysis)
     - Example: [{"component": "Module A", "shape": "rounded rectangle|ellipse|curlyBrace|bracket", "fill": "#dae8fc", "stroke": "#6c8ebf", "text": "#000000", "radius": 10, "icon": "database|cloud|gear|null", "shadow": false, "is_background": false}]
   - "containment_hierarchy": (Object, optional) Container/sub-element tree. (This field is now populated by P1.1 analysis)
     - "root": {"name": "Canvas", "children": [{"name": "Group 1", "children": ["Module A", "Module B"]}]}
   - "relationships_extended": (List, optional) Relations beyond edges, or descriptions of complex internal component structure.
     - Example: [
         {"type": "contains|adjacent|overlay|references|reads_from|writes_to|calls|produces|layout_detail|groups", "source": "Module A", ...},
         {"type": "describes_structure", "source": "Component B", ... "note": "Component contains a 3D coordinate system with X, Y, Z axes."},
         {"type": "layout_detail", "source": "GPT Block #1", ... "note": "Internal sub-modules are very compact..."},
         {"type": "describes_subgraph", "source": "Component C", ... "note": "Subgraph contains: [nodes: 5 nodes]..."},
         {"type": "groups", "source": "Grouping Brace {", "target": null, "evidence": "visual", "note": "This brace visually spans [Module A, Module B]."},
         {"type": "describes_subgraph", "source": "Component C", ... "note": "Subgraph contains: [nodes: 5 nodes]..."},
         {"type": "groups", "source": "Grouping Brace {", ... "note": "This brace visually spans [Module A, Module B]."},
         {"type": "describes_structure", "source": "Matrix L", "target": null, "evidence": "visual", "note": "n x n grid. Lower-triangular area is '0-valued' (light gray)."}
       ]
   - "files_and_artifacts": (List, optional) Detected files/documents and their associations.
     - Example: [{"name": "report.pdf", "kind": "document|dataset|code|config|log", "linked_to": ["Module C"], "relation": "produces"}]
   - "panel_layout": (Object, optional) Multi-panel description.
     - {"panels": 1, "layout": "single|grid|row|column", "labels": []}
   - "legend_and_symbols": (Object, optional) Legend information.
     - {"has_legend": false, "items": []}
   - "typography": (Object, optional) Important typographic info.
     - {"monospace_used": false, "bold_italic_used": false}
   - "ports_and_edge_semantics": (Object, optional) Port and edge semantics.
     - {"has_ports": false, "edge_types": ["data"]}
   - "background_layers": (Object, optional) Background/layering info.
     - {"has_raster_background": false, "z_order_notes": null}

4. Handling of Empty/Optional Fields:
   - For all fields marked as `(optional)` in the schema:
   - If no corresponding content is found in the image, you **must** retain the key in the JSON.
   - If the field's expected value is a **List**, output an **empty list `[]`**.
   - If the field's expected value is an **Object**, output `null` or an object with its default empty state (e.g., `{"has_legend": false, "items": []}`).
   - This ensures the output JSON always has a consistent top-level structure.

--- Final Instructions (Strictly Follow) ---
1.  Analyze the image provided.
2.  Your sole output must be and only be a JSON object.
3.  It is strictly forbidden to include any text, comments, explanations, or Markdown markup (like ```json ... ```) before or after the JSON.

Please analyze the image based on the above rules and context, and output ONLY the JSON:
"""

    if context_text:
        # 将组装好的上下文作为附加说明加入 Prompt 末尾，帮助模型理解图的语义场景
        prompt += f"\nAdditional textual context (caption / label / surrounding text):\n{context_text}\n"

    return prompt


def get_diagram_prompt(
    description: Optional[Dict[str, Any]] = None,
    context_text: Optional[str] = None
) -> str:
    """Get prompt for draw.io XML generation.

    这里参考 academic-figure-dataset 中的 image_to_xml_prompt_template：
    - 输入包括：原始图片 + 可选的结构化 JSON 描述（description 参数）；
    - 图片是事实来源（ground truth），JSON 是高质量草稿；
    - 输出必须是单一、可解析的 Draw.io/mxGraph XML，不要返回解释文本或 Markdown 代码块。
    """
    # 中文摘要（不会发送给模型）：
    # - 目标：根据图片 + （可选的）结构化描述，生成完整的 Draw.io XML；
    # - 关键约束：
    #   * 所有可见元素都是 <mxCell>，带唯一 id 与 <mxGeometry>；
    #   * edge="1" 的边单元不能自闭合，必须有内部 <mxGeometry>；
    #   * 字符串要进行 XML 转义（< / > / &）；
    #   * 不要输出 ```xml``` 之类的代码围栏，只输出原始 XML；
    #   * 可以利用 description 中的 components / relationships / styles 作为布局和样式的“提示”。
    base_prompt = r"""
You are an extremely precise and meticulous Draw.io diagram generation expert.
Your task is to generate a single, complete, syntactically correct, and parsable Draw.io XML file based on a [JSON Description Draft] and the [Original Image].

--- Core Inputs ---

[JSON Description Draft]:
(This is a high-quality draft used to provide “hints” for component names, styles, and basic topology)
{json_description}

[Original Image]:
(This is the only “source of truth.” You must use it for final visual verification)

--- Core Rules (Image First) ---

1) Core Task (Image as primary, JSON as auxiliary)
- **Image is Ground Truth**: You **must** treat the [Original Image] as the highest standard for verifying all facts.
- **JSON is a High-Quality Draft**: You **should** first use the [JSON Description Draft] to quickly understand the diagram’s structure, component names (`components.name`), styles (`component_styles`), and labels (`arrows.label`).
- **Re-analyzing Text Context is Forbidden**: You no longer need to process `{context_text}`; all your information sources are limited to the [JSON Description Draft] and the [Original Image].

2) XML Output Specification (STRICT)
- **Single File**: The response must contain only the XML content; any explanatory text, prefixes/suffixes, or Markdown fences are strictly forbidden.
- **No Fences or Prefixes/Suffixes**: No Markdown code fences may appear (including ```xml, ```html, ``` and ~~~ forms).
- **Root & Structure**: Must start with `<mxfile ...>` and end with `</mxfile>`.
- **Canvas Settings**: `<mxGraphModel>` must include `grid="1" gridSize="10" guides="1" page="1"`...
- **Element Specification**:
    - All visible elements (shapes, lines, text) must be `<mxCell>`.
    - Every `<mxCell>` must include `id`, `value`, `style`, and `parent`, and contain an `<mxGeometry ... as=\"geometry\"/>`.
    - **id must be globally unique (CRITICAL)**: You **must** ensure that the `id` attribute on *every single* `<mxCell>` is **globally unique**. **You are ultimately responsible for this when generating `id`s from the [JSON Description Draft]’s `components.name` field**: If the JSON draft *accidentally* provides duplicate `name`s, you **must** proactively add suffixes when generating the XML (for example, `_1`, `_2`) or de-duplicate in other ways, to ensure that the XML output **never** contains duplicate `id`s.
    - No dangling `source/target` references; strings must be XML-escaped; no DOCTYPE/external entities or control characters; attribute quotes must be standard double quotes (").
    - **Attribute Syntax (CRITICAL ERROR CHECK)**: You must ensure *all* attributes on *every* `<mxCell>` tag follow the `name="value"` format. **Do not** produce attribute errors caused by missing quotes, such as `name="value name="value"`. `parent="1" vertex="1"` is correct. `parent="1 vertex="1"` is **incorrect** and causes an "attributes construct error".
    - **Edge Cell Syntax (CRITICAL)**: Self-closing edge tags (e.g., `<mxCell edge="1" ... />`) are **strictly forbidden**. Every `<mxCell>` with `edge="1"` **must** be a parent tag and **must** contain a `<mxGeometry relative="1" as="geometry" />` child tag inside it. `</mxCell>`. Omitting this child will cause the edge to not render and is a critical failure.

- **XML Escaping (CRITICAL ERROR CHECK)**:
  - This is the "not a drawing file" error you reported. You **must** follow this rule to prevent it.
  - When you use `style="...html=1;..."` for a cell, you are expected to use HTML tags (like `<b>` or `<font>`) in the `value` attribute for formatting.
  - **However**: The `value` attribute itself is still part of the XML. Therefore, these HTML tags **must be XML-escaped**.
  - **Rule (Angle Brackets)**: **All** `<` characters in the attribute value **must** be written as `&lt;`. All `>` characters **must** be written as `&gt;`. **This rule applies to all HTML tags, including `<b>`, `<font>`, `<i>`, `<u>`, and `<br>`.**
  - **Rule (Ampersand &)**: (New Focus) Likewise, all `&` characters (ampersand) in the attribute value **must** be written as `&amp;`.
  - **This is especially critical for escaping HTML entities (like &nbsp;)!**
  - **Example (Incorrect - causes parser failure):**
    `value="<b>Positive:</b> <font ...>red</font>"` (Error: Unescaped <)
    `value="Line 1<br>Line 2"` (Error: Unescaped <br> tag, this is the failure you saw)
    `value="Text &nbsp; spacing"` (Error: Unescaped & character)
    `value="Text &ampnbsp; spacing"` (Error: Malformed escape, missing semicolon, causes 'ampnbsp' error)
  - **Example (Correct - XML safe):**
    `value="&lt;b&gt;Positive:&lt;/b&gt; &lt;font color='#ff0000'&gt;red&lt;/font&gt;"`
    `value="Line 1&lt;br&gt;Line 2"` (Correct: <br> is properly escaped)
    `value="Text &amp;nbsp; spacing"` (Correct: &nbsp; is properly escaped as &amp;nbsp;)
  - **Examples (Correct – XML safe):**
    `value="&lt;b&gt;Positive:&lt;/b&gt; &lt;font color='#ff0000'&gt;red&lt;/font&gt;"`
    `value="Text &amp;nbsp; spacing"` (Correct: &nbsp; is properly escaped as &amp;nbsp;)

- **Strictly Forbid External Images (CRITICAL: No External Images)**
  - You must never use `style="...shape=image;..."` in your XML output together with external URLs (such as `image=https://...`) as a shortcut for vectorization.
  - This is a strictly prohibited form of “cheating.”

3) Layout & Style Guidelines (JSON-assisted)
- **Layout (Image-assisted)**:
  - **Alignment**: All `x`, `y`, `width`, and `height` values must be multiples of `gridSize` (10).
  - **Positioning**: Strictly refer to the visual layout of the [Original Image] when planning your grid layout (`x`, `y` coordinates).
  - **Spacing**: Maintain even spacing between components (e.g., 40–60 units). Avoid overlaps.
- **Shapes & Colors (JSON-assisted)**:
  - **Prioritize using** the style information provided in the [JSON Description Draft]’s `component_styles` field (e.g., `fillColor`, `strokeColor`, `shape`).
  - If the JSON does not provide styles, use the following professional, high-contrast default color scheme:
  - Recommended: component blue (`fillColor=#dae8fc;strokeColor=#6c8bf;`), flow green (`fillColor=#d5e8d4;strokeColor=#82b366;`).

- **Mandatory Rendering of Braces/Brackets (CRITICAL: Mandatory Brace/Bracket Rendering)**:
  - * The [JSON Description Draft] has **already correctly** identified components with `shape: "curlyBrace"` (curly brace) or `shape: "bracket"` (bracket) in its `component_styles` and `relationships_extended`.
  - * Your task is to **unconditionally execute** these instructions.
  - * You **must** use the corresponding Draw.io brace shapes in the `<mxCell>` `style` (for example, `style="shape=brace;..."` or `style="shape=bracket;..."`).
  - * You **must** use the [Original Image] to precisely adjust their `direction` (for example, `direction=south` to make the opening face downward, or `direction=west` to make the opening face right) and their `width`/`height`, so that they correctly cover the elements described in the JSON `relationships_extended`’s `note` field.
  - * **(Failure Checkpoint)**: You are **never allowed** to skip or ignore any `shape: "curlyBrace"` instruction. This is treated as a severe functional failure.

- **Connecting Edges (JSON-assisted, Image-verified)**:
    - **Topology**: You **must** create a *separate* `<mxCell edge="1">` for *every* object in the [JSON Description Draft]’s `arrows.details` list. If the JSON contains two records with `from: "A"`, then you must create two edges originating from A.
    - **Style (Solid vs Dashed)**: Prioritize using the `style` field from the JSON (for example, `style="dashed"`), and verify it against the [Original Image].
    - **Head/Tail Styling (Head/Tail Styling)** (critical): You **must** read the `heads` and `tails` fields in the JSON to construct the edge style:
      - If `is_bidirectional` is `true` or `heads` is `"double arrow"`, you **must** add `startArrow=classic;endArrow=classic;` to the style.
      - If `heads` is `"no head"`, you **must** add `endArrow=none;`.
      - If the `tails` field specifies a special style (for example, `"T-bar"`), you **must** add the corresponding `startArrow` style (for example, `startArrow=block;...`).
    - **Routing (Routing) (critical new rule)**:
      - Prioritize using the `routing` field. If it is `curved`, you **must** use an `<Array as="points">`.
      - If it is `orthogonal`, you **must** add `edgeStyle=orthogonalEdgeStyle;` to the `style`.
      - If it is `straight`, then you do not add any `edgeStyle`.
    - **Connection Ports (Connection Ports) (critical new rule)**:
      - You **must** read the `connection_ports` object (`source_port` and `target_port`).
      - Based on these values (for example, `"middle_right"` or `"top_center"`), you **must** compute and add the **precise Draw.io `exitX`, `exitY`, `entryX`, `entryY` anchors** in the `style` attribute of each `<mxCell edge="1">`.
      - **Examples (in style)**:
        - `...source_port: "middle_right"` corresponds to `exitX=1;exitY=0.5;`
        - `...target_port: "top_center"` corresponds to `entryX=0.5;entryY=0;`
        - `...source_port: "bottom_left_corner"` corresponds to `exitX=0;exitY=1;`
      - **This is the most important instruction for eliminating arrow confusion.**
    - **Edge Labels**: Prioritize using the text in the `label` field.
    - **Path Description (Auxiliary)**: Use the `path_description` field as an auxiliary clue to help you plan the `points` of orthogonal (`orthogonal`) or curved (`curved`) paths.
    - **Layout (Image-assisted)**:
      - **Alignment**: All `x`, `y`, `width`, `height` values must be multiples of `gridSize` (10).
      - **Canvas Centering (CRITICAL)**: **It is forbidden** to stack all elements in the top-left corner (e.g., `x=10, y=10`). You **must** use the `pageWidth` and `pageHeight` defined in the `<mxGraphModel>` (e.g., 1200x800) to plan your layout. You **must** calculate a 'global offset' for your drawing (e.g., a margin of `offsetX=100`, `offsetY=150`) and add this offset to all your components' `x` and `y` coordinates. This ensures the diagram is roughly centered and legible on the canvas.
      - **Reasonable Scaling**: Use the [Original Image]'s layout as a proportional guide. If the [JSON] draft has 3 components in a horizontal flow, do not cram them into 200px; spread them out over 600-800px of width to match the visual feel and proportions of the original image.
      - **Spacing**: (Keep this) Maintain even spacing between components (e.g., 40–60 units). Avoid overlaps.

4) CRITICAL: 1:1 Arrow Completeness Mandate (MANDATORY)
- The [JSON Description Draft]'s `arrows.details` list is the absolute source of truth for topology.
- You MUST iterate through this list and create exactly one (1) `<mxCell edge="1">` for every single object in that list.
- If the JSON `arrows.details` list contains 14 items, your final XML output MUST contain exactly 14 `<mxCell edge="1">` elements.
- If the JSON contains 4 items, your output must contain 4 edges.
- Generating an incomplete set of edges (e.g., 12 out of 14) is considered a critical failure and "laziness." You must generate all of them.

5) Z-Order (Layer) Management (CRITICAL)
- **Identify Backgrounds**: Check the [JSON Description Draft]’s `component_styles` for components with `is_background: true` or `zIndex: -1`.
- **Rendering Order (Critical)**: When generating the XML, you **must** follow Draw.io’s layering rules. All `<mxCell>` elements marked as background (for example, the orange, purple, and blue boxes in this figure) **must be defined first** inside the `<root>` tag.
- **Render Foreground**: All other elements (especially **text nodes**) **must** be defined *after* these background boxes.
- **(Rule Summary: The earlier an `<mxCell>` appears in the XML, the further back it is in the layer stack.)**

6) Mandatory Reconstruction of Complex Vector Diagrams (CRITICAL: Re-build Complex Vectors)
- The `relationships_extended` field in the [JSON Description Draft] (especially entries with `type: "describes_structure"` and `type: "describes_subgraph"`) contains the **key reconstruction instructions** provided by the “Architect” (Prompt 1) for rebuilding complex vector diagrams (such as coordinate systems, neural networks, and **node-link graphs**).
- When you see these entries, you must use the descriptions in `note` and **combine them with the [Original Image]** to *re-draw from scratch* these complex internal structures using `<mxCell>` primitives (rectangles, circles, text, lines).
- It is **strictly forbidden** at this step to use textual placeholders for these complex structures as a way to “slack off” or skip them.

  * **Subgraph (Node-Link) Re-build (Construction Instruction)**:
    * 1. **Identify Subgraph Instruction**: If the `type` is `describes_subgraph` and the `note` describes a "node-link graph" (e.g., the "3x3x3 fully connected network" in this image).
    * 2. **Loop-Create Nodes**: You **must** use the `note`'s description (e.g., "first layer has 3 nodes") to loop-create **all** individual nodes (e.g., as `<mxCell>` with `shape=ellipse`).
    * 3. **Loop-Create Edges**: You **must** use the `note`'s description (e.g., "fully connected") to loop-create **all** internal connecting lines (as `<mxCell edge="1">`).
    * 4. **No Shortcuts (CRITICAL)**: **It is strictly forbidden** to draw this `describes_subgraph` component as a single, blank placeholder box or to omit its internal connections. This is considered 'giving up' (摆烂) and is a critical failure.

  * **Matrix Grids (Construction Instruction)**:
    * 1. **Identify Grid Instruction**: If the `type` is `describes_structure` and the `note` describes a "grid" or "triangular matrix".
    * 2. **Mandatory Table Shape (CRITICAL)**: You **must** use Draw.io's `shape=table` as the parent container, `shape=tableRow` for rows, and `shape=tableCell` for cells to *actually* rebuild this grid.
    * 3. **Manual Assembly Forbidden (CRITICAL FAILURE)**: **It is strictly forbidden** to "fake" a grid by creating many separate `<mxCell vertex="1">` squares and arranging them manually. This is "giving up" (摆烂) and will cause catastrophic failure in arrow routing and layout. You **must** use the `shape=table` structure.
    * 4. **Cell-by-Cell Coloring**: You **must** read the `note`'s description (e.g., "Lower-triangular area is '0-valued' (light gray)") and apply the correct `fillColor` to **each individual** `<mxCell type="tableCell">` to 100% reproduce the pattern from the original image.

7) Decorative/Special Element Handling (JSON-assisted, Image-verified)
- **Semantic Icons (❄️, 🔥)**:
  - (This rule remains unchanged.) Icons like ❄️ and 🔥 are **key semantic information**...
  - You **must** reproduce them.
  - The best approach is to create a small, independent **text node** `<mxCell>` (using the emoji character ❄️ or 🔥 as its `value`).
  - Place this text node at a corner of its associated component (**confirm the exact position using the [Original Image]**).
- **Non-vector Graphics (Screenshots, etc.)**:
  - If the [JSON Description Draft]’s `non_diagram_elements` mentions `category: "screenshot"`, and you can **confirm the presence** of that screenshot in the [Original Image]:
  - You **must** create a **highlighted (yellow), dashed-border** rectangular `<mxCell>` at the corresponding position in the diagram.
  - Use the description from the JSON (such as “mobile UI screenshot”) as the `value` of this rectangular node.

8) Internal Verification Workflow (Self-check; Do Not Output This Checklist)
1.  **Parse the Draft (Parse Draft)**:
    * Read the [JSON Description Draft]’s `components`, `arrows`, `styles`, and `containment_hierarchy`.
    * Form a “draft plan”.
2.  **Visual Verification & Correction (Visual Verification & Correction)**:
    * **Node & Container Check**: While looking at the [Original Image], check whether *every* component in the draft plan (including **containers** implied by the JSON `containment_hierarchy`) appears in the diagram, and whether there are extra components. **Use the image as the ground truth to correct the list.**
    * **Edge Check (Critical)**: While looking at the [Original Image], **independently recount** all arrows.
    * **Conflict Resolution**: Does the number/topology of arrows in the draft plan match the [Original Image]?
    * **Container Connection Check (Key)**: **Examine the [Original Image] carefully! The JSON draft may have missed arrows pointing to container boundaries (for example, an 'Opinion' arrow). You must independently re-check and add any missing “node-to-container” edges.**
3.  **Plan the Layout (Layout)**:
    * While looking at the [Original Image], plan the `x, y, width, height` coordinates on a 10x10 grid for all nodes and **containers** in the **corrected list**.
4.  **Create Nodes and Containers (Nodes & Containers)**:
    * **First (Z-Order Critical)**: Traverse the list and **create all** `<mxCell>` elements marked as `is_background: true` **first**.
    * **Then**: Traverse the list again and create all **foreground** `<mxCell>` nodes (such as text, arrow labels, etc.), setting their `parent` to 1 or to their container’s ID.
    * **(This order ensures that backgrounds appear first in the XML and therefore lie at the bottom of the layer stack.)**
    * (Rule 5) Create all semantic icons (❄️, 🔥) and non-vector placeholders (screenshots).
5.  **Create Edges (Edges)**:
    * Traverse the **corrected** edge list (**making sure it includes the “node-to-container” edges you added**).
    * Ensure that you create a set of `<mxCell>` edges whose count **exactly matches** the [Original Image].
    * **Style Check**: Cross-check the image again and apply the correct styles.
    * **Edge Labels**: Add the `label` provided in the JSON.
6.  **Assemble & Validate (Assemble & Validate)**:
    - Assemble the XML.
    - **Run Final Validation Checks**:
     - 1. Is it well-formed?
     - 2. Are all `id`s unique?
     - 3. Are there any dangling `source/target` references?
     - 4. (XML Escaping Check): ...
     - 5. (Parent-Child Check - CRITICAL): ...
     - 6. **(Subgraph Construction Check - CRITICAL):** Did I check the JSON's `relationships_extended`? If I found a `type: "describes_subgraph"` instruction (like a "neural network"), did I *actually* create all of its *internal nodes* AND *internal edges* in my XML draft? Or did I "give up" (摆烂) and only draw the nodes but skip the edges? I **must** go back and add all missing internal edges before outputting.
7.  **Finally, output only the XML content.**
"""

    prompt = base_prompt

    if description:
        # 将结构化描述作为 JSON 草稿嵌入 Prompt，帮助模型对齐组件/连线语义
        prompt += "\n\n--- JSON Description Draft (for reference, KEEP IMAGE AS GROUND TRUTH) ---\n"
        prompt += json.dumps(description, ensure_ascii=False, indent=2)
        prompt += "\n"

    if context_text:
        # 可选的额外文本上下文，只作为补充说明
        prompt += "\nAdditional textual context (optional, secondary to the image):\n"
        prompt += context_text
        prompt += "\n"

    return prompt


# Alternative: More concise prompts for faster/cheaper models

def get_classification_prompt_concise(context_text: Optional[str] = None) -> str:
    """Shorter classification prompt for faster models"""
    prompt = """Classify this image as a structured diagram or not.
Target: flowcharts, architectures, networks, data flows, block diagrams.
Not: photos, UI screenshots, charts, tables, equations.
"""
    if context_text:
        prompt += f"\nContext: {context_text}\n"

    prompt += """\nJSON output:
{"is_candidate": bool, "score": 0-1, "diagram_type": "type|null", "reason": "text"}"""
    return prompt


def get_description_prompt_concise(context_text: Optional[str] = None) -> str:
    """Shorter description prompt"""
    prompt = """Describe this diagram structure:
1. Type and purpose
2. All components (id, type, label)
3. All connections (source, target, label)
4. Layout (hierarchical/layered/etc, direction)
"""
    if context_text:
        prompt += f"\nContext: {context_text}\n"

    prompt += """\nJSON output with: diagram_type, title, summary, components[], relationships[], spatial_layout, annotations[]"""
    return prompt


def get_xml_editing_incremental_prompt(
    original_xml: str,
    instruction: str
) -> str:
    """
    Generate XML editing prompt (incremental format to save tokens)
    
    Args:
        original_xml: Original XML content
        instruction: Modification instruction
        
    Returns:
        Prompt string
    """
    prompt = f"""You are a professional Draw.io XML editing expert. Your task is to edit the given XML according to the modification instruction.

## Original XML
```xml
{original_xml}
```

## Modification Instruction
{instruction}

## Requirements
1. **Only output modified parts**: To save tokens, you only need to output the modified XML fragments, not the complete XML
2. **Incremental format**: Output JSON format containing all places that need modification (because there may be multiple places to modify)
3. **Format requirements**:
   - Each modification contains two fields:
     - `original_fragment`: Original XML fragment (the part to be replaced)
     - `modified_fragment`: Modified XML fragment (the replacement content)
   - If there are multiple modifications, output multiple modification objects
4. **Fragment requirements**:
   - `original_fragment` must be a complete fragment from the original XML (can be a complete element, such as `<mxCell>...</mxCell>`)
   - `modified_fragment` is the corresponding modified fragment
   - Fragments must be precise enough to uniquely match the position in the original XML
5. **Maintain correct XML format**: Modified fragments must maintain correct and parseable XML format

## Output Format (Strict JSON)

Please output a JSON object in the following format:

```json
{{
  "changes": [
    {{
      "original_fragment": "<mxCell id='node_1' value='Old Text' ...>...</mxCell>",
      "modified_fragment": "<mxCell id='node_1' value='New Text' ...>...</mxCell>"
    }},
    {{
      "original_fragment": "<mxCell id='edge_1' ...>...</mxCell>",
      "modified_fragment": "<mxCell id='edge_1' ...>...</mxCell>"
    }}
  ]
}}
```

**Important Notes**:
- If the instruction involves only one modification, the `changes` array contains only one element
- If the instruction involves multiple modifications (e.g., "delete node A and node B"), the `changes` array contains multiple elements
- `original_fragment` must be a complete and precise fragment from the original XML
- For deletion operations, `modified_fragment` is an empty string `""`
- Only output JSON, do not include any explanatory text or Markdown code block markers

Please analyze the instruction and output incremental modification JSON:
"""
    return prompt
