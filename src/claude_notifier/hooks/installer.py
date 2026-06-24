#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Claude Code钩子安装器 - PyPI版本
为PyPI用户提供自动钩子配置功能
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import logging

class ClaudeHookInstaller:
    """Claude Code钩子安装器"""
    
    def __init__(self):
        self.home_dir = Path.home()
        self.claude_config_dir = self.home_dir / '.claude'
        self.settings_file = self.claude_config_dir / 'settings.json'
        self.legacy_hooks_file = self.home_dir / '.config' / 'claude' / 'hooks.json'
        self.notifier_config_dir = self.home_dir / '.claude-notifier'
        self.logger = logging.getLogger(__name__)

        # 保留旧路径兼容（只读）
        self.hooks_file = self.legacy_hooks_file

        # 获取钩子脚本路径
        self.hook_script_path = Path(__file__).parent / 'claude_hook.py'
        
    def detect_claude_code(self) -> Tuple[bool, Optional[str]]:
        """检测Claude Code安装"""
        # 检查常见的Claude Code安装位置
        possible_locations = [
            'claude',
            'claude-code',
            '/usr/local/bin/claude',
            '/opt/homebrew/bin/claude',
            str(self.home_dir / '.local/bin/claude'),
        ]
        
        for location in possible_locations:
            if shutil.which(location):
                return True, location
        
        # 检查Claude配置目录
        if self.claude_config_dir.exists():
            return True, str(self.claude_config_dir)
        
        return False, None
    
    def backup_existing_hooks(self) -> Optional[str]:
        """备份现有钩子配置"""
        if not self.hooks_file.exists():
            return None
        
        from datetime import datetime
        backup_name = f"hooks.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.hooks_file.parent / backup_name
        
        try:
            shutil.copy2(self.hooks_file, backup_path)
            self.logger.info(f"已备份现有钩子配置到: {backup_path}")
            return str(backup_path)
        except Exception as e:
            self.logger.error(f"备份钩子配置失败: {e}")
            return None
    
    def create_hooks_config(self) -> Dict[str, Any]:
        """
        创建钩子配置（仅 hooks 字段的值）

        使用 Claude Code CLI 最新版本的 hooks API 格式：
        - PreToolUse: 工具使用前触发（用于敏感操作检测）
        - PostToolUse: 工具使用后触发
        - Stop: Claude 停止工作时触发（任务完成通知）
        - Notification: 通知事件（权限请求、空闲提示）

        数据通过 stdin 以 JSON 格式传递，响应通过 stdout 返回 JSON
        """
        # 统一使用当前 Python 解释器
        py = sys.executable
        py_quoted = f'"{py}"' if (os.name == 'nt' or ' ' in py) else py
        hook_path = str(self.hook_script_path)
        hook_quoted = f'"{hook_path}"' if (os.name == 'nt' or ' ' in hook_path) else hook_path

        # 基础命令（新版 API 通过 stdin 传递数据，无需命令行参数）
        base_command = f"{py_quoted} {hook_quoted}"

        return {
            # PreToolUse: 工具使用前触发，用于敏感操作检测
            "PreToolUse": [
                {
                    # 匹配敏感工具：Bash命令、文件编辑、文件写入、文件删除等
                    "matcher": "Bash|Edit|Write|MultiEdit|DeleteFile|NotebookEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": base_command
                        }
                    ]
                }
            ],
            # PostToolUse: 工具使用后触发（可用于错误检测）
            "PostToolUse": [
                {
                    # 匹配可能产生错误的工具
                    "matcher": "Bash|Task",
                    "hooks": [
                        {
                            "type": "command",
                            "command": base_command
                        }
                    ]
                }
            ],
            # Stop: Claude 停止工作时触发（任务完成通知）
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": base_command
                        }
                    ]
                }
            ],
            # Notification: 权限请求和空闲提示
            "Notification": [
                {
                    # 匹配权限请求和空闲提示
                    "matcher": "permission_prompt|idle_prompt",
                    "hooks": [
                        {
                            "type": "command",
                            "command": base_command
                        }
                    ]
                }
            ]
        }

    def create_metadata(self) -> Dict[str, Any]:
        """创建用于识别安装来源的 _metadata。"""
        return {
            "installer": "claude-notifier-pypi",
            "api_version": "2.0",
            "installed_at": str(os.times()),
            "hook_script": str(self.hook_script_path),
            "config_dir": str(self.notifier_config_dir)
        }

    def is_notifier_managed(self, settings: Dict[str, Any]) -> bool:
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
    
    def read_settings(self) -> Dict[str, Any]:
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

    def write_settings(self, settings: Dict[str, Any]) -> None:
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
            shutil.copy2(self.legacy_hooks_file, backup_path)
            self.legacy_hooks_file.unlink()
            self.logger.info(f"已迁移旧 hooks.json，备份: {backup_path}")
            return str(backup_path)
        except Exception as e:
            self.logger.error(f"迁移旧 hooks.json 失败: {e}")
            return None

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
    
    def verify_installation(self) -> bool:
        """验证钩子安装"""
        try:
            # 检查配置文件
            if not self.settings_file.exists():
                return False

            # 检查配置格式
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 检查必要的钩子（新版 API 格式）
            required_hooks = ['PreToolUse', 'Stop']
            hooks = config.get('hooks', {})

            for hook_name in required_hooks:
                if hook_name not in hooks:
                    self.logger.error(f"缺少必要钩子: {hook_name}")
                    return False

                # 新版 API 格式：hooks 的值是数组
                hook_list = hooks[hook_name]
                if not isinstance(hook_list, list) or len(hook_list) == 0:
                    self.logger.warning(f"钩子配置无效: {hook_name}")
                    return False

            # 检查钩子脚本
            if not self.hook_script_path.exists():
                self.logger.error(f"钩子脚本不存在: {self.hook_script_path}")
                return False

            print("✅ 钩子配置验证通过")
            return True

        except Exception as e:
            self.logger.error(f"验证钩子安装失败: {e}")
            return False
    
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

    def print_status(self):
        """打印安装状态"""
        status = self.get_installation_status()

        print("📊 Claude Code钩子状态")
        print("=" * 40)

        # Claude Code检测
        if status['claude_detected']:
            print(f"✅ Claude Code: {status['claude_location']}")
        else:
            print("❌ Claude Code: 未检测到")

        # 钩子脚本
        if status['hook_script_exists']:
            print(f"✅ 钩子脚本: {self.hook_script_path}")
        else:
            print(f"❌ 钩子脚本: 未找到")

        # 钩子配置
        if status['hooks_installed']:
            if status['hooks_valid']:
                print(f"✅ 钩子配置: {self.settings_file}")
                if status['enabled_hooks']:
                    print(f"🔗 已启用钩子: {', '.join(status['enabled_hooks'])}")
                else:
                    print("⚠️ 没有启用的钩子")
            else:
                print(f"❌ 钩子配置: 格式错误 - {status.get('error', '未知错误')}")
        else:
            print("❌ 钩子配置: 未安装")

        # 总体状态
        if (status['claude_detected'] and
            status['hook_script_exists'] and
            status['hooks_installed'] and
            status['hooks_valid'] and
            status['enabled_hooks']):
            print("\n🎉 钩子系统完全就绪！")
        else:
            print("\n⚠️ 钩子系统需要配置")
            print("运行 'claude-notifier hooks install' 进行安装")

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Claude Code钩子安装器')
    parser.add_argument('action', choices=['install', 'uninstall', 'status', 'verify'],
                       help='操作类型')
    parser.add_argument('--force', action='store_true',
                       help='强制执行（跳过确认）')
    
    args = parser.parse_args()
    
    installer = ClaudeHookInstaller()
    
    if args.action == 'install':
        success, message = installer.install_hooks(force=args.force)
        print(message)
        sys.exit(0 if success else 1)
    
    elif args.action == 'uninstall':
        success, message = installer.uninstall_hooks()
        print(message)
        sys.exit(0 if success else 1)
    
    elif args.action == 'status':
        installer.print_status()
    
    elif args.action == 'verify':
        if installer.verify_installation():
            print("✅ 钩子配置验证成功")
            sys.exit(0)
        else:
            print("❌ 钩子配置验证失败")
            sys.exit(1)

if __name__ == "__main__":
    main()