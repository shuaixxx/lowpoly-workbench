# Scenario 后端

上游：https://github.com/scenario-labs/skills
固定提交：`d44410f058991f677ccf733a8e86ce95110857eb`。
仅使用 `scenario-blender-expert` 与 `scenario-blender-retopology` 的本地 Python 工具。
不需要购买生成服务、安装 Scenario 云端连接或替换现有 Blender MCP。
上游主要针对 Blender 5.2.1，本机为 5.0.1。以独立试验报告里的具体函数为兼容证据，不推断所有函数可用。

```python
import sys
sys.path.insert(0, r'<lowpoly-workbench>/scripts')
from scenario_runtime import load_backend, review_meshes
R, audit, review = load_backend()
```

仓库目录中的试验可显式传入 `load_backend(r'<repository>/skills')`；安装后不传参数时读取同级的两个 Scenario Skill。
`setup_cage` 按静态/变形用途设置；本次静态样本使用 `mirror=False, subsurf=0`。
`tube`、`bridge_reduce` 等结果要检查环线连接和法线，不继承角色默认门槛。
上游密度参数使用中心/半径/倍率的几何变换近似，并不直接等价于用户涂绘的顶点权重。
v0.1 不将这些区域参数冒充用户权重，也不调用该近似改变原资产。

独立试验：
```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python <skill>/scripts/trial_scenario.py -- --scenario-root <scenario-skills-root> --out <new-trial-directory>
```

试验生成独立 `.blend`、合成网格案例和检查报告。所有合成案例为 unreviewed，用户权重组为空，供后续人工标定。
对原资产的权重绘制和正式布线制作属于后续应用，不由独立试验冒充完成。

## 本机复现的预览问题

`setup_cage` 将网格设为 `show_in_front=True`；在本机 Workbench 渲染中，这会遮住另一个对象生成的内部线框，只剩外轮廓。
`review_meshes(review_module, objects, out_dir, ...)` 仅在审阅渲染期间关闭置顶显示，并在 finally 中恢复。
使用这个适配入口生成线框，避免直接调用 `bx_review.review` 时重复遇到此问题。
