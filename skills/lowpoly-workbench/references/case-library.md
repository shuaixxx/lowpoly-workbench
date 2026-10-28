# 网格案例库 v0.1

每个案例保存真实顶点/面数组及局部坐标变换；图片可辅助审阅，不承担主索引。
工作区案例数据与 Skill 分开保存，例如 `<workspace>/lowpoly-workspace/cases/cases.sqlite3`。

## 记录

JSON 包含 `schema_version: 1`、唯一 `id`、`name`、`scope`（static/deforming/unspecified）、
`status`（unreviewed/accepted/rejected/failed）、`mesh.vertices`、`mesh.faces`、
`importance`、`provenance`、可选 `rule_ids` 和 `related_case_ids`。
`importance.weights` 与顶点一一对应；`null` 表示未标定，0 是已标定低优先级。
确认由用户绘制的权重，`author` 才能标为 user；合成赋值为 synthetic，未赋值通道为 unassigned，来源不明则为 unknown。导出时须明确传入已核实的来源，不能只因存在数值就推定作者。案例入库不会创建用户评价。
accepted/rejected 必须有 `review.by: user` 和可追溯的 `review.evidence`。
这是证据字段校验，无法代替代理核实评价确由用户作出。

`blender_bridge.export_patch(obj, path, face_indices=...)` 导出指定局部；省略索引时导出对象全部控制网格。
对较大高模先选定局部，避免将整件重网格作为微小布线案例。
v0.1 索引顶点/边/面数量、边界环、连通分量、面类型、度数直方图、Euler 值及 WL 结构指纹。
几何特征采用协方差特征值比例，允许平移、旋转和统一缩放；它是粗筛特征，不包含可靠的语义或曲率理解。

## 命令（普通 Python，无额外依赖）

```text
python mesh_cases.py add --db <cases.sqlite3> --record <patch.json>
python mesh_cases.py search --db <cases.sqlite3> --query <patch.json> --quads
python mesh_cases.py search --db <cases.sqlite3> --query <patch.json> --quads --lock-boundary
python mesh_cases.py stats --db <cases.sqlite3>
```

默认只检索 accepted；独立演示使用 `--include-unreviewed`。
`--same-signature` 只筛选相同 WL 指纹，仍需核对实际边界和连接。
`descriptor_distance` 只用于候选排序，未校准成质量、成功概率或效率指标。
相同几何的多种拓扑可以同时保留，不能仅凭形状相似度认定一种更好。
修改评价使用新记录 ID 并通过 `related_case_ids` 连接旧记录，保留当时的网格与规则版本。
v0.1 不自动合并或覆盖已有案例；相同 ID 会拒绝写入。
