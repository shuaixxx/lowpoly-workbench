# 安装、验证和独立复现

在仓库根目录运行命令。命令中的 `python` 应指向 Python 3.10+，`blender` 应指向要测试的 Blender 可执行文件。Windows 可以用完整可执行文件路径替换命令名。

## 安装三个 Skill

```powershell
python -X utf8 tools/install.py --dry-run
python -X utf8 tools/install.py
```

默认目录为 `CODEX_HOME/skills`；没有设置 `CODEX_HOME` 时为 `~/.codex/skills`。也可使用 `--dest` 指定目标。相同内容跳过；不同内容会停止，明确更新时添加 `--update`。更新先把原目录移入目标目录同级的 `skill-backups/lowpoly-workbench/<时间>/`，再复制新目录，不删除旧版本。

在 Codex 的新对话中调用 `$lowpoly-workbench`。这仅安装 Skill 和本地 Python 辅助代码，不安装 Blender、不启动外部服务、不更换 MCP 插件，也不使用 Scenario 云生成额度。

## 无 Blender 的检查

```powershell
python -B -X utf8 tools/verify_repository.py
python -B -X utf8 -m unittest discover -s skills/lowpoly-workbench/scripts -p "test_*.py" -v
python -B -X utf8 tools/seed_cases.py --out .local/cases.sqlite3
python -B -X utf8 skills/lowpoly-workbench/scripts/mesh_cases.py stats --db .local/cases.sqlite3
python -B -X utf8 skills/lowpoly-workbench/scripts/mesh_cases.py search --db .local/cases.sqlite3 --query examples/scenario-002/cases/Tube_08.json --quads --include-unreviewed
```

起始数据库可随时由四份 JSON 重建。不要直接修改 `examples/` 中的历史试验；个人评价和后续案例放在自己的工作目录。重复种子目标会拒绝覆盖。

## Blender 独立试验

已实测 5.0.1。输出目录必须为空；试验仅接受后台且未打开用户文件的启动方式：

```powershell
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 1 --python skills/lowpoly-workbench/scripts/trial_scenario.py -- --scenario-root skills --out .local/trial-new
```

运行会创建合成高模和四个低模，导出案例、索引、统计、线框/中性光预览，保存并重新打开合成 `.blend`。`--skip-render` 适合仅检查几何与索引；使用这个选项时不应声称已检查生成的预览。

当前辅助工具可通过 Blender Python 或现有 MCP 桥接调用；本仓库不提供统一 GUI。对用户资产进行操作前先读 Skill，检查场景、范围和版本，保留原文件。不要把独立试验脚本粘贴到正在制作的场景运行。

## 版本与数据

Scenario 的两个 Skill 固定在 `third-party.json` 记录的提交。上游更新可能改变行为，应单独验证后再升级。规则文档和当前 Skill 为 v0.1.1，案例 JSON 的 `schema_version` 为 1；两种版本含义不同。
