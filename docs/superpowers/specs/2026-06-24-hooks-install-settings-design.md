# 设计文档：claude-notifier hooks install 写入 ~/.claude/settings.json

## 1. 背景与目标

### 1.1 当前问题

当前 `claude-notifier hooks install` 将 Claude Code 钩子配置写入：

```
~/.config/claude/hooks.json
```

但 Claude Code 实际读取并生效的配置文件是：

```
~/.claude/settings.json
```

中的 `hooks` 字段。这导致：

- 安装后 Claude Code 没有真正加载 notifier 钩子。
- 文档中示例 `cat ~/.claude/settings.json | jq '.hooks'` 与实际安装位置不一致。
- 卸载逻辑 (`src/claude_notifier/cli/uninstall.py`) 已经知道 `~/.claude/settings.json`，但安装器没有往那里写。

### 1.2 目标

让 `claude-notifier hooks install` 把钩子配置写入 `~/.claude/settings.json` 的 `hooks` 字段：

- 若 `settings.json` 不存在，创建文件并插入 `hooks` 和 `_metadata`。
- 若 `settings.json` 已存在但无 `hooks`，直接插入。
- 若 `settings.json` 已有 `hooks`：
  - 若是本工具安装的，直接替换。
  - 若不是本工具安装的，需要 `--force` 才替换；否则提示用户。
- 安装时若发现旧路径 `~/.config/claude/hooks.json` 存在且由本工具创建，备份并删除。
- 卸载时从 `settings.json` 中移除 `hooks` 和 `_metadata`，保留其他用户配置。

---

## 2. 架构设计

### 2.1 组件划分

```
┌─────────────────────────────────────┐
│  src/claude_notifier/hooks/installer.py │
├─────────────────────────────────────┤
│  ClaudeHookInstaller                │
│  ├── 目标文件: ~/.claude/settings.json  │
│  ├── 负责: detect / install / uninstall │
│  ├── 新增/调整方法:                 │
│  │   - read_settings()              │
│  │   - write_settings()             │
│  │   - backup_settings()            │
│  │   - is_notifier_managed()        │
│  │   - create_hooks_config()        │
│  │   - create_metadata()            │
│  │   - migrate_legacy_hooks_file()  │
│  │   - install_hooks()              │
│  │   - uninstall_hooks()            │
│  │   - verify_installation()        │
│  │   - get_installation_status()    │
│  └── 废弃: hooks.json 目标路径逻辑    │
└─────────────────────────────────────┘
```

### 2.2 目标路径变更

| 项目 | 旧路径 | 新路径 |
|---|---|---|
| 安装目标 | `~/.config/claude/hooks.json` | `~/.claude/settings.json` |
| 备份位置 | `~/.config/claude/hooks.json.backup.*` | `~/.claude/settings.json.YYYYMMDD_HHMMSS.backup` |
| 旧文件清理 | 无 | `~/.config/claude/hooks.json`（若由本工具创建） |

### 2.3 配置结构

写入 `~/.claude/settings.json` 的片段示例：

```json
{
  "effortLevel": "max",
  "env": {},
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write|MultiEdit|DeleteFile|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/python /path/to/claude_hook.py"
          }
        ]
      }
    ],
    "PostToolUse": [...],
    "Stop": [...],
    "Notification": [...]
  },
  "_metadata": {
    "installer": "claude-notifier-pypi",
    "api_version": "2.0",
    "installed_at": "...",
    "hook_script": "/path/to/claude_hook.py",
    "config_dir": "/home/user/.claude-notifier"
  },
  "language": "中文",
  "model": "opus[1m]"
}
```

`hooks` 与 `_metadata` 作为 `settings.json` 的顶级字段，与用户的其他配置共存。

---

## 3. 数据流

### 3.1 安装流程

```
claude-notifier hooks install [--force]
│
├─ 1. detect_claude_code()
│     未检测到 → 失败返回
│
├─ 2. 确保 ~/.claude 目录存在
│
├─ 3. read_settings()
│     读取 ~/.claude/settings.json，不存在返回 {}
│
├─ 4. backup_settings()
│     生成时间戳备份文件
│
├─ 5. is_notifier_managed(settings)
│     判断现有 hooks 是否由本工具安装
│     ├─ 是 → 继续替换
│     └─ 否 → 检查 --force
│         ├─ 有 --force → 继续替换
│         └─ 无 --force → 提示确认/失败
│
├─ 6. settings['hooks'] = create_hooks_config()
│   settings['_metadata'] = create_metadata()
│
├─ 7. write_settings(settings)
│
├─ 8. migrate_legacy_hooks_file()
│     若 ~/.config/claude/hooks.json 存在且由本工具创建
│     则备份并删除
│
└─ 9. verify_installation()
      检查 settings.json 中 hooks 字段结构
```

### 3.2 卸载流程

```
claude-notifier hooks uninstall
│
├─ 1. 若 ~/.claude/settings.json 不存在 → 成功返回
│
├─ 2. read_settings()
├─ 3. backup_settings()
├─ 4. 删除 settings['hooks']
├─ 5. 删除 settings['_metadata']
├─ 6. write_settings(settings)
│
└─ 7. 返回成功
```

### 3.3 状态检查流程

```
claude-notifier hooks status
│
├─ 1. detect_claude_code()
├─ 2. 检查 ~/.claude/settings.json 是否存在
├─ 3. 读取并解析 hooks 字段
├─ 4. 统计启用的钩子类型
└─ 5. 打印状态
```

---

## 4. 关键算法

### 4.1 识别“本工具安装的 hooks”

满足以下任一条件即视为由本工具管理：

1. `settings.json` 中存在 `_metadata.installer == "claude-notifier-pypi"`。
2. `settings.json` 中 `hooks` 字段下任一 command 字符串包含 `claude_notifier/hooks/claude_hook.py` 或 `claude_hook.py`。

```python
def is_notifier_managed(self, settings: dict) -> bool:
    metadata = settings.get("_metadata", {})
    if metadata.get("installer") == "claude-notifier-pypi":
        return True

    hooks = settings.get("hooks", {})
    marker = "claude_hook.py"
    for hook_list in hooks.values():
        for item in hook_list:
            for hook in item.get("hooks", []):
                command = hook.get("command", "")
                if marker in command:
                    return True
    return False
```

### 4.2 旧 hooks.json 识别

旧 `~/.config/claude/hooks.json` 若满足 `is_notifier_managed()` 相同逻辑，则视为本工具创建。

---

## 5. 错误处理

| 阶段 | 异常场景 | 处理 |
|---|---|---|
| 安装前 | 未检测到 Claude Code | 失败：提示安装 Claude Code |
| 安装前 | `~/.claude` 目录无法创建 | 失败：返回原始异常 |
| 安装中 | `settings.json` 不存在 | 当作空字典处理 |
| 安装中 | `settings.json` JSON 损坏 | 先备份损坏文件，然后覆盖为有效配置 |
| 安装中 | 现有 hooks 非本工具且未 `--force` | 失败：提示使用 `--force` 或备份后确认 |
| 安装中 | 写入 settings.json 失败 | 失败：尝试恢复备份 |
| 安装后 | 旧 `hooks.json` 无法删除 | 警告：不影响安装成功 |
| 验证 | hooks 结构不完整 | 失败或警告 |
| 卸载 | settings.json 不存在 | 成功：无需卸载 |
| 卸载 | settings.json 损坏 | 备份后尝试重写；失败则失败 |
| 卸载 | 删除后 settings 为空 | 保留空对象 `{}`，不删除文件 |

---

## 6. CLI 与文档联动

### 6.1 CLI 提示文案更新

- `install_hooks()` 内部报错中提到的路径统一改为 `~/.claude/settings.json`。
- `main.py` 中 `hooks install` 的帮助信息无需新增选项，保持 `--force` 语义。
- `setup` 命令调用 installer 的方式不变。

### 6.2 文档更新

- `docs/quickstart.md` 和 `docs/quickstart_en.md` 中：
  - 删除指向 `~/.config/claude/hooks.json` 的说明。
  - 统一使用 `cat ~/.claude/settings.json | jq '.hooks'`。
- `docs/configuration.md`（如相关）同步更新钩子配置位置。

---

## 7. 测试策略

### 7.1 单元测试

使用临时目录模拟 `HOME`，覆盖：

| 用例 | 预期 |
|---|---|
| settings.json 不存在时安装 | 生成完整 hooks 和 metadata |
| 已有 notifier hooks 时安装 | 直接替换，保留其他字段 |
| 有非 notifier hooks 且无 `--force` | 拒绝安装 |
| 有非 notifier hooks 且有 `--force` | 替换并备份 |
| 旧 hooks.json 存在且由 notifier 创建 | 备份并删除旧文件 |
| 旧 hooks.json 存在但非 notifier 创建 | 保留，仅提示 |
| 安装保留其他 settings 字段 | env、model、language 等不变 |
| 卸载 | 删除 hooks 和 metadata，保留其他字段 |
| settings.json 不存在时卸载 | 成功 |
| 状态检查 | 正确识别已安装/未安装 |

### 7.2 集成测试

在临时 HOME 下跑完整流程：

```
install → status → verify → uninstall → status
```

---

## 8. 兼容性说明

- **旧路径 `~/.config/claude/hooks.json`**：不再读写。安装时若检测到由本工具创建，备份并删除；否则忽略。
- **现有已安装用户**：重新运行 `claude-notifier hooks install` 后，配置会迁移到 `~/.claude/settings.json`，旧文件会被清理。
- **非 notifier 用户的 hooks**：不会被静默覆盖，需 `--force`。

---

## 9. 后续工作

1. 按本设计实现 `installer.py` 修改。
2. 更新相关单元测试与集成测试。
3. 更新 `docs/quickstart.md` 和 `docs/quickstart_en.md` 中的路径说明。
4. 手动验证：在临时 HOME 下跑通 install → status → uninstall 流程。
