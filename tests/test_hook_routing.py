#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Claude Hook 事件路由集成测试

模拟 Claude Code 真实调用 claude_hook.py 的方式：
- 通过 stdin 传入 JSON（含 hook_event_name）
- 不设置 CLAUDE_HOOK_EVENT 环境变量
- 期望退出码 0 且 stdout 输出有效 JSON 响应

回归用例：曾因脚本依赖 CLAUDE_HOOK_EVENT 环境变量导致
"Stop hook error: Failed with non-blocking status code" 报错。
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HOOK_SCRIPT = Path(__file__).parent.parent / "src" / "claude_notifier" / "hooks" / "claude_hook.py"


def _run_hook(stdin_payload: dict, extra_env: dict = None):
    """以 Claude Code 的调用方式运行 hook 脚本。

    使用独立的临时 HOME，确保 Notifier 读不到真实配置（0 渠道），
    从而不会触发真实通知发送。
    """
    tmp_home = tempfile.mkdtemp(prefix="hook_test_home_")
    env = {
        "HOME": tmp_home,
        "PATH": os.environ.get("PATH", ""),
    }
    # 显式确保未注入旧版环境变量
    env.pop("CLAUDE_HOOK_EVENT", None)
    if extra_env:
        env.update(extra_env)

    proc = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(stdin_payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc


def _parse_stdout_json(proc):
    """stdout 可能含多行，取最后一行非空内容作为 JSON 响应。"""
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines, f"stdout 为空。stderr={proc.stderr!r}"
    return json.loads(lines[-1])


class TestHookRoutingViaStdin:
    """Claude Code 通过 stdin JSON（hook_event_name）驱动 hook 路由。"""

    def test_stop_event_exits_zero(self):
        proc = _run_hook({
            "session_id": "s1",
            "transcript_path": "/tmp/t.json",
            "cwd": "/tmp",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        })
        assert proc.returncode == 0, f"退出码非0\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        assert "Usage" not in proc.stdout

    def test_stop_event_emits_continue_json(self):
        proc = _run_hook({
            "session_id": "s1",
            "transcript_path": "/tmp/t.json",
            "cwd": "/tmp",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        })
        result = _parse_stdout_json(proc)
        assert result.get("continue") is True

    def test_notification_permission_prompt_exits_zero(self):
        proc = _run_hook({
            "session_id": "s1",
            "transcript_path": "/tmp/t.json",
            "cwd": "/tmp",
            "hook_event_name": "Notification",
            "notification_type": "permission_prompt",
            "message": "Allow Bash?",
        })
        assert proc.returncode == 0, f"退出码非0\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        result = _parse_stdout_json(proc)
        assert result.get("continue") is True

    def test_subagentstop_routes_like_stop(self):
        proc = _run_hook({
            "session_id": "s1",
            "transcript_path": "/tmp/t.json",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStop",
        })
        assert proc.returncode == 0, f"退出码非0\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
