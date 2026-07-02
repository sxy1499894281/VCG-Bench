# 表格美化显示说明

## 安装推荐包

为了获得更好的表格显示效果，建议安装以下包：

```bash
# 基础表格美化（推荐）
pip install tabulate

# 彩色表格显示（可选，更美观）
pip install rich
```

## 显示效果对比

### 1. 使用 tabulate（推荐）
- 使用网格格式（grid）显示表格
- 自动对齐数字
- 清晰的边框和分隔线
- 适合大多数场景

### 2. 使用 rich（最美观）
- 彩色表格显示
- 更美观的边框样式
- 自动处理长文本
- 适合数据量较小的表格（≤50行，≤15列）

### 3. 回退到 pandas（默认）
- 如果上述包都未安装，使用pandas默认显示
- 功能完整但格式较简单

## 使用方法

所有notebook都包含 `display_table()` 函数，使用方法：

```python
# 基本使用
display_table(df, title="表格标题", max_rows=20)

# 示例
display_table(task1_by_model_df, title="Task1按模型统计", max_rows=15)
```

## 函数参数

- `df`: 要显示的DataFrame
- `title`: 表格标题（可选）
- `max_rows`: 最大显示行数（默认20）
- `use_rich`: 是否优先使用rich显示（默认True）

## 注意事项

1. **rich** 适合小表格，大表格会自动回退到 tabulate
2. **tabulate** 适合所有大小的表格
3. 如果两个包都未安装，会使用pandas默认显示
4. 所有表格都会自动格式化浮点数为3位小数

