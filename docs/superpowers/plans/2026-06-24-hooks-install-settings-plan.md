# hooks install 写入 ~/.claude/settings.json 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修改 `claude-notifier hooks install/uninstall/status/verify`，使钩子配置写入 `~/.claude/settings.json` 的 `hooks` 字段，安全替换或插入，并迁移旧 `~/.config/claude/hooks.json`。

**Architecture:** 集中修改 `src/claude_notifier/hooks/installer.py` 中的 `ClaudeHookInstaller`，新增 settings.json 读写、来源识别、旧文件迁移逻辑；CLI 层无需改接口；新增独立测试文件覆盖 installer 行为；更新 quickstart 文档中的路径示例。

**Tech Stack:** Python 3.8+, pathlib, json, pytest, click (用于 CLI 测试)。

## Global Constraints

- 目标文件：`~/.claude/settings.json`。
- 旧路径 `~/.config/claude/hooks.json` 不再读写；安装时若判定为本工具创建则备份并删除。
- 识别本工具安装的 hooks：`_metadata.installer == "claude-notifier-pypi"` 或任一 hook command 包含 `claude_hook.py`。
- 非本工具 hooks 时，`install_hooks(force=False)` 必须拒绝替换。
- 所有写操作前必须备份 `settings.json`。
- 卸载时仅删除 `hooks` 和 `_metadata`，保留其他用户配置。
- Python 3.8+ 兼容，类型注解使用 `typing.Dict`, `typing.Optional`, `typing.Tuple` 等。
- 提交信息使用中文，符合仓库现有风格。

---

## File Structure

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `src/claude_notifier/hooks/installer.py` | 修改 | 核心安装器：目标路径改为 `~/.claude/settings.json`，新增读写/备份/识别/迁移方法。 |
| `tests/test_hooks_installer.py` | 新建 | `ClaudeHookInstaller` 的单元测试，使用临时 HOME。 |
| `docs/quickstart.md` | 修改 | 将 `cat ~/.config/claude/hooks.json` 改为 `cat ~/.claude/settings.json \| jq '.hooks'`。 |
| `docs/quickstart_en.md` | 修改 | 英文文档同步（若存在旧路径引用）。 |

---

## Task 1: 重构 `ClaudeHookInstaller` 的目标路径与基础读写

**Files:**
- Modify: `src/claude_notifier/hooks/installer.py:18-289`
- Test: `tests/test_hooks_installer.py` (新建)

**Interfaces:**
- Consumes: 无（此任务为基础设施）。
- Produces:
  - `ClaudeHookInstaller.settings_file: Path` — 指向 `~/.claude/settings.json`。
  - `ClaudeHookInstaller.legacy_hooks_file: Path` — 指向 `~/.config/claude/hooks.json`。
  - `ClaudeHookInstaller.read_settings() -> dict` — 读取 settings.json，不存在或空返回 `{}`。
  - `ClaudeHookInstaller.write_settings(settings: dict) -> None` — 缩进 2 写入 JSON。
  - `ClaudeHookInstaller.backup_settings() -> Optional[str]` — 生成 `settings.json.YYYYMMDD_HHMMSS.backup`。

- [ ] **Step 1: 写失败测试，验证 installer 使用新的 settings 路径**

```python
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from claude_notifier.hooks.installer import ClaudeHookInstaller


class TestClaudeHookInstallerPaths:
    def test_settings_file_points_to_claude_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            installer = ClaudeHookInstaller()
            # 通过 mock Path.home 来验证
            with patch.object(Path, 'home', return_value=home):
                installer = ClaudeHookInstaller()
                assert installer.settings_file == home / '.claude' / 'settings.json'
                assert installer.legacy_hooks_file == home / '.config' / 'claude' / 'hooks.json'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_hooks_installer.py::TestClaudeHookInstallerPaths::test_settings_file_points_to_claude_settings -v`
Expected: FAIL — `settings_file` 或 `legacy_hooks_file` 属性不存在。

- [ ] **Step 3: 修改 installer.py 构造函数与基础路径属性**

```python
# 在 __init__ 中替换原有路径定义
self.home_dir = Path.home()
self.claude_config_dir = self.home_dir / '.claude'
self.settings_file = self.claude_config_dir / 'settings.json'
self.legacy_hooks_file = self.home_dir / '.config' / 'claude' / 'hooks.json'
self.notifier_config_dir = self.home_dir / '.claude-notifier'
```

同时保留 `self.hooks_file` 的只读兼容（可选，测试用不到），或完全删除。

- [ ] **Step 4: 添加 read_settings / write_settings / backup_settings 方法**

```python
def read_settings(self) -> Dict[str, any]:
    """读取 Claude Code settings.json，不存在或为空返回空字典。"""
    if not self.settings_file.exists():
        return {}
    try:
        with open(self.settings_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except Exception as e:
        self.logger.warning(f"读取 settings.json 失败: {e}，将使用空配置")
        return {}

def write_settings(self, settings: Dict[str, any]) -> None:
    """写入 Claude Code settings.json。"""
    self.claude_config_dir.mkdir(parents=True, exist_ok=True)
    with open(self.settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def backup_settings(self) -> Optional[str]:
    """备份当前 settings.json，返回备份路径。"""
    if not self.settings_file.exists():
        return None
    from datetime import datetime
    backup_name = f"settings.json.{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup"
    backup_path = self.claude_config_dir / backup_name
    try:
        import shutil
        shutil.copy2(self.settings_file, backup_path)
        self.logger.info(f"已备份 settings.json 到: {backup_path}")
        return str(backup_path)
    except Exception as e:
        self.logger.error(f"备份 settings.json 失败: {e}")
        return None
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_hooks_installer.py::TestClaudeHookInstallerPaths -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/claude_notifier/hooks/installer.py tests/test_hooks_installer.py
git commit -m "$(cat <<'EOF'
refactor(hooks): 将安装器目标路径改为 ~/.claude/settings.json

新增 read_settings / write_settings / backup_settings 基础方法。

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 实现 hooks 来源识别与 metadata 生成

**Files:**
- Modify: `src/claude_notifier/hooks/installer.py`
- Test: `tests/test_hooks_installer.py`

**Interfaces:**
- Consumes: `read_settings()` 返回的 dict。
- Produces:
  - `is_notifier_managed(settings: dict) -> bool`
  - `create_metadata() -> dict`
  - `create_hooks_config()` 调整：返回仅含 `hooks` 字段值的 dict（当前返回顶层对象，需拆分）。

- [ ] **Step 1: 写失败测试验证来源识别**

```python
class TestIsNotifierManaged:
    def _installer(self, tmp_home: Path):
        with patch.object(Path, 'home', return_value=tmp_home):
            return ClaudeHookInstaller()

    def test_detects_by_metadata_installer(self, tmp_path):
        installer = self._installer(tmp_path)
        settings = {"_metadata": {"installer": "claude-notifier-pypi"}}
        assert installer.is_notifier_managed(settings) is True

    def test_detects_by_hook_command(self, tmp_path):
        installer = self._installer(tmp_path)
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": "/usr/bin/python /some/path/claude_notifier/hooks/claude_hook.py"}
                        ]
                    }
                ]
            }
        }
        assert installer.is_notifier_managed(settings) is True

    def test_foreign_hooks_not_managed(self, tmp_path):
        installer = self._installer(tmp_path)
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": "/usr/bin/some-other-hook"}
                        ]
                    }
                ]
            }
        }
        assert installer.is_notifier_managed(settings) is False

    def test_empty_settings_not_managed(self, tmp_path):
        installer = self._installer(tmp_path)
        assert installer.is_notifier_managed({}) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_hooks_installer.py::TestIsNotifierManaged -v`
Expected: FAIL — `is_notifier_managed` 未定义。

- [ ] **Step 3: 实现 is_notifier_managed 与 create_metadata**

```python
def is_notifier_managed(self, settings: Dict[str, any]) -> bool:
    """判断 settings 中的 hooks 是否由本工具管理。"""
    metadata = settings.get('_metadata', {})
    if metadata.get('installer') == 'claude-notifier-pypi':
        return True

    hooks = settings.get('hooks', {})
    marker = 'claude_hook.py'
    for hook_list in hooks.values():
        if not isinstance(hook_list, list):
            continue
        for item in hook_list:
            if not isinstance(item, dict):
                continue
            for hook in item.get('hooks', []):
                if not isinstance(hook, dict):
                    continue
                command = hook.get('command', '')
                if marker in command:
                    return True
    return False

def create_metadata(self) -> Dict[str, any]:
    """创建用于识别安装来源的 _metadata。"""
    return {
        "installer": "claude-notifier-pypi",
        "api_version": "2.0",
        "installed_at": str(os.times()),
        "hook_script": str(self.hook_script_path),
        "config_dir": str(self.notifier_config_dir)
    }
```

- [ ] **Step 4: 调整 create_hooks_config 仅返回 hooks 字段**

原 `create_hooks_config` 返回 `{ "hooks": {...}, "_metadata": {...} }`。改为仅返回 hooks 字典。

```python
def create_hooks_config(self) -> Dict[str, any]:
    """创建 hooks 配置（仅 hooks 字段的值）。"""
    py = sys.executable
    py_quoted = f'"{py}"' if (os.name == 'nt' or ' ' in py) else py
    hook_path = str(self.hook_script_path)
    hook_quoted = f'"{hook_path}"' if (os.name == 'nt' or ' ' in hook_path) else hook_path
    base_command = f"{py_quoted} {hook_quoted}"

    return {
        "PreToolUse": [
            {
                "matcher": "Bash|Edit|Write|MultiEdit|DeleteFile|NotebookEdit",
                "hooks": [{"type": "command", "command": base_command}]
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Bash|Task",
                "hooks": [{"type": "command", "command": base_command}]
            }
        ],
        "Stop": [
            {
                "hooks": [{"type": "command", "command": base_command}]
            }
        ],
        "Notification": [
            {
                "matcher": "permission_prompt|idle_prompt",
                "hooks": [{"type": "command", "command": base_command}]
            }
        ]
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_hooks_installer.py::TestIsNotifierManaged -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/claude_notifier/hooks/installer.py tests/test_hooks_installer.py
git commit -m "$(cat <<'EOF'
feat(hooks): 添加 hooks 来源识别与 metadata 生成

is_notifier_managed 通过 _metadata 或 command 内容识别本工具安装的 hooks。
create_hooks_config 现在仅返回 hooks 字段值。

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 实现 install_hooks 的安全写入逻辑

**Files:**
- Modify: `src/claude_notifier/hooks/installer.py`
- Test: `tests/test_hooks_installer.py`

**Interfaces:**
- Consumes: `read_settings()`, `backup_settings()`, `is_notifier_managed()`, `create_hooks_config()`, `create_metadata()`, `write_settings()`。
- Produces:
  - `install_hooks(force: bool = False) -> Tuple[bool, str]` 更新后的完整行为。
  - `migrate_legacy_hooks_file() -> Optional[str]` — 迁移旧文件并返回备份路径或 None。

- [ ] **Step 1: 写失败测试覆盖安装场景**

```python
class TestInstallHooks:
    def _installer(self, tmp_home: Path):
        with patch.object(Path, 'home', return_value=tmp_home):
            return ClaudeHookInstaller()

    def test_install_creates_settings_when_missing(self, tmp_path):
        installer = self._installer(tmp_path)
        with patch.object(installer, 'detect_claude_code', return_value=(True, '/usr/bin/claude')):
            success, message = installer.install_hooks()
        assert success is True
        assert installer.settings_file.exists()
        settings = installer.read_settings()
        assert 'hooks' in settings
        assert '_metadata' in settings
        assert settings['_metadata']['installer'] == 'claude-notifier-pypi'

    def test_install_preserves_other_settings(self, tmp_path):
        installer = self._installer(tmp_path)
        installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
        original = {"model": "opus[1m]", "language": "中文", "env": {"FOO": "bar"}}
        installer.write_settings(original)

        with patch.object(installer, 'detect_claude_code', return_value=(True, '/usr/bin/claude')):
            success, _ = installer.install_hooks()

        assert success is True
        settings = installer.read_settings()
        assert settings['model'] == 'opus[1m]'
        assert settings['language'] == '中文'
        assert settings['env']['FOO'] == 'bar'
        assert 'hooks' in settings

    def test_install_replaces_notifier_hooks(self, tmp_path):
        installer = self._installer(tmp_path)
        installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
        old_hooks = {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "old_python claude_hook.py"}]}]}
        installer.write_settings({"hooks": old_hooks, "_metadata": {"installer": "claude-notifier-pypi"}})

        with patch.object(installer, 'detect_claude_code', return_value=(True, '/usr/bin/claude')):
            success, _ = installer.install_hooks()

        assert success is True
        settings = installer.read_settings()
        assert settings['hooks']['PreToolUse'][0]['matcher'] == "Bash|Edit|Write|MultiEdit|DeleteFile|NotebookEdit"

    def test_install_refuses_foreign_hooks_without_force(self, tmp_path):
        installer = self._installer(tmp_path)
        installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
        foreign = {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "/other/hook"}]}]}}
        installer.write_settings(foreign)

        with patch.object(installer, 'detect_claude_code', return_value=(True, '/usr/bin/claude')):
            success, message = installer.install_hooks(force=False)

        assert success is False
        assert 'force' in message.lower() or 'force' in message

    def test_install_replaces_foreign_hooks_with_force(self, tmp_path):
        installer = self._installer(tmp_path)
        installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
        foreign = {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "/other/hook"}]}]}, "model": "kimi"}
        installer.write_settings(foreign)

        with patch.object(installer, 'detect_claude_code', return_value=(True, '/usr/bin/claude')):
            success, _ = installer.install_hooks(force=True)

        assert success is True
        settings = installer.read_settings()
        assert 'hooks' in settings
        assert settings['model'] == 'kimi'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_hooks_installer.py::TestInstallHooks -v`
Expected: 部分失败 — install_hooks 仍使用旧 hooks.json 逻辑。

- [ ] **Step 3: 重写 install_hooks 方法**

```python
def install_hooks(self, force: bool = False) -> Tuple[bool, str]:
    """安装钩子配置到 ~/.claude/settings.json。"""
    try:
        # 1. 检测 Claude Code
        claude_detected, claude_location = self.detect_claude_code()
        if not claude_detected:
            return False, "❌ 未检测到Claude Code安装，请先安装Claude Code"

        print(f"✅ 检测到Claude Code: {claude_location}")

        # 2. 创建配置目录
        self.claude_config_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 配置目录: {self.claude_config_dir}")

        # 3. 读取当前 settings.json 并备份
        settings = self.read_settings()
        backup_path = self.backup_settings()
        if backup_path:
            print(f"📄 已备份现有配置: {backup_path}")

        # 4. 判断是否已有 hooks 以及是否由本工具管理
        existing_hooks = settings.get('hooks')
        if existing_hooks:
            if not self.is_notifier_managed(settings) and not force:
                return False, "❌ 检测到非本工具安装的 hooks，请使用 --force 强制替换，或先手动备份"

        # 5. 写入 hooks 与 metadata
        settings['hooks'] = self.create_hooks_config()
        settings['_metadata'] = self.create_metadata()

        self.write_settings(settings)
        print(f"✅ 钩子配置已安装: {self.settings_file}")

        # 6. 迁移旧 hooks.json
        migrated = self.migrate_legacy_hooks_file()
        if migrated:
            print(f"🗑️  已迁移旧 hooks.json: {migrated}")

        # 7. 验证
        if self.verify_installation():
            return True, "🎉 Claude Code钩子安装成功！"
        else:
            return False, "⚠️ 钩子配置可能存在问题"

    except Exception as e:
        self.logger.error(f"安装钩子失败: {e}")
        return False, f"❌ 安装失败: {str(e)}"
```

- [ ] **Step 4: 实现 migrate_legacy_hooks_file**

```python
def migrate_legacy_hooks_file(self) -> Optional[str]:
    """迁移旧路径 hooks.json：若由本工具创建则备份并删除，否则返回 None。"""
    if not self.legacy_hooks_file.exists():
        return None

    try:
        with open(self.legacy_hooks_file, 'r', encoding='utf-8') as f:
            legacy_config = json.load(f)
    except Exception as e:
        self.logger.warning(f"读取旧 hooks.json 失败: {e}，跳过迁移")
        return None

    if not self.is_notifier_managed(legacy_config):
        self.logger.info("旧 hooks.json 不是由本工具创建，保留不删除")
        return None

    # 备份旧文件
    from datetime import datetime
    backup_name = f"hooks.json.{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup"
    backup_path = self.legacy_hooks_file.parent / backup_name
    try:
        import shutil
        shutil.copy2(self.legacy_hooks_file, backup_path)
        self.legacy_hooks_file.unlink()
        self.logger.info(f"已迁移旧 hooks.json，备份: {backup_path}")
        return str(backup_path)
    except Exception as e:
        self.logger.error(f"迁移旧 hooks.json 失败: {e}")
        return None
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_hooks_installer.py::TestInstallHooks -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/claude_notifier/hooks/installer.py tests/test_hooks_installer.py
git commit -m "$(cat <<'EOF'
feat(hooks): 实现 install_hooks 写入 ~/.claude/settings.json

支持：不存在时创建、替换本工具 hooks、非本工具 hooks 需 --force、
保留其他 settings 字段、迁移旧 hooks.json。

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 更新 uninstall_hooks / verify_installation / get_installation_status

**Files:**
- Modify: `src/claude_notifier/hooks/installer.py`
- Test: `tests/test_hooks_installer.py`

**Interfaces:**
- Consumes: `read_settings()`, `write_settings()`, `backup_settings()`。
- Produces:
  - `uninstall_hooks() -> Tuple[bool, str]` 改为删除 settings.json 中的 `hooks` 和 `_metadata`。
  - `verify_installation() -> bool` 改为检查 settings.json。
  - `get_installation_status() -> Dict` 改为检查 settings.json。
  - `print_status()` 更新输出路径。

- [ ] **Step 1: 写失败测试**

```python
class TestUninstallHooks:
    def _installer(self, tmp_home: Path):
        with patch.object(Path, 'home', return_value=tmp_home):
            return ClaudeHookInstaller()

    def test_uninstall_removes_hooks_and_metadata(self, tmp_path):
        installer = self._installer(tmp_path)
        installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
        installer.write_settings({
            "model": "opus[1m]",
            "hooks": {"PreToolUse": []},
            "_metadata": {"installer": "claude-notifier-pypi"}
        })

        success, _ = installer.uninstall_hooks()
        assert success is True
        settings = installer.read_settings()
        assert 'hooks' not in settings
        assert '_metadata' not in settings
        assert settings['model'] == 'opus[1m]'

    def test_uninstall_when_settings_missing(self, tmp_path):
        installer = self._installer(tmp_path)
        success, message = installer.uninstall_hooks()
        assert success is True
        assert '无需卸载' in message or '不存在' in message


class TestVerifyInstallation:
    def _installer(self, tmp_home: Path):
        with patch.object(Path, 'home', return_value=tmp_home):
            return ClaudeHookInstaller()

    def test_verify_passes_with_valid_hooks(self, tmp_path):
        installer = self._installer(tmp_path)
        installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
        hooks = installer.create_hooks_config()
        installer.write_settings({"hooks": hooks})
        assert installer.verify_installation() is True

    def test_verify_fails_when_hooks_missing(self, tmp_path):
        installer = self._installer(tmp_path)
        installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
        installer.write_settings({"model": "opus[1m]"})
        assert installer.verify_installation() is False


class TestGetInstallationStatus:
    def _installer(self, tmp_home: Path):
        with patch.object(Path, 'home', return_value=tmp_home):
            return ClaudeHookInstaller()

    def test_status_reports_installed_hooks(self, tmp_path):
        installer = self._installer(tmp_path)
        installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
        hooks = installer.create_hooks_config()
        installer.write_settings({"hooks": hooks})

        status = installer.get_installation_status()
        assert status['hooks_installed'] is True
        assert status['hooks_file'] == str(installer.settings_file)
        assert 'PreToolUse' in status['enabled_hooks']

    def test_status_reports_not_installed(self, tmp_path):
        installer = self._installer(tmp_path)
        status = installer.get_installation_status()
        assert status['hooks_installed'] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_hooks_installer.py::TestUninstallHooks tests/test_hooks_installer.py::TestVerifyInstallation tests/test_hooks_installer.py::TestGetInstallationStatus -v`
Expected: FAIL — 旧方法仍检查 hooks.json。

- [ ] **Step 3: 更新 uninstall_hooks**

```python
def uninstall_hooks(self) -> Tuple[bool, str]:
    """从 ~/.claude/settings.json 中卸载钩子配置。"""
    try:
        if not self.settings_file.exists():
            return True, "钩子配置不存在，无需卸载"

        # 备份
        backup_path = self.backup_settings()

        settings = self.read_settings()
        modified = False

        if 'hooks' in settings:
            del settings['hooks']
            modified = True
        if '_metadata' in settings:
            del settings['_metadata']
            modified = True

        if modified:
            self.write_settings(settings)

        message = "✅ Claude Code钩子已卸载"
        if backup_path:
            message += f"，配置已备份到: {backup_path}"

        return True, message

    except Exception as e:
        return False, f"❌ 卸载失败: {str(e)}"
```

- [ ] **Step 4: 更新 verify_installation**

```python
def verify_installation(self) -> bool:
    """验证 ~/.claude/settings.json 中的钩子配置。"""
    try:
        if not self.settings_file.exists():
            return False

        settings = self.read_settings()
        hooks = settings.get('hooks', {})

        required_hooks = ['PreToolUse', 'Stop']
        for hook_name in required_hooks:
            if hook_name not in hooks:
                self.logger.error(f"缺少必要钩子: {hook_name}")
                return False
            hook_list = hooks[hook_name]
            if not isinstance(hook_list, list) or len(hook_list) == 0:
                self.logger.warning(f"钩子配置无效: {hook_name}")
                return False

        if not self.hook_script_path.exists():
            self.logger.error(f"钩子脚本不存在: {self.hook_script_path}")
            return False

        print("✅ 钩子配置验证通过")
        return True

    except Exception as e:
        self.logger.error(f"验证钩子安装失败: {e}")
        return False
```

- [ ] **Step 5: 更新 get_installation_status 与 print_status**

```python
def get_installation_status(self) -> Dict:
    """获取基于 ~/.claude/settings.json 的安装状态。"""
    status = {
        'claude_detected': False,
        'claude_location': None,
        'hooks_installed': False,
        'hooks_file': str(self.settings_file),
        'hooks_valid': False,
        'hook_script_exists': self.hook_script_path.exists(),
        'enabled_hooks': []
    }

    status['claude_detected'], status['claude_location'] = self.detect_claude_code()

    if self.settings_file.exists():
        try:
            settings = self.read_settings()
            hooks = settings.get('hooks', {})

            if hooks:
                status['hooks_installed'] = True
                status['hooks_valid'] = True
                for hook_name, hook_list in hooks.items():
                    if isinstance(hook_list, list) and len(hook_list) > 0:
                        status['enabled_hooks'].append(hook_name)
        except Exception as e:
            status['hooks_valid'] = False
            status['error'] = str(e)

    return status
```

`print_status()` 中所有 `self.hooks_file` 引用改为 `self.settings_file`，输出文案改为 `settings.json`。例如：

```python
if status['hooks_installed']:
    if status['hooks_valid']:
        print(f"✅ 钩子配置: {self.settings_file}")
    else:
        print(f"❌ 钩子配置: 格式错误 - {status.get('error', '未知错误')}")
else:
    print("❌ 钩子配置: 未安装")
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/test_hooks_installer.py -v`
Expected: PASS（Task 1-4 全部测试）

- [ ] **Step 7: 提交**

```bash
git add src/claude_notifier/hooks/installer.py tests/test_hooks_installer.py
git commit -m "$(cat <<'EOF'
feat(hooks): 卸载、验证、状态检查全部迁移到 ~/.claude/settings.json

uninstall_hooks 仅删除 hooks 和 _metadata；verify 与 status 检查 settings.json；
print_status 更新输出路径。

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 更新文档中的路径示例

**Files:**
- Modify: `docs/quickstart.md:275`
- Modify: `docs/quickstart_en.md:271`（已正确，但需检查是否还有其他旧引用）

**Interfaces:**
- 无代码接口，仅文档文案。

- [ ] **Step 1: 定位需要修改的行**

Run: `grep -n "hooks.json\|~/.config/claude" docs/quickstart.md docs/quickstart_en.md`
Expected: 在 `docs/quickstart.md` 中找到 `cat ~/.config/claude/hooks.json`。

- [ ] **Step 2: 修改中文文档**

将 `docs/quickstart.md` 中的：

```bash
cat ~/.config/claude/hooks.json
```

改为：

```bash
cat ~/.claude/settings.json | jq '.hooks'
```

- [ ] **Step 3: 检查英文文档**

若 `docs/quickstart_en.md` 中路径已是 `~/.claude/settings.json` 则无需修改。若仍有旧引用，同步修改。

- [ ] **Step 4: 提交**

```bash
git add docs/quickstart.md docs/quickstart_en.md
git commit -m "$(cat <<'EOF'
docs: 更新钩子配置检查路径为 ~/.claude/settings.json

统一使用 `cat ~/.claude/settings.json | jq '.hooks'` 示例。

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: 全量回归测试

**Files:**
- 运行整个测试套件确认无回归。

- [ ] **Step 1: 运行 hooks installer 测试**

Run: `pytest tests/test_hooks_installer.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行 CLI 相关测试**

Run: `pytest tests/test_cli.py -v`
Expected: 无新增失败（install_hooks 接口签名未变）。

- [ ] **Step 3: 运行全量测试**

Run: `python tests/run_all_tests.py` 或 `pytest tests/`
Expected: 覆盖率不降低，无新增失败。

- [ ] **Step 4: 手动验证（可选但强烈建议）**

在临时 HOME 下执行：

```bash
export HOME=/tmp/test-claude-notifier-home
mkdir -p $HOME/.claude
mkdir -p $HOME/.config/claude
# 模拟旧 hooks.json
echo '{"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "python claude_hook.py"}]}]}}' > $HOME/.config/claude/hooks.json
python -m claude_notifier.cli.main hooks install --force
python -m claude_notifier.cli.main hooks status
python -m claude_notifier.cli.main hooks verify
python -m claude_notifier.cli.main hooks uninstall
python -m claude_notifier.cli.main hooks status
```

验证：
- `~/.claude/settings.json` 包含正确 hooks。
- 旧 `~/.config/claude/hooks.json` 已被备份删除。
- 卸载后 settings.json 中无 hooks/_metadata。

- [ ] **Step 5: 提交（如仅有测试数据清理）**

若回归测试发现小问题，修复后提交；若无问题，此步骤可跳过。

---

## Spec Coverage Check

| 设计文档章节 | 覆盖任务 |
|---|---|
| 2.1 组件划分 | Task 1-4 |
| 2.2 目标路径变更 | Task 1, 3, 4 |
| 2.3 配置结构 | Task 2, 3 |
| 3.1 安装流程 | Task 3 |
| 3.2 卸载流程 | Task 4 |
| 3.3 状态检查流程 | Task 4 |
| 4.1 识别算法 | Task 2 |
| 4.2 旧 hooks.json 识别 | Task 3 |
| 5. 错误处理 | Task 1-4 的异常分支 |
| 6. CLI 与文档联动 | Task 5 |
| 7. 测试策略 | Task 1-6 |
| 8. 兼容性说明 | Task 3 的迁移逻辑 |

## Placeholder Scan

- 无 TBD/TODO。
- 所有步骤包含具体代码与命令。
- 所有方法签名与类型一致。

## Type Consistency

- `install_hooks(force: bool = False) -> Tuple[bool, str]` 保持与现有 CLI 调用兼容。
- `uninstall_hooks() -> Tuple[bool, str]` 保持兼容。
- `verify_installation() -> bool` 保持兼容。
- `get_installation_status() -> Dict` 返回字段名与旧版保持一致，仅 `hooks_file` 值变为 settings.json 路径。
