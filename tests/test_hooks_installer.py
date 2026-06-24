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


class TestClaudeHookInstallerSettings:
    def test_read_settings_file_not_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(Path, 'home', return_value=home):
                installer = ClaudeHookInstaller()
                assert installer.read_settings() == {}

    def test_read_settings_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(Path, 'home', return_value=home):
                installer = ClaudeHookInstaller()
                installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
                installer.settings_file.write_text('')
                assert installer.read_settings() == {}

    def test_read_settings_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(Path, 'home', return_value=home):
                installer = ClaudeHookInstaller()
                installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
                installer.settings_file.write_text('{"hooks": {"PreToolUse": []}}')
                assert installer.read_settings() == {"hooks": {"PreToolUse": []}}

    def test_write_settings_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(Path, 'home', return_value=home):
                installer = ClaudeHookInstaller()
                installer.write_settings({"hooks": {"PreToolUse": []}})
                assert installer.settings_file.exists()
                content = json.loads(installer.settings_file.read_text())
                assert content == {"hooks": {"PreToolUse": []}}

    def test_write_settings_indent_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(Path, 'home', return_value=home):
                installer = ClaudeHookInstaller()
                installer.write_settings({"a": 1})
                text = installer.settings_file.read_text()
                # 验证缩进为2个空格
                assert '  "a": 1' in text

    def test_backup_settings_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(Path, 'home', return_value=home):
                installer = ClaudeHookInstaller()
                assert installer.backup_settings() is None

    def test_backup_settings_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(Path, 'home', return_value=home):
                installer = ClaudeHookInstaller()
                installer.claude_config_dir.mkdir(parents=True, exist_ok=True)
                installer.settings_file.write_text('{"test": true}')
                backup_path = installer.backup_settings()
                assert backup_path is not None
                assert backup_path.endswith('.backup')
                assert Path(backup_path).exists()
                assert json.loads(Path(backup_path).read_text()) == {"test": True}


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


class TestCreateMetadata:
    def test_metadata_fields(self, tmp_path):
        with patch.object(Path, 'home', return_value=tmp_path):
            installer = ClaudeHookInstaller()
            metadata = installer.create_metadata()
            assert metadata["installer"] == "claude-notifier-pypi"
            assert metadata["api_version"] == "2.0"
            assert "installed_at" in metadata
            assert "hook_script" in metadata
            assert "config_dir" in metadata


class TestCreateHooksConfig:
    def test_returns_only_hooks_field(self, tmp_path):
        with patch.object(Path, 'home', return_value=tmp_path):
            installer = ClaudeHookInstaller()
            config = installer.create_hooks_config()
            assert "hooks" not in config
            assert "_metadata" not in config
            assert "PreToolUse" in config
            assert "PostToolUse" in config
            assert "Stop" in config
            assert "Notification" in config

    def test_hook_command_contains_script(self, tmp_path):
        with patch.object(Path, 'home', return_value=tmp_path):
            installer = ClaudeHookInstaller()
            config = installer.create_hooks_config()
            pre_tool = config["PreToolUse"][0]
            command = pre_tool["hooks"][0]["command"]
            assert "claude_hook.py" in command
