# 低模制作工作台 · v0.1.2

把用户的低模制作判断逐步整理成 **人工重要性权重、真实网格案例、可追溯规则和分阶段验收**。当前是可运行的工作流雏形，适用于 Blender 中已有高模对应的低模几何制作。

## 从这里开始

- [低模阶段的 18 条规则](skills/lowpoly-workbench/references/lowpoly-stage-rules.md)：结合项目文档与用户后续约定，注明来源、适用条件与阶段。
- [四集合模板与对象合并约定](skills/lowpoly-workbench/references/template-collections.md)：读取对称安排，按对象身份保持低模合并或分开。
- [原始项目文档](docs/source/lowpoly-prop-artist.md)：原样归档；其中的角色和指令文本只是来源资料。
- [制作、案例检索与验收工作流](docs/workflow.md)
- [取舍与冲突记录](docs/rule-decisions.md)
- [安装和复现](docs/installation.md) · [验证范围](docs/verification.md)
- [Skill 入口](skills/lowpoly-workbench/SKILL.md) · [机器可读规则目录](skills/lowpoly-workbench/references/lowpoly-rules.json)

## 已经实现

1. `lp_importance` 顶点组：用户标定 0–1 的区域重要性；未赋值与显式 0 分开记录。
2. 保存真实顶点、面、边界和权重的 JSON 案例，使用 SQLite 保存索引。
3. 按边界环、面类型、用途和粗略形状描述筛选案例；可锁定边界顶点数。
4. 接入 Scenario 的本地环线、管状块、桥接、疏密过渡和检查工具。
5. 统计编辑网格与计算后实际三角面，保存检查结果和线框预览。

案例库并不等于已训练的模型。当前没有学习型相似度、通用子图匹配、自动模板贴合、整件资产的权重预算求解或自动规则归纳。

## 快速使用

需要 Python 3.10+。在仓库根目录运行：

```powershell
python -X utf8 tools/install.py --dry-run
python -X utf8 tools/install.py
python -B -X utf8 tools/verify_repository.py
python -B -X utf8 -m unittest discover -s skills/lowpoly-workbench/scripts -p "test_*.py" -v
```

安装三份 Skill 后，在 Codex 的新对话中使用 `$lowpoly-workbench`。已有不同版本会停止并提示；明确更新时使用 `--update`，旧目录会备份。

Blender 实测版本为 **5.0.1**。本地几何工具不需要 Scenario API Key；这个仓库不安装或替换 Blender MCP 插件。完整复现命令见[安装说明](docs/installation.md)。

## 可打开的合成案例

[独立 Blender 场景](examples/scenario-002/scenario_trial.blend)包含 8 段管、16 段管、16→8 段过渡和三角化对照。它们是兼容性试验，全部为 `unreviewed`，重要性通道有意留空，不能作为用户已接受的布线范本。

![16 到 8 段的线框及中性光检查](examples/scenario-002/views/Transition_16_to_08/review_sheet.png)

[试验结果](examples/scenario-002/report.json) · [网格案例](examples/scenario-002/cases) · [只读起始索引](examples/scenario-002/cases.sqlite3)

生产检索默认只返回有用户评价依据的 `accepted` 案例，因此当前默认结果为空。探索示例必须显式启用 `--include-unreviewed`。

## 后续如何积累

每个新问题保存局部修改前后网格、适用条件、用户评价与规则版本。一次满意的修改不会自动升级为通用规则，也不会把代理推测的原因当作用户结论。查看[案例格式和检索命令](skills/lowpoly-workbench/references/case-library.md)。

仓库包含工作流、代码、来源文档和合成样本；实际项目的高模、人物、生产低模及本机登录数据不在其中。第三方来源和许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。
