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
