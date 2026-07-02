# Draw.io CLI Linux 部署指南

## 概述

代码已经过优化，可以在Linux环境下正常使用draw.io CLI进行渲染。主要改进包括：

1. ✅ **自动查找draw.io**：支持多种Linux安装方式
2. ✅ **AppImage支持**：自动检测和配置AppImage文件
3. ✅ **无头模式支持**：自动添加`--no-sandbox`参数（如需要）
4. ✅ **错误处理增强**：更详细的错误日志和自动重试机制
5. ✅ **超时时间优化**：从30秒增加到60秒

---

## Linux安装Draw.io CLI

### 方式1：通过包管理器安装（推荐）

#### Debian/Ubuntu
```bash
sudo apt update
sudo apt install drawio
```

#### Fedora/RHEL
```bash
sudo dnf install drawio
```

#### Arch Linux
```bash
sudo pacman -S drawio
```

安装后，draw.io通常位于 `/usr/bin/drawio`，代码会自动检测。

### 方式2：使用AppImage（无需root权限）

1. **下载AppImage**
   ```bash
   cd ~/Downloads
   wget https://github.com/jgraph/drawio-desktop/releases/latest/download/drawio-x86_64-*.AppImage
   ```

2. **赋予执行权限**
   ```bash
   chmod +x drawio-x86_64-*.AppImage
   ```

3. **移动到合适位置（可选）**
   ```bash
   mkdir -p ~/Applications
   mv drawio-x86_64-*.AppImage ~/Applications/
   ```

代码会自动在以下位置查找AppImage：
- `~/Applications/drawio*.AppImage`
- `~/Downloads/drawio*.AppImage`
- `/opt/drawio*.AppImage`

### 方式3：手动指定路径

如果draw.io安装在其他位置，可以在代码中手动指定：

```python
from src.renderer.drawio_renderer import DrawioRenderer

renderer = DrawioRenderer(
    backend='drawio-cli',
    drawio_path=Path('/path/to/your/drawio'),  # 指定路径
    skip_render=False
)
```

---

## 代码改进说明

### 1. 自动查找draw.io (`_find_drawio`)

**改进内容：**
- ✅ 增加了AppImage文件的自动搜索
- ✅ 自动检测文件是否可执行，如不可执行则尝试添加执行权限
- ✅ 支持更多Linux常见路径（`~/.local/bin/drawio`等）
- ✅ 改进了`which`命令的超时处理

**支持的路径：**
- `/usr/bin/drawio` - 系统包管理器安装
- `/usr/local/bin/drawio` - 本地安装
- `/snap/bin/drawio` - Snap包安装
- `~/Applications/drawio*.AppImage` - AppImage（用户目录）
- `~/Downloads/drawio*.AppImage` - AppImage（下载目录）
- `~/.local/bin/drawio` - 用户本地bin目录

### 2. 渲染命令优化 (`_render_with_drawio_cli`)

**改进内容：**
- ✅ **自动添加`--no-sandbox`**：在Linux环境下使用AppImage时自动添加，避免chrome-sandbox错误
- ✅ **超时时间增加**：从30秒增加到60秒，适合复杂图表
- ✅ **错误日志增强**：输出更详细的错误信息，便于调试
- ✅ **自动重试机制**：如果短选项格式失败，自动尝试长选项格式

**命令格式：**
- 默认使用短选项：`drawio -x -f png -s 1.0 -o output.png input.drawio`
- 失败时自动尝试长选项：`drawio --export --format png --scale 1.0 --output output.png input.drawio`

### 3. 新增长选项支持 (`_render_with_long_options`)

如果短选项格式失败，代码会自动尝试长选项格式，提高兼容性。

---

## 使用示例

### 基本使用

```python
from pathlib import Path
from src.renderer.drawio_renderer import DrawioRenderer
from src.core.models import DiagramXML

# 创建renderer（自动检测draw.io）
renderer = DrawioRenderer()

# 检查是否可用
if renderer.can_render():
    print("Draw.io CLI is available")
    
    # 渲染XML
    xml_content = "<mxGraphModel>...</mxGraphModel>"
    diagram = DiagramXML(xml_content=xml_content, diagram_type='flowchart')
    
    success = renderer.render(
        diagram=diagram,
        output_path=Path("output.png"),
        format='png',
        scale=1.0,
        transparent=False
    )
    
    if success:
        print("Rendering succeeded!")
else:
    print("Draw.io CLI not found")
```

### 跳过渲染模式（HPC环境）

如果Linux服务器没有安装draw.io，可以使用跳过渲染模式：

```python
renderer = DrawioRenderer(skip_render=True)

# 如果PNG文件已存在，会返回True
# 如果不存在，会返回False并记录警告
```

---

## 常见问题排查

### 1. 找不到draw.io

**症状：** 日志显示 "Drawio executable not found"

**解决方案：**
1. 确认draw.io已安装：
   ```bash
   which drawio
   # 或
   drawio --version
   ```

2. 如果使用AppImage，确认文件有执行权限：
   ```bash
   chmod +x ~/Applications/drawio-x86_64-*.AppImage
   ```

3. 手动指定路径：
   ```python
   renderer = DrawioRenderer(drawio_path=Path("/path/to/drawio"))
   ```

### 2. chrome-sandbox错误

**症状：** 渲染失败，错误信息包含 "chrome-sandbox"

**解决方案：**
代码已自动处理，会在Linux AppImage环境下自动添加`--no-sandbox`参数。

如果仍有问题，可以手动运行：
```bash
drawio --no-sandbox -x -f png -o output.png input.drawio
```

### 3. 渲染超时

**症状：** 日志显示 "Drawio rendering timed out"

**解决方案：**
- 代码已增加超时时间到60秒
- 如果图表非常复杂，可以修改代码中的`timeout`参数
- 检查系统资源（CPU、内存）是否充足

### 4. 权限错误

**症状：** AppImage文件无法执行

**解决方案：**
```bash
chmod +x /path/to/drawio-x86_64-*.AppImage
```

代码会自动尝试添加执行权限，但如果文件在系统保护目录，可能需要手动处理。

---

## 测试验证

### 测试draw.io是否正常工作

```bash
# 创建测试XML文件
cat > test.drawio << 'EOF'
<mxGraphModel>
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    <mxCell id="2" value="Hello" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">
      <mxGeometry x="100" y="100" width="120" height="60" as="geometry"/>
    </mxCell>
  </root>
</mxGraphModel>
EOF

# 测试渲染
drawio -x -f png -o test.png test.drawio

# 检查输出
ls -lh test.png
```

### 测试Python代码

```python
from pathlib import Path
from src.renderer.drawio_renderer import DrawioRenderer

renderer = DrawioRenderer()
print(f"Draw.io found: {renderer.can_render()}")
print(f"Draw.io path: {renderer.drawio_path}")
```

---

## 总结

✅ **代码已完全支持Linux环境**，主要改进：

1. 自动检测多种安装方式（包管理器、AppImage等）
2. 自动处理Linux特有的问题（sandbox、权限等）
3. 增强的错误处理和日志输出
4. 自动重试机制（短选项→长选项）

**无需修改代码**，只需确保draw.io CLI已正确安装即可使用。

---

## 参考链接

- [Draw.io GitHub Releases](https://github.com/jgraph/drawio-desktop/releases)
- [Draw.io CLI文档](https://github.com/jgraph/drawio-desktop/wiki/Command-Line)
- [AppImage使用指南](https://docs.appimage.org/)

