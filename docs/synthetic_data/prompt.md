## task1合成数据流程:
1、搜集数据:
- 网络爬取图片
- ppt爬取图片
- 部分公开benchmark:
  "SALT-NLP/Design2Code"
  "SalihaE/UMLModels"
  "rakitha/mermaid-flowchart-transformer"
2、调用gemini-3-pro-preview粗略筛选合适的图片（screening）
4、调用gemini-3-pro-preview生成图片描述，得到llm_description.json，参考片段如下:
```json
{
  "image_type": "schematic diagram",
  "overview": "A technical diagram illustrating a distributed computing algorithm (likely Ring Attention), detailing a multi-step data transfer and computation process across four ranks (CP rank0-3). It shows a cyclic 'SendRecv' phase for shifting data blocks (Q), followed by a 'permute' phase and an 'all2all' communication phase.",
  "components": [
    {
      "name": "Step 1 Label",
      "count": 1,
      "description": "Text label indicating the first phase of the process."
    },
    {
      "name": "Step 2 Label",
      "count": 1,
      "description": "Text label indicating the second phase of the process."
    },
    {
      "name": "CP rank0 (Step 1)",
      "count": 1,
      "description": "Rounded rectangle container for Rank 0 in Step 1, containing Blue data blocks Q0, K0, V0 and attention text."
    },
    {
      "name": "CP rank1 (Step 1)",
      "count": 1,
      "description": "Rounded rectangle container for Rank 1 in Step 1, containing Yellow data blocks Q1, K1, V1 and attention text."
    }
  ],
  "spatial_layout": {
    "primary_layout": "Two main rows. The top row is split into two columns ('Step 1' and 'Step 2') separated by a vertical line. The bottom row shows a progression from a 'permute' phase on the left to an 'all2all' phase on the right.",
    "relative_positions": [
      "Step 1 is to the left of Step 2.",
      "In Step 1 and 2, Ranks are arranged in a square topology (0 top-left, 1 top-right, 2 bottom-right, 3 bottom-left).",
      "The Permute phase (bottom-left) is to the left of the All2All phase (bottom-right)."
    ]
  }
}
```
5、调用gemini-3-pro-preview根据描述“搭建”出xml代码，得到diagram.xml,参考片段如下:
```xml
<mxGraphModel dx="1422" dy="794" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1200" pageHeight="1100" math="0" shadow="0">
    <root>
      <mxCell id="0" />
      <mxCell id="1" parent="0" />
      
      <!-- Rank 0 (Top Left) -->
      <mxCell id="s1_r0_lbl" value="CP rank0" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;" vertex="1" parent="1">
        <mxGeometry x="100" y="80" width="80" height="20" as="geometry" />
      </mxCell>
      <mxCell id="s1_r0" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#000000;arcSize=10;verticalAlign=top;" vertex="1" parent="1">
        <mxGeometry x="80" y="100" width="120" height="120" as="geometry" />
      </mxCell>
      <mxCell id="s1_r0_q" value="Q0" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#A0C0F0;strokeColor=#000000;" vertex="1" parent="s1_r0">
        <mxGeometry x="25" y="15" width="70" height="20" as="geometry" />
      </mxCell>
      <mxCell id="s1_r0_k" value="K0" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#A0C0F0;strokeColor=#000000;" vertex="1" parent="s1_r0">
        <mxGeometry x="25" y="35" width="70" height="20" as="geometry" />
      </mxCell>
      <mxCell id="s1_r0_v" value="V0" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#A0C0F0;strokeColor=#000000;" vertex="1" parent="s1_r0">
        <mxGeometry x="25" y="55" width="70" height="20" as="geometry" />
      </mxCell>
      <mxCell id="s1_r0_txt" value="&lt;font color=&quot;#CC0000&quot;&gt;Attn(Q0, KV0)&lt;/font&gt;" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=11;" vertex="1" parent="s1_r0">
        <mxGeometry x="5" y="85" width="110" height="20" as="geometry" />
      </mxCell>
      
      <!-- Step 1 Ring Arrow -->
      <mxCell id="edge_s1_1" value="SendRecv(Q1)" style="edgeStyle=none;html=1;endArrow=classic;startArrow=none;exitX=0;exitY=0.5;entryX=1;entryY=0.5;rounded=0;" edge="1" parent="1" source="s1_r1" target="s1_r0">
        <mxGeometry relative="1" as="geometry" />
      </mxCell>
    </root>
</mxGraphModel>
```
6、渲染得到的xml代码得到还原的渲染图rendered.png
7、最后得到{orginal.png,diagram.xml,rendered.png，llm_description.json}
8、送去evaluator评估模型能力

## task2合成数据流程:
1、人工筛选task1中还原较好的{diagram.xml,rendered.png}作为task2的Ground Truth
2、调用gemini-3-pro-preview合成不同难度的修改指令，得到{diagram.xml,rendered.png，instructions}
3、让不同模型根据instructions修改diagram.xml，输出model_output.json，参考片段如下:
```json
[
  {
    "original_fragment": "<mxCell id=\"s2_r0_lbl\" value=\"CP rank0\" ...>...</mxCell>\n<mxCell id=\"s2_r0\" value=\"\" style=\"rounded=1;...\">...</mxCell>\n<mxCell id=\"s2_r0_q\" value=\"Q1\" ...>...</mxCell>...",
    "modified_fragment": "<mxCell id=\"s2_buffer\" value=\"Buffer\" style=\"ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#ffffff;strokeColor=#000000;\" vertex=\"1\" parent=\"1\">\n        <mxGeometry x=\"660\" y=\"100\" width=\"120\" height=\"120\" as=\"geometry\" />\n      </mxCell>"
  },
  {
    "original_fragment": "<mxCell id=\"edge_s2_1\" value=\"SendRecv(Q2)\" ... source=\"s2_r1\" target=\"s2_r0\">...</mxCell>",
    "modified_fragment": "<mxCell id=\"edge_s2_1\" value=\"SendRecv(Q2)\" ... source=\"s2_r1\" target=\"s2_buffer\">...</mxCell>"
  },
  {
    "original_fragment": "<mxCell id=\"edge_s2_2\" value=\"SendRecv(Q1)\" ... source=\"s2_r0\" target=\"s2_r3\">...</mxCell>",
    "modified_fragment": ""
  }
]
```
4、使用正则匹配替换原xml片段，输出修改后的xml:modified.xml
5、渲染修改后的xml得到修改后的图像:modified.png
6、最后得到{rendered.png，instructions，model_output.json，modified.xml，modified.png}
7、送去evaluator评估模型能力

请你阅读上面的流程，给我一个更完整的画图prompt，我需要根据这个prompt让其他模型来画出这个图片，要求:
1、我引用图片的地方不用描述，生成占位图标即可，我自己填入
2、流程的流向从左到右，从上到下
3、内容要求
尽可能涵盖方法的大部分关键步骤、核心模块、数据流动方向
使用流程图、框架图、模块图、结构示意图等科研图风格
描述每个模块的形状、分区、相互连接方式、箭头指向、层次结构
若涉及模型结构，请描述输入、预处理、核心模块、算法步骤、输出
若涉及多阶段方法，需体现流程化的层级关系
4、视觉与版式
图像饱满，不留大片空白
图元（boxes, arrows, icons）比例适中
布局整齐，左右/上下逻辑自然
使用柔和但可区分的色块区分模块，并确保可打印性
分辨率高，适合论文投稿（≥ 4K）
5、语言要求
Prompt 输出为 英文
结构用清晰的层级描述，便于图像生成模型理解
使用如 “diagram”, “workflow”, “pipeline”, “schematic illustration” 等科研绘图常用词
6、额外要求
不加入3D、写实人物
整体符合国际期刊科研方法图标准
7、参考图片

请你阅读上面的流程，给我一个更完整的prompt，我需要根据这个prompt让其他模型来给出这个图片的xml代码文件，xml渲染出来的图片要求如下:
1、流程的流向从左到右，从上到下
2、分辨率高，适合论文投稿（≥ 4K）
3、语言要求
Prompt 输出为 英文
结构用清晰的层级描述，便于图像生成模型理解
使用如 “diagram”, “workflow”, “pipeline”, “schematic illustration” 等科研绘图常用词
4、风格参考图片: