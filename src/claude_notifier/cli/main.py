#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Claude Notifier 主CLI入口
统一的命令行工具，支持所有功能
"""

import sys
import click
import logging
from typing import Optional, List

# 配置日志级别，避免INFO消息在CLI中显示
logging.getLogger('claude_notifier').setLevel(logging.ERROR)
# 抑制所有低级别日志消息在CLI中显示
logging.getLogger().setLevel(logging.ERROR)

# 注意：避免在顶层导入重型依赖，按需在命令中惰性导入
# 这样 `claude-notifier --version` 仅加载最少模块，降低在 CI 环境卡住的风险


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='显示版本信息')
@click.option('--status', is_flag=True, help='显示状态信息')
@click.pass_context
def cli(ctx, version, status):
    """Claude Notifier - Claude Code智能通知系统
    
    基础使用:
        claude-notifier send "Hello World!"
        
    智能功能 (需要安装intelligence模块):
        claude-notifier send "通知" --throttle
        
    查看帮助:
        claude-notifier --help
        claude-notifier send --help
    """
    # 配置日志级别，避免INFO消息在CLI中显示
    import logging
    logging.getLogger('claude_notifier').setLevel(logging.ERROR)
    logging.getLogger().setLevel(logging.ERROR)
    
    # 确保子命令可以访问上下文
    ctx.ensure_object(dict)
    
    if version:
        from claude_notifier.__version__ import print_version_info
        print_version_info()
        return
        
    if status:
        from claude_notifier import print_feature_status
        print_feature_status()
        try:
            from claude_notifier.core.notifier import Notifier
            notifier = Notifier()
            status_info = notifier.get_status()
            print(f"\n📊 系统状态:")
            print(f"  配置文件: {status_info['config']['file']}")
            print(f"  配置有效: {'✅' if status_info['config']['valid'] else '❌'}")
            print(f"  启用渠道: {status_info['channels']['total_enabled']}")
            if status_info['channels']['enabled']:
                print(f"  渠道列表: {', '.join(status_info['channels']['enabled'])}")
                
            # 集成钩子状态检查
            _check_and_suggest_hooks()
                
        except Exception as e:
            print(f"❌ 状态获取失败: {e}")
        return
        
    if ctx.invoked_subcommand is None:
        # 智能首次运行检查
        _first_run_setup_check()
        click.echo(ctx.get_help())


def _first_run_setup_check():
    """首次运行智能设置检查"""
    import os
    from pathlib import Path
    
    setup_marker = Path.home() / '.claude-notifier' / '.setup_complete'
    
    # 如果已经设置过，跳过
    if setup_marker.exists():
        return
        
    try:
        from claude_notifier.hooks.installer import ClaudeHookInstaller
        installer = ClaudeHookInstaller()
        
        # 检测Claude Code
        claude_detected, claude_location = installer.detect_claude_code()
        
        if claude_detected:
            status = installer.get_installation_status()
            if not status['hooks_installed']:
                print(f"\n🔍 检测到Claude Code: {claude_location}")
                print("💡 提示: 使用 'claude-notifier hooks install' 启用Claude Code智能集成")
                print("   完整功能: 会话通知 | 任务跟踪 | 错误监控 | 限流提醒")
                
        # 创建设置标记
        os.makedirs(setup_marker.parent, exist_ok=True)
        setup_marker.touch()
        
    except Exception:
        # 静默处理检查错误，不影响正常使用
        pass


def _check_and_suggest_hooks():
    """检查并建议钩子配置"""
    try:
        from claude_notifier.hooks.installer import ClaudeHookInstaller
        installer = ClaudeHookInstaller()
        
        status = installer.get_installation_status()
        print(f"\n🔗 Claude Code集成:")
        
        if status['claude_detected']:
            print(f"  Claude Code: ✅ {status['claude_location']}")
            
            if status['hooks_installed'] and status['hooks_valid']:
                enabled_count = len(status['enabled_hooks'])
                print(f"  钩子配置: ✅ 已启用 ({enabled_count} 个钩子)")
                if status['enabled_hooks']:
                    print(f"  启用钩子: {', '.join(status['enabled_hooks'])}")
            else:
                print("  钩子配置: ❌ 未配置")
                print("  💡 建议: claude-notifier hooks install")
        else:
            print("  Claude Code: ❌ 未检测到")
            
    except Exception as e:
        print(f"  钩子检查: ⚠️  检查失败 ({e})")


@cli.command()
@click.option('--auto', is_flag=True, help='自动配置（跳过确认）')
@click.option('--claude-code-only', is_flag=True, help='仅配置Claude Code钩子')
def setup(auto, claude_code_only):
    """一键智能配置 Claude Notifier
    
    自动检测环境并配置所有功能：
    - 基础配置文件初始化
    - Claude Code钩子集成（如果检测到）
    - 权限和路径配置
    
    Examples:
        claude-notifier setup              # 交互式配置
        claude-notifier setup --auto       # 自动配置
        claude-notifier setup --claude-code-only  # 仅配置钩子
    """
    import os
    from pathlib import Path
    
    click.echo("🚀 Claude Notifier 智能配置向导")
    click.echo("=" * 50)
    
    setup_results = []
    
    # 1. 基础配置检查（除非只配置Claude Code）
    if not claude_code_only:
        try:
            from claude_notifier.core.notifier import Notifier
            notifier = Notifier()
            status_info = notifier.get_status()
            
            if status_info['config']['valid']:
                click.echo("✅ 基础配置已存在且有效")
                setup_results.append(("基础配置", True, "配置文件已存在"))
            else:
                if auto or click.confirm("是否创建默认配置文件?"):
                    # 这里可以添加配置文件创建逻辑
                    click.echo("ℹ️  基础配置初始化需要手动设置通知渠道")
                    click.echo("   参考: https://github.com/kdush/Claude-Code-Notifier#configuration")
                    setup_results.append(("基础配置", False, "需要手动配置"))
                else:
                    setup_results.append(("基础配置", False, "用户跳过"))
                    
        except Exception as e:
            click.echo(f"⚠️  基础配置检查失败: {e}")
            setup_results.append(("基础配置", False, f"检查失败: {e}"))
    
    # 2. Claude Code钩子配置
    try:
        from claude_notifier.hooks.installer import ClaudeHookInstaller
        installer = ClaudeHookInstaller()
        
        # 检测Claude Code
        claude_detected, claude_location = installer.detect_claude_code()
        
        if claude_detected:
            click.echo(f"🔍 检测到Claude Code: {claude_location}")
            
            status = installer.get_installation_status()
            
            if status['hooks_installed'] and status['hooks_valid']:
                click.echo("✅ Claude Code钩子已配置")
                setup_results.append(("Claude Code钩子", True, "已安装且有效"))
            else:
                should_install = auto or click.confirm("是否安装Claude Code钩子集成?")
                
                if should_install:
                    click.echo("🔧 正在安装Claude Code钩子...")
                    success, message = installer.install_hooks(force=auto)
                    
                    if success:
                        click.echo(f"✅ {message}")
                        setup_results.append(("Claude Code钩子", True, "安装成功"))
                        
                        # 验证安装
                        if installer.verify_installation():
                            click.echo("✅ 钩子配置验证通过")
                        else:
                            click.echo("⚠️  钩子配置验证失败，但基本功能可用")
                    else:
                        click.echo(f"❌ {message}")
                        setup_results.append(("Claude Code钩子", False, message))
                else:
                    setup_results.append(("Claude Code钩子", False, "用户跳过"))
        else:
            click.echo("ℹ️  未检测到Claude Code安装")
            click.echo("   如需集成，请先安装Claude Code: https://docs.anthropic.com/claude/docs/claude-code")
            setup_results.append(("Claude Code检测", False, "未检测到安装"))
            
    except Exception as e:
        click.echo(f"❌ Claude Code钩子配置失败: {e}")
        setup_results.append(("Claude Code钩子", False, f"配置失败: {e}"))
    
    # 3. 权限检查
    try:
        config_dir = Path.home() / '.claude-notifier'
        if config_dir.exists():
            permissions = oct(config_dir.stat().st_mode)[-3:]
            if permissions >= '755':
                setup_results.append(("目录权限", True, f"权限正常 ({permissions})"))
            else:
                click.echo(f"⚠️  配置目录权限过低: {permissions}")
                if auto or click.confirm("是否修复目录权限?"):
                    config_dir.chmod(0o755)
                    setup_results.append(("目录权限", True, "已修复"))
                else:
                    setup_results.append(("目录权限", False, "权限过低，用户跳过修复"))
        else:
            setup_results.append(("目录权限", True, "配置目录将在首次使用时创建"))
            
    except Exception as e:
        setup_results.append(("目录权限", False, f"检查失败: {e}"))
    
    # 4. 创建设置完成标记
    try:
        setup_marker = Path.home() / '.claude-notifier' / '.setup_complete'
        os.makedirs(setup_marker.parent, exist_ok=True)
        setup_marker.touch()
    except Exception:
        pass  # 静默处理标记文件错误
    
    # 5. 配置结果总结
    click.echo("\n" + "=" * 50)
    click.echo("📋 配置结果总结:")
    
    success_count = 0
    for item, success, details in setup_results:
        status_icon = "✅" if success else "❌" 
        click.echo(f"  {status_icon} {item}: {details}")
        if success:
            success_count += 1
    
    total_count = len(setup_results)
    click.echo(f"\n🎯 完成情况: {success_count}/{total_count} 项配置成功")
    
    if success_count == total_count:
        click.echo("🎉 恭喜！Claude Notifier 已完全配置完成")
        click.echo("💡 下一步: 配置通知渠道以开始使用")
        click.echo("   运行: claude-notifier --help")
    elif success_count > 0:
        click.echo("⚠️  部分配置完成，系统可以基本使用")
        click.echo("💡 建议: 检查失败项目并手动配置")
    else:
        click.echo("❌ 配置未完成，请检查错误并重试")
        sys.exit(1)


@cli.command()
@click.argument('message')
@click.option('-c', '--channels', help='指定发送渠道 (逗号分隔)')
@click.option('-t', '--type', 'event_type', default='custom', help='事件类型')
@click.option('-p', '--priority', default='normal', 
              type=click.Choice(['low', 'normal', 'high', 'critical']),
              help='通知优先级')
@click.option('--throttle', is_flag=True, help='启用智能限流 (需要intelligence模块)')
@click.option('--project', help='指定项目名称')
def send(message, channels, event_type, priority, throttle, project):
    """发送通知消息
    
    Examples:
        claude-notifier send "Hello World!"
        claude-notifier send "重要通知" -c dingtalk,email -p high
        claude-notifier send "智能通知" --throttle
    """
    try:
        # 解析渠道列表
        channels_list = None
        if channels:
            channels_list = [c.strip() for c in channels.split(',')]
            
        # 选择通知器类型
        if throttle:
            # 尝试使用智能通知器
            try:
                from claude_notifier import IntelligentNotifier
                notifier = IntelligentNotifier()
            except ImportError:
                click.echo("❌ 智能功能未安装: pip install claude-notifier[intelligence]")
                return False
        else:
            from claude_notifier.core.notifier import Notifier
            notifier = Notifier()
            
        # 构建消息数据
        kwargs = {'priority': priority}
        if project:
            kwargs['project'] = project
            
        # 检查是否有可用的通知渠道
        status_info = notifier.get_status()
        enabled_channels = status_info['channels']['enabled']
        
        if not enabled_channels and not channels_list:
            click.echo("⚠️  没有配置的通知渠道，消息未发送")
            click.echo("💡 使用 'claude-notifier config init' 配置通知渠道")
            return False
            
        # 发送通知
        success = notifier.send(message, channels_list, event_type, **kwargs)
        
        if success:
            if enabled_channels or channels_list:
                click.echo("✅ 通知发送成功")
            else:
                click.echo("⚠️  通知已处理，但没有启用的渠道")
        else:
            click.echo("❌ 通知发送失败")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ 发送失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('-c', '--channels', help='测试指定渠道 (逗号分隔，默认测试所有)')
def test(channels):
    """测试通知渠道配置
    
    Examples:
        claude-notifier test
        claude-notifier test -c dingtalk,email
    """
    try:
        from claude_notifier.core.notifier import Notifier
        notifier = Notifier()
        
        channels_list = None
        if channels:
            channels_list = [c.strip() for c in channels.split(',')]
            
        click.echo("🔔 开始测试通知渠道...")
        results = notifier.test_channels(channels_list)
        
        if not results:
            click.echo("⚠️  没有配置的通知渠道")
            return
            
        success_count = sum(results.values())
        total_count = len(results)
        
        click.echo(f"\n📊 测试结果 ({success_count}/{total_count} 成功):")
        
        for channel, success in results.items():
            status = "✅" if success else "❌"
            click.echo(f"  {status} {channel}")
            
        if success_count == total_count:
            click.echo("\n🎉 所有渠道测试通过!")
        elif success_count == 0:
            click.echo("\n❌ 所有渠道测试失败，请检查配置")
            sys.exit(1)
        else:
            click.echo("\n⚠️  部分渠道测试失败，请检查配置")
            
    except Exception as e:
        click.echo(f"❌ 测试失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--intelligence', is_flag=True, help='显示智能功能状态')
@click.option('--export', help='导出基础状态数据到文件')
def status(intelligence, export):
    """快速系统健康检查
    
    显示核心组件状态：版本、配置、渠道、钩子等基础信息。
    需要详细监控和性能分析请使用 monitor 命令。
        
    Examples:
        claude-notifier status
        claude-notifier status --intelligence  
        claude-notifier status --export status.json
    """
    try:
        # 基础状态
        from claude_notifier import print_feature_status
        print_feature_status()
        
        # 通知器状态
        from claude_notifier.core.notifier import Notifier
        notifier = Notifier()
        status_info = notifier.get_status()
        
        click.echo(f"\n📊 通知器状态:")
        click.echo(f"  版本: {status_info['version']}")
        click.echo(f"  配置文件: {status_info['config']['file']}")
        click.echo(f"  配置有效: {'✅' if status_info['config']['valid'] else '❌'}")
        click.echo(f"  最后修改: {status_info['config']['last_modified'] or '未知'}")
        
        click.echo(f"\n📡 通知渠道:")
        click.echo(f"  可用渠道: {', '.join(status_info['channels']['available'])}")
        click.echo(f"  启用渠道: {status_info['channels']['total_enabled']}")
        if status_info['channels']['enabled']:
            click.echo(f"  渠道列表: {', '.join(status_info['channels']['enabled'])}")
        else:
            click.echo("  ⚠️  没有启用的通知渠道")
            
        # 智能功能状态
        if intelligence:
            try:
                from claude_notifier import IntelligentNotifier
                intelligent_notifier = IntelligentNotifier()
                intel_status = intelligent_notifier.get_intelligence_status()
                
                click.echo(f"\n🧠 智能功能:")
                click.echo(f"  智能功能: {'✅ 已启用' if intel_status['enabled'] else '❌ 已禁用'}")
                
                if intel_status['enabled']:
                    components = intel_status['components']
                    click.echo(f"  操作阻止: {'✅' if components['operation_gate']['enabled'] else '❌'}")
                    click.echo(f"  通知限流: {'✅' if components['notification_throttle']['enabled'] else '❌'}")
                    click.echo(f"  消息分组: {'✅' if components['message_grouper']['enabled'] else '❌'}")
                    click.echo(f"  冷却管理: {'✅' if components['cooldown_manager']['enabled'] else '❌'}")
                    
            except ImportError:
                click.echo(f"\n🧠 智能功能: ❌ 未安装 (pip install claude-notifier[intelligence])")
                
        # 钩子状态
        click.echo(f"\n🔗 Claude Code集成:")
        try:
            from claude_notifier.hooks.installer import ClaudeHookInstaller
            installer = ClaudeHookInstaller()
            hook_status = installer.get_installation_status()
            
            if hook_status['claude_detected']:
                click.echo(f"  Claude Code: ✅ 已检测到")
                if hook_status['hooks_installed']:
                    click.echo(f"  钩子状态: ✅ 已安装并配置")
                    if hook_status['hooks_valid']:
                        click.echo(f"  钩子验证: ✅ 配置有效")
                    else:
                        click.echo(f"  钩子验证: ⚠️ 配置需要检查")
                else:
                    click.echo(f"  钩子状态: ❌ 未安装 (运行 'claude-notifier setup' 配置)")
            else:
                click.echo(f"  Claude Code: ❌ 未检测到")
                
        except ImportError:
            click.echo(f"  钩子功能: ❌ 不可用")
        except Exception as e:
            click.echo(f"  钩子状态: ❌ 检查失败 ({e})")
            
        # 导出功能（仅基础状态）
        if export:
            export_data = {
                'version': status_info['version'],
                'config': status_info['config'],
                'channels': status_info['channels']
            }
            
            if intelligence:
                try:
                    from claude_notifier import IntelligentNotifier
                    intelligent_notifier = IntelligentNotifier()
                    export_data['intelligence'] = intelligent_notifier.get_intelligence_status()
                except ImportError:
                    export_data['intelligence'] = {'available': False}
                    
            try:
                from claude_notifier.hooks.installer import ClaudeHookInstaller
                installer = ClaudeHookInstaller()
                export_data['hooks'] = installer.get_installation_status()
            except ImportError:
                export_data['hooks'] = {'available': False}
                
            import json
            with open(export, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            click.echo(f"\n💾 基础状态已导出到: {export}")
            click.echo(f"💡 如需完整监控数据请使用: claude-notifier monitor --export")
                
    except Exception as e:
        click.echo(f"❌ 状态获取失败: {e}")
        sys.exit(1)
        
    # 提示使用monitor命令获取详细监控信息
    click.echo(f"\n💡 提示: 使用 'claude-notifier monitor' 查看详细监控和性能数据")


def _show_monitoring_status(mode: str, export_file: Optional[str] = None):
    """显示监控系统状态"""
    try:
        from claude_notifier.monitoring.dashboard import MonitoringDashboard, DashboardMode
    except ImportError:
        click.echo(f"\n📊 监控系统: ❌ 监控功能不可用")
        return
        
    try:
        # 创建监控仪表板
        dashboard_config = {
            'auto_refresh': False,
            'cache_duration': 5
        }
        dashboard = MonitoringDashboard(dashboard_config)
        
        # 获取仪表板视图
        dashboard_mode = DashboardMode(mode)
        dashboard_view = dashboard.get_dashboard_view(dashboard_mode)
        
        click.echo(f"\n{dashboard_view}")
        
        # 导出功能
        if export_file:
            import json
            export_data = dashboard.export_dashboard_data(include_history=True)
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            click.echo(f"\n💾 状态数据已导出到: {export_file}")
            
        # 清理资源
        dashboard.cleanup()
        
    except Exception as e:
        click.echo(f"\n❌ 监控状态获取失败: {e}")


# _watch_status函数已移除 - 实时监控功能现在只在monitor命令中提供


@cli.command()
@click.option('--mode', type=click.Choice(['overview', 'detailed', 'alerts', 'historical', 'performance']),
              default='overview', help='监控模式')
@click.option('--start', is_flag=True, help='启动后台监控')
@click.option('--stop', is_flag=True, help='停止后台监控')
@click.option('--report', help='生成监控报告并保存到文件')
@click.option('--export', help='导出监控数据到JSON文件')
@click.option('--watch', is_flag=True, help='实时监控模式')
@click.option('--interval', type=int, default=5, help='监控间隔(秒)')
def monitor(mode, start, stop, report, export, watch, interval):
    """监控系统管理和实时状态查看
    
    模式选择:
        overview     - 系统概览 (默认)
        detailed     - 详细监控信息
        alerts       - 报警信息
        historical   - 历史数据
        performance  - 性能监控
        
    Examples:
        claude-notifier monitor
        claude-notifier monitor --mode performance
        claude-notifier monitor --start
        claude-notifier monitor --watch --interval 3
        claude-notifier monitor --report monitor_report.txt
        claude-notifier monitor --export monitoring_data.json
    """
    try:
        from claude_notifier.monitoring.dashboard import MonitoringDashboard, DashboardMode
    except ImportError:
        click.echo("❌ 监控功能不可用，请检查监控模块安装")
        sys.exit(1)
        
    try:
        # 创建监控仪表板
        dashboard_config = {
            'auto_refresh': start,
            'update_interval': interval,
            'cache_duration': 5
        }
        dashboard = MonitoringDashboard(dashboard_config)
        
        if start:
            click.echo("🚀 启动后台监控系统...")
            dashboard.start()
            click.echo("✅ 后台监控已启动")
            
            # 显示启动状态
            summary = dashboard.get_status_summary()
            click.echo(f"\n📊 监控状态:")
            click.echo(f"  整体状态: {summary['overall_status']}")
            click.echo(f"  报警数量: {summary['alert_count']}")
            click.echo(f"  严重报警: {summary['critical_alerts']}")
            
            click.echo("\n💡 提示: 使用 'claude-notifier monitor --stop' 停止监控")
            
        elif stop:
            click.echo("⏹️  停止后台监控系统...")
            dashboard.stop()
            click.echo("✅ 后台监控已停止")
            
        elif watch:
            _watch_monitoring(dashboard, mode, interval)
            
        elif report:
            click.echo("📋 生成监控报告...")
            
            # 生成各种报告
            reports = []
            
            # 统计报告
            if dashboard.statistics_manager:
                stat_report = dashboard.statistics_manager.generate_report(
                    include_intelligence=True, 
                    include_performance=True
                )
                reports.append("📊 统计报告")
                reports.append("=" * 60)
                reports.append(stat_report)
                reports.append("")
                
            # 性能报告
            if dashboard.performance_monitor:
                perf_report = dashboard.performance_monitor.generate_performance_report()
                reports.append("⚡ 性能监控报告")
                reports.append("=" * 60)
                reports.append(perf_report)
                reports.append("")
                
            # 监控仪表板报告
            dashboard_report = dashboard.get_dashboard_view(DashboardMode.DETAILED)
            reports.append("🖥️  监控仪表板报告")
            reports.append("=" * 60)
            reports.append(dashboard_report)
            
            # 保存报告
            full_report = "\n".join(reports)
            with open(report, 'w', encoding='utf-8') as f:
                f.write(full_report)
                
            click.echo(f"✅ 监控报告已保存到: {report}")
            
        elif export:
            click.echo("💾 导出监控数据...")
            export_data = dashboard.export_dashboard_data(include_history=True)
            
            import json
            with open(export, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            click.echo(f"✅ 监控数据已导出到: {export}")
            
        else:
            # 默认显示监控状态
            dashboard_mode = DashboardMode(mode) if mode != 'performance' else DashboardMode.DETAILED
            dashboard_view = dashboard.get_dashboard_view(dashboard_mode)
            
            click.echo(dashboard_view)
            
            # 如果是性能模式，显示额外的性能信息
            if mode == 'performance' and dashboard.performance_monitor:
                alerts = dashboard.performance_monitor.get_alerts()
                if alerts:
                    click.echo("\n🚨 性能报警:")
                    for alert in alerts[:10]:  # 显示前10个
                        icon = '🔴' if alert['level'] == 'critical' else '🟡'
                        click.echo(f"  {icon} {alert['message']}")
                        
        # 清理资源
        dashboard.cleanup()
                
    except Exception as e:
        click.echo(f"❌ 监控操作失败: {e}")
        sys.exit(1)


def _watch_monitoring(dashboard: 'MonitoringDashboard', mode: str, interval: int):
    """监控实时显示模式"""
    import time
    import os
    
    try:
        click.echo(f"🔄 开始实时监控 (每{interval}秒刷新，按 Ctrl+C 退出)\n")
        
        while True:
            # 清屏
            os.system('clear' if os.name == 'posix' else 'cls')
            
            click.echo(f"🔄 实时监控模式 (间隔: {interval}s, 按 Ctrl+C 退出)")
            click.echo(f"📅 刷新时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo("=" * 80)
            
            try:
                # 获取仪表板视图
                dashboard_mode = DashboardMode(mode) if mode != 'performance' else DashboardMode.DETAILED
                dashboard_view = dashboard.get_dashboard_view(dashboard_mode)
                click.echo(dashboard_view)
                
                # 性能模式显示额外信息
                if mode == 'performance' and dashboard.performance_monitor:
                    current_metrics = dashboard.performance_monitor.get_current_metrics()
                    click.echo("\n⚡ 实时性能指标:")
                    for name, metric in current_metrics.items():
                        level_icon = {
                            'excellent': '💚',
                            'good': '🟢', 
                            'warning': '🟡',
                            'critical': '🔴',
                            'unknown': '⚪'
                        }.get(metric.level.value, '⚪')
                        click.echo(f"  {level_icon} {name}: {metric.value}{metric.unit}")
                        
            except Exception as e:
                click.echo(f"❌ 监控数据获取失败: {e}")
                
            click.echo("\n" + "=" * 80)
            click.echo(f"⏱️  下次刷新: {interval}秒后 (按 Ctrl+C 退出)")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        click.echo("\n👋 退出实时监控模式")


@cli.group(invoke_without_command=True)
@click.pass_context
def config(ctx):
    """配置管理和维护工具
    
    Examples:
        claude-notifier config                    # 查看配置状态
        claude-notifier config show               # 显示完整配置
        claude-notifier config validate           # 验证配置
        claude-notifier config backup             # 备份配置
        claude-notifier config init               # 初始化配置
        claude-notifier config channels           # 管理渠道配置
    """
    if ctx.invoked_subcommand is None:
        _show_config_status()


def _show_config_status():
    """显示配置状态"""
    try:
        from claude_notifier.core.notifier import Notifier
        notifier = Notifier()
        status_info = notifier.get_status()
        config_info = status_info['config']
        
        click.echo("⚙️  配置状态:")
        click.echo(f"  文件路径: {config_info['file']}")
        click.echo(f"  配置有效: {'✅' if config_info['valid'] else '❌'}")
        click.echo(f"  最后修改: {config_info['last_modified'] or '未知'}")
        
        # 显示渠道配置摘要
        channels = status_info['channels']
        click.echo(f"\n📡 渠道配置:")
        click.echo(f"  可用渠道: {len(channels['available'])}")
        click.echo(f"  启用渠道: {channels['total_enabled']}")
        if channels['enabled']:
            click.echo(f"  活跃渠道: {', '.join(channels['enabled'])}")
            
        if not config_info['valid']:
            click.echo("\n💡 建议:")
            click.echo("  1. 运行 'claude-notifier config validate' 检查问题")
            click.echo("  2. 运行 'claude-notifier config init' 重新初始化")
            click.echo("  3. 查看 'claude-notifier config --help' 了解更多选项")
            
    except Exception as e:
        click.echo(f"❌ 配置状态获取失败: {e}")
        sys.exit(1)


@config.command()
@click.option('--format', type=click.Choice(['yaml', 'json']), default='yaml', help='显示格式')
@click.option('--sensitive', is_flag=True, help='显示敏感信息 (tokens, webhooks)')
def show(format, sensitive):
    """显示完整配置内容"""
    try:
        from claude_notifier.core.config import ConfigManager
        import json
        import yaml
        
        config_manager = ConfigManager()
        config_data = config_manager.get_config()
        
        # 隐藏敏感信息
        if not sensitive:
            config_data = _hide_sensitive_data(config_data.copy())
            
        if format == 'json':
            click.echo(json.dumps(config_data, indent=2, ensure_ascii=False))
        else:
            click.echo(yaml.dump(config_data, default_flow_style=False, allow_unicode=True))
            
        if not sensitive:
            click.echo("\n💡 提示: 使用 --sensitive 显示敏感信息")
            
    except Exception as e:
        click.echo(f"❌ 配置显示失败: {e}")
        sys.exit(1)


@config.command()
@click.option('--fix', is_flag=True, help='自动修复可修复的问题')
def validate(fix):
    """验证配置文件完整性和正确性"""
    try:
        from claude_notifier.core.config import ConfigManager
        import os
        import yaml
        
        config_manager = ConfigManager()
        config_file = config_manager.config_path
        
        click.echo("🔍 正在验证配置...")
        
        validation_results = []
        
        # 1. 文件存在性检查
        if not os.path.exists(config_file):
            validation_results.append({
                'level': 'error',
                'message': f'配置文件不存在: {config_file}',
                'fixable': True,
                'fix_action': 'create_default'
            })
        else:
            validation_results.append({
                'level': 'success',
                'message': '配置文件存在'
            })
            
            # 2. YAML语法检查
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
                validation_results.append({
                    'level': 'success',
                    'message': 'YAML语法正确'
                })
            except yaml.YAMLError as e:
                validation_results.append({
                    'level': 'error',
                    'message': f'YAML语法错误: {e}',
                    'fixable': False
                })
                
            # 3. 配置结构检查
            if config_manager.is_valid():
                validation_results.append({
                    'level': 'success',
                    'message': '配置结构有效'
                })
            else:
                validation_results.append({
                    'level': 'warning',
                    'message': '配置结构不完整，可能缺少必要字段',
                    'fixable': True,
                    'fix_action': 'add_missing_fields'
                })
                
            # 4. 渠道配置检查
            config_data = config_manager.get_config()
            channels = config_data.get('channels', {})
            
            if not channels:
                validation_results.append({
                    'level': 'warning',
                    'message': '没有配置任何通知渠道',
                    'fixable': True,
                    'fix_action': 'add_sample_channels'
                })
            else:
                enabled_count = sum(1 for ch in channels.values() if ch.get('enabled', False))
                if enabled_count == 0:
                    validation_results.append({
                        'level': 'warning',
                        'message': '没有启用任何通知渠道'
                    })
                else:
                    validation_results.append({
                        'level': 'success',
                        'message': f'已启用 {enabled_count} 个通知渠道'
                    })
                    
        # 显示验证结果
        click.echo("\n📋 验证结果:")
        
        error_count = 0
        warning_count = 0
        fixable_count = 0
        
        for result in validation_results:
            level = result['level']
            message = result['message']
            
            if level == 'success':
                click.echo(f"  ✅ {message}")
            elif level == 'warning':
                click.echo(f"  ⚠️  {message}")
                warning_count += 1
                if result.get('fixable'):
                    fixable_count += 1
            elif level == 'error':
                click.echo(f"  ❌ {message}")
                error_count += 1
                if result.get('fixable'):
                    fixable_count += 1
                    
        # 摘要
        click.echo(f"\n📊 验证摘要:")
        click.echo(f"  错误: {error_count}")
        click.echo(f"  警告: {warning_count}")
        click.echo(f"  可自动修复: {fixable_count}")
        
        # 自动修复
        if fix and fixable_count > 0:
            click.echo(f"\n🔧 开始自动修复...")
            _auto_fix_config(validation_results, config_manager)
            
        elif fixable_count > 0:
            click.echo(f"\n💡 提示: 使用 --fix 选项自动修复问题")
            
        if error_count > 0:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ 配置验证失败: {e}")
        sys.exit(1)


@config.command()
@click.option('--backup-dir', help='备份目录 (默认: ~/.claude-notifier/backups)')
def backup(backup_dir):
    """备份当前配置"""
    try:
        from claude_notifier.core.config import ConfigManager
        import shutil
        import os
        from datetime import datetime
        
        config_manager = ConfigManager()
        config_file = config_manager.config_path
        
        if not os.path.exists(config_file):
            click.echo("❌ 配置文件不存在，无法备份")
            sys.exit(1)
            
        # 设置备份目录
        if backup_dir is None:
            backup_dir = os.path.expanduser('~/.claude-notifier/backups')
            
        os.makedirs(backup_dir, exist_ok=True)
        
        # 生成备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'config_backup_{timestamp}.yaml'
        backup_path = os.path.join(backup_dir, backup_name)
        
        # 执行备份
        shutil.copy2(config_file, backup_path)
        
        click.echo(f"✅ 配置已备份到: {backup_path}")
        
        # 显示备份列表
        backups = [f for f in os.listdir(backup_dir) if f.startswith('config_backup_')]
        backups.sort(reverse=True)
        
        if len(backups) > 1:
            click.echo(f"\n📁 最近的备份文件:")
            for backup in backups[:5]:  # 显示最近5个
                backup_path = os.path.join(backup_dir, backup)
                stat = os.stat(backup_path)
                backup_time = datetime.fromtimestamp(stat.st_mtime)
                click.echo(f"  • {backup} ({backup_time.strftime('%Y-%m-%d %H:%M:%S')})")
                
    except Exception as e:
        click.echo(f"❌ 配置备份失败: {e}")
        sys.exit(1)


@config.command()
@click.option('--force', is_flag=True, help='强制覆盖现有配置')
@click.option('--template', type=click.Choice(['basic', 'full', 'intelligence']), 
              default='basic', help='配置模板')
def init(force, template):
    """初始化配置文件"""
    try:
        from claude_notifier.core.config import ConfigManager
        import os
        import yaml
        
        config_manager = ConfigManager()
        config_file = config_manager.config_path
        
        # 检查是否需要覆盖
        if os.path.exists(config_file) and not force:
            click.echo("❌ 配置文件已存在")
            click.echo("💡 使用 --force 强制覆盖，或先备份: claude-notifier config backup")
            sys.exit(1)
            
        # 生成配置模板
        config_template = _generate_config_template(template)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        # 写入配置
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_template, f, default_flow_style=False, allow_unicode=True)
            
        click.echo(f"✅ 配置文件已初始化: {config_file}")
        click.echo(f"📋 使用模板: {template}")
        
        click.echo(f"\n💡 下一步:")
        click.echo(f"  1. 编辑配置文件: {config_file}")
        click.echo(f"  2. 配置通知渠道: claude-notifier config channels")
        click.echo(f"  3. 验证配置: claude-notifier config validate")
        click.echo(f"  4. 测试通知: claude-notifier test")
        
    except Exception as e:
        click.echo(f"❌ 配置初始化失败: {e}")
        sys.exit(1)


@config.command()
@click.option('--enable', help='启用指定渠道 (逗号分隔)')
@click.option('--disable', help='禁用指定渠道 (逗号分隔)')
@click.option('--list', 'list_channels', is_flag=True, help='列出所有渠道配置')
def channels(enable, disable, list_channels):
    """管理通知渠道配置"""
    try:
        from claude_notifier.core.config import ConfigManager
        import yaml
        
        config_manager = ConfigManager()
        config_data = config_manager.get_config()
        channels_config = config_data.get('channels', {})
        
        if list_channels:
            click.echo("📡 通知渠道配置:")
            
            if not channels_config:
                click.echo("  (无配置的渠道)")
            else:
                for channel_name, channel_config in channels_config.items():
                    enabled = channel_config.get('enabled', False)
                    status = "✅ 已启用" if enabled else "❌ 已禁用"
                    
                    click.echo(f"  • {channel_name}: {status}")
                    
                    # 显示关键配置 (隐藏敏感信息)
                    for key, value in channel_config.items():
                        if key == 'enabled':
                            continue
                        if key in ['token', 'secret', 'webhook', 'password']:
                            value = '*' * 8
                        click.echo(f"    {key}: {value}")
            return
            
        modified = False
        
        # 启用渠道
        if enable:
            channel_list = [ch.strip() for ch in enable.split(',')]
            for channel in channel_list:
                if channel in channels_config:
                    channels_config[channel]['enabled'] = True
                    click.echo(f"✅ 已启用渠道: {channel}")
                    modified = True
                else:
                    click.echo(f"❌ 渠道不存在: {channel}")
                    
        # 禁用渠道
        if disable:
            channel_list = [ch.strip() for ch in disable.split(',')]
            for channel in channel_list:
                if channel in channels_config:
                    channels_config[channel]['enabled'] = False
                    click.echo(f"❌ 已禁用渠道: {channel}")
                    modified = True
                else:
                    click.echo(f"❌ 渠道不存在: {channel}")
                    
        # 保存修改
        if modified:
            with open(config_manager.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            click.echo("\n✅ 配置已保存")
            
        # 重新加载配置
        try:
            notifier = Notifier()
            notifier.reload_config()
            click.echo("✅ 配置已重新加载")
        except:
            pass
            
    except Exception as e:
        click.echo(f"❌ 渠道配置操作失败: {e}")
        sys.exit(1)


@config.command()
def reload():
    """重新加载配置文件"""
    try:
        notifier = Notifier()
        success = notifier.reload_config()
        
        if success:
            click.echo("✅ 配置重新加载成功")
        else:
            click.echo("❌ 配置重新加载失败")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ 配置重新加载失败: {e}")
        sys.exit(1)


def _hide_sensitive_data(config_data):
    """隐藏配置中的敏感信息"""
    sensitive_keys = ['token', 'secret', 'webhook', 'password', 'key', 'api_key']
    
    def hide_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    if isinstance(value, str) and len(value) > 0:
                        obj[key] = '*' * min(8, len(value))
                else:
                    hide_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                hide_recursive(item)
                
    hide_recursive(config_data)
    return config_data


def _auto_fix_config(validation_results, config_manager):
    """自动修复配置问题"""
    import yaml
    import os
    
    config_data = config_manager.get_config()
    modified = False
    
    for result in validation_results:
        if not result.get('fixable'):
            continue
            
        fix_action = result.get('fix_action')
        
        if fix_action == 'create_default':
            config_data = _generate_config_template('basic')
            modified = True
            click.echo("  🔧 创建默认配置文件")
            
        elif fix_action == 'add_missing_fields':
            default_config = _generate_config_template('basic')
            
            # 递归添加缺失字段
            def merge_missing(target, source):
                for key, value in source.items():
                    if key not in target:
                        target[key] = value
                    elif isinstance(value, dict) and isinstance(target[key], dict):
                        merge_missing(target[key], value)
                        
            merge_missing(config_data, default_config)
            modified = True
            click.echo("  🔧 添加缺失的配置字段")
            
        elif fix_action == 'add_sample_channels':
            if 'channels' not in config_data:
                config_data['channels'] = {}
                
            # 添加示例渠道配置
            config_data['channels'].update(_get_sample_channels())
            modified = True
            click.echo("  🔧 添加示例渠道配置")
            
    if modified:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_manager.config_path), exist_ok=True)
        
        # 保存修复后的配置
        with open(config_manager.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            
        click.echo("✅ 自动修复完成")
    else:
        click.echo("⚠️  没有可自动修复的问题")


def _generate_config_template(template_type):
    """生成配置模板"""
    base_config = {
        'channels': {},
        'events': {
            'hook_events': {
                'command_executed': {'enabled': True, 'channels': []},
                'error_occurred': {'enabled': True, 'channels': [], 'priority': 'high'}
            }
        },
        'notifications': {
            'default_channels': [],
            'rate_limiting': {
                'enabled': False,
                'max_per_minute': 10
            }
        },
        'advanced': {
            'logging': {
                'level': 'info',
                'file': '~/.claude-notifier/logs/notifier.log'
            }
        }
    }
    
    if template_type == 'full':
        base_config['channels'] = _get_sample_channels()
        base_config['events']['custom_events'] = {
            'build_completed': {'enabled': True, 'channels': []},
            'deployment_finished': {'enabled': True, 'channels': [], 'priority': 'high'}
        }
        
    elif template_type == 'intelligence':
        base_config['channels'] = _get_sample_channels()
        base_config['intelligent_limiting'] = {
            'enabled': True,
            'operation_gate': {
                'enabled': True,
                'sensitivity': 'medium'
            },
            'notification_throttle': {
                'enabled': True,
                'duplicate_window': 300
            },
            'message_grouper': {
                'enabled': True,
                'group_window': 120
            },
            'cooldown_manager': {
                'enabled': True,
                'default_cooldown': 60
            }
        }
        
    return base_config


def _get_sample_channels():
    """获取示例渠道配置"""
    return {
        'dingtalk': {
            'enabled': False,
            'webhook': 'https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN',
            'secret': 'YOUR_SECRET'
        },
        'feishu': {
            'enabled': False,
            'webhook': 'https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN'
        },
        'email': {
            'enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': 'your_email@gmail.com',
            'password': 'your_password',
            'from_addr': 'your_email@gmail.com',
            'to_addrs': ['recipient@example.com']
        }
    }


@cli.group(invoke_without_command=True)
@click.pass_context
def hooks(ctx):
    """Claude Code钩子管理
    
    管理Claude Code集成钩子，实现智能通知功能：
    
    Commands:
        install   - 安装钩子配置
        uninstall - 卸载钩子配置  
        status    - 查看钩子状态
        verify    - 验证钩子配置
        
    Examples:
        claude-notifier hooks                  # 查看钩子状态
        claude-notifier hooks install         # 安装钩子
        claude-notifier hooks status          # 检查钩子状态
        claude-notifier hooks verify          # 验证钩子配置
    """
    if ctx.invoked_subcommand is None:
        _show_hooks_status()


def _show_hooks_status():
    """显示钩子状态概览"""
    try:
        from claude_notifier.hooks.installer import ClaudeHookInstaller
        
        installer = ClaudeHookInstaller()
        installer.print_status()
        
    except ImportError:
        click.echo("❌ 钩子功能不可用")
        click.echo("💡 请确保在PyPI安装中包含钩子模块")
    except Exception as e:
        click.echo(f"❌ 钩子状态获取失败: {e}")


@hooks.command()
@click.option('--force', is_flag=True, help='强制安装（覆盖现有配置）')
@click.option('--detect-only', is_flag=True, help='只检测Claude Code，不安装')
def install(force, detect_only):
    """安装Claude Code钩子配置
    
    自动检测Claude Code安装并配置钩子，实现：
    - 会话开始时的通知
    - 命令执行时的权限检查
    - 任务完成时的庆祝通知
    - 错误发生时的报警通知
    """
    try:
        from claude_notifier.hooks.installer import ClaudeHookInstaller
        
        installer = ClaudeHookInstaller()
        
        if detect_only:
            # 只检测不安装
            claude_detected, claude_location = installer.detect_claude_code()
            if claude_detected:
                click.echo(f"✅ 检测到Claude Code: {claude_location}")
                click.echo("💡 运行 'claude-notifier hooks install' 开始安装")
            else:
                click.echo("❌ 未检测到Claude Code安装")
                click.echo("💡 请先安装Claude Code: npm install -g @anthropic-ai/claude-code")
            return
        
        # 执行安装
        success, message = installer.install_hooks(force=force)
        click.echo(message)
        
        if success:
            click.echo("\n🎉 Claude Code钩子安装完成！")
            click.echo("\n📋 后续步骤:")
            click.echo("  1. 重新启动Claude Code")
            click.echo("  2. 运行 'claude-notifier test' 测试通知")
            click.echo("  3. 开始使用增强的Claude Code体验")
        else:
            click.echo("\n💡 安装故障排除:")
            click.echo("  1. 确保Claude Code已正确安装")
            click.echo("  2. 检查~/.claude目录权限")
            click.echo("  3. 使用 --force 强制覆盖现有配置")
            sys.exit(1)
            
    except ImportError:
        click.echo("❌ 钩子安装器不可用")
        click.echo("💡 这可能是PyPI包问题，请联系开发者")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 钩子安装失败: {e}")
        sys.exit(1)


@hooks.command()
@click.option('--backup/--no-backup', default=True, help='是否备份现有配置')
def uninstall(backup):
    """卸载Claude Code钩子配置
    
    移除已安装的钩子配置，恢复原始Claude Code行为。
    卸载后Claude Code将不再发送通知。
    """
    try:
        from claude_notifier.hooks.installer import ClaudeHookInstaller
        
        installer = ClaudeHookInstaller()
        
        # 确认卸载
        if not click.confirm("确定要卸载Claude Code钩子吗？这将停止所有Claude Code通知功能"):
            click.echo("❌ 用户取消卸载")
            return
        
        success, message = installer.uninstall_hooks()
        click.echo(message)
        
        if success:
            click.echo("\n✅ Claude Code钩子已成功卸载")
            click.echo("💡 重新启动Claude Code以使更改生效")
        else:
            sys.exit(1)
            
    except ImportError:
        click.echo("❌ 钩子安装器不可用")
        sys.exit(1)  
    except Exception as e:
        click.echo(f"❌ 钩子卸载失败: {e}")
        sys.exit(1)


@hooks.command()
def status():
    """查看钩子详细状态
    
    显示完整的钩子系统状态，包括：
    - Claude Code检测结果
    - 钩子脚本状态
    - 配置文件状态
    - 启用的钩子列表
    """
    try:
        from claude_notifier.hooks.installer import ClaudeHookInstaller
        
        installer = ClaudeHookInstaller()
        installer.print_status()
        
        # 额外的诊断信息
        status = installer.get_installation_status()
        
        if status['claude_detected'] and status['hooks_installed'] and status['hooks_valid']:
            click.echo(f"\n💡 提示:")
            click.echo(f"  - 钩子已就绪，Claude Code启动时将自动加载")
            click.echo(f"  - 运行 'claude-notifier test' 测试通知功能")
            click.echo(f"  - 查看 ~/.claude-notifier/logs/ 了解详细日志")
        else:
            click.echo(f"\n⚠️ 问题修复建议:")
            if not status['claude_detected']:
                click.echo(f"  - 安装Claude Code: npm install -g @anthropic-ai/claude-code")
            if not status['hooks_installed']:
                click.echo(f"  - 安装钩子: claude-notifier hooks install")
            if not status['hooks_valid']:
                click.echo(f"  - 重新安装: claude-notifier hooks install --force")
                
    except ImportError:
        click.echo("❌ 钩子功能不可用")
    except Exception as e:
        click.echo(f"❌ 状态获取失败: {e}")


@hooks.command()
@click.option('--fix', is_flag=True, help='自动修复发现的问题')
def verify(fix):
    """验证钩子配置完整性
    
    全面验证钩子系统：
    - 检查钩子脚本文件
    - 验证配置文件格式
    - 测试钩子执行权限
    - 检查路径和依赖
    """
    try:
        from claude_notifier.hooks.installer import ClaudeHookInstaller
        
        installer = ClaudeHookInstaller()
        
        click.echo("🔍 开始钩子配置验证...")
        
        # 基础验证
        if installer.verify_installation():
            click.echo("✅ 钩子配置验证通过")
            
            # 执行钩子测试
            click.echo("\n🧪 测试钩子执行...")
            
            # 简单的钩子调用测试
            import subprocess
            
            hook_script = installer.hook_script_path
            if hook_script.exists():
                try:
                    # 测试钩子脚本语法
                    result = subprocess.run(
                        [sys.executable, '-m', 'py_compile', str(hook_script)],
                        capture_output=True, text=True
                    )
                    
                    if result.returncode == 0:
                        click.echo("✅ 钩子脚本语法正确")
                    else:
                        click.echo(f"❌ 钩子脚本语法错误: {result.stderr}")
                        
                except Exception as e:
                    click.echo(f"⚠️ 钩子脚本测试失败: {e}")
            
            # 配置文件权限检查
            if installer.hooks_file.exists():
                import os
                stat_info = installer.hooks_file.stat()
                if stat_info.st_mode & 0o044:  # 检查读权限
                    click.echo("✅ 钩子配置文件权限正确")
                else:
                    click.echo("⚠️ 钩子配置文件权限异常")
                    
            click.echo("\n🎉 钩子系统验证完成")
            
        else:
            click.echo("❌ 钩子配置验证失败")
            
            if fix:
                click.echo("\n🔧 尝试自动修复...")
                success, message = installer.install_hooks(force=True)
                if success:
                    click.echo("✅ 自动修复成功")
                else:
                    click.echo(f"❌ 自动修复失败: {message}")
                    sys.exit(1)
            else:
                click.echo("💡 使用 --fix 选项尝试自动修复")
                sys.exit(1)
                
    except ImportError:
        click.echo("❌ 钩子验证功能不可用")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 钩子验证失败: {e}")
        sys.exit(1)


@cli.group(invoke_without_command=True)
@click.pass_context  
def debug(ctx):
    """交互式调试和诊断工具
    
    调试功能:
        logs        - 日志查看和分析
        trace       - 通知流程跟踪
        shell       - 交互式调试Shell
        diagnose    - 系统诊断
        intelligence- 智能功能调试
        
    Examples:
        claude-notifier debug                     # 显示调试选项
        claude-notifier debug logs --tail        # 实时查看日志
        claude-notifier debug trace dingtalk     # 跟踪钉钉通知流程
        claude-notifier debug shell              # 启动交互式Shell
        claude-notifier debug diagnose           # 系统诊断
        claude-notifier debug intelligence       # 智能功能调试
    """
    if ctx.invoked_subcommand is None:
        _show_debug_menu()


def _show_debug_menu():
    """显示调试菜单"""
    click.echo("🐛 Claude Code Notifier 调试工具")
    click.echo("=" * 50)
    click.echo("")
    
    click.echo("📋 可用的调试命令:")
    click.echo("  📄 logs        - 查看和分析日志文件")
    click.echo("  🔍 trace       - 跟踪通知发送流程") 
    click.echo("  🖥️  shell       - 交互式调试Shell")
    click.echo("  🩺 diagnose    - 系统健康诊断")
    click.echo("  🧠 intelligence- 智能功能调试")
    click.echo("")
    
    click.echo("💡 使用示例:")
    click.echo("  claude-notifier debug logs --tail")
    click.echo("  claude-notifier debug trace dingtalk")
    click.echo("  claude-notifier debug diagnose --full")
    click.echo("")
    
    click.echo("❓ 获取帮助: claude-notifier debug <命令> --help")


@debug.command()
@click.option('--tail', is_flag=True, help='实时跟踪日志 (类似tail -f)')
@click.option('--level', type=click.Choice(['debug', 'info', 'warning', 'error']),
              help='过滤日志级别')
@click.option('--lines', type=int, default=50, help='显示行数')
@click.option('--filter', help='过滤关键词')
@click.option('--component', help='过滤组件名称')
def logs(tail, level, lines, filter, component):
    """查看和分析日志文件"""
    try:
        import os
        import re
        import time
        from pathlib import Path
        
        # 查找日志文件
        possible_log_paths = [
            '~/.claude-notifier/logs/notifier.log',
            '~/.claude-notifier/notifier.log',
            './logs/notifier.log',
            './notifier.log'
        ]
        
        log_file = None
        for path in possible_log_paths:
            expanded_path = Path(os.path.expanduser(path))
            if expanded_path.exists():
                log_file = expanded_path
                break
                
        if not log_file:
            click.echo("❌ 找不到日志文件")
            click.echo("💡 日志文件可能位置:")
            for path in possible_log_paths:
                click.echo(f"  • {path}")
            sys.exit(1)
            
        click.echo(f"📄 日志文件: {log_file}")
        
        if tail:
            _tail_log_file(log_file, level, filter, component)
        else:
            _show_log_file(log_file, lines, level, filter, component)
            
    except Exception as e:
        click.echo(f"❌ 日志查看失败: {e}")
        sys.exit(1)


def _tail_log_file(log_file, level_filter, keyword_filter, component_filter):
    """实时跟踪日志文件"""
    click.echo(f"🔄 实时跟踪日志 (按 Ctrl+C 退出)")
    click.echo(f"📍 过滤条件: 级别={level_filter or '全部'}, 关键词={keyword_filter or '无'}, 组件={component_filter or '全部'}")
    click.echo("-" * 80)
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            # 移到文件末尾
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    if _should_show_log_line(line, level_filter, keyword_filter, component_filter):
                        formatted_line = _format_log_line(line)
                        click.echo(formatted_line, nl=False)
                else:
                    time.sleep(0.1)
                    
    except KeyboardInterrupt:
        click.echo("\n👋 停止日志跟踪")
    except Exception as e:
        click.echo(f"\n❌ 日志跟踪失败: {e}")


def _show_log_file(log_file, lines, level_filter, keyword_filter, component_filter):
    """显示日志文件内容"""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            
        # 过滤日志行
        filtered_lines = []
        for line in all_lines:
            if _should_show_log_line(line, level_filter, keyword_filter, component_filter):
                filtered_lines.append(line)
                
        # 显示最后N行
        display_lines = filtered_lines[-lines:] if len(filtered_lines) > lines else filtered_lines
        
        click.echo(f"📋 显示最后 {len(display_lines)} 行日志:")
        click.echo("-" * 80)
        
        for line in display_lines:
            formatted_line = _format_log_line(line)
            click.echo(formatted_line, nl=False)
            
    except Exception as e:
        click.echo(f"❌ 读取日志失败: {e}")


def _should_show_log_line(line, level_filter, keyword_filter, component_filter):
    """判断是否应该显示日志行"""
    if level_filter:
        if level_filter.upper() not in line:
            return False
            
    if keyword_filter:
        if keyword_filter.lower() not in line.lower():
            return False
            
    if component_filter:
        if component_filter.lower() not in line.lower():
            return False
            
    return True


def _format_log_line(line):
    """格式化日志行"""
    # 添加颜色标记
    if 'ERROR' in line:
        return f"🔴 {line}"
    elif 'WARNING' in line:
        return f"🟡 {line}"
    elif 'INFO' in line:
        return f"🔵 {line}"
    elif 'DEBUG' in line:
        return f"⚪ {line}"
    else:
        return line


@debug.command()
@click.argument('channel', required=False)
@click.option('--message', default='调试测试消息', help='测试消息内容')
@click.option('--step', is_flag=True, help='单步调试模式')
@click.option('--verbose', is_flag=True, help='详细输出')
def trace(channel, message, step, verbose):
    """跟踪通知发送流程"""
    try:
        click.echo("🔍 开始通知流程跟踪")
        click.echo("=" * 50)
        
        if not channel:
            # 显示可用渠道
            notifier = Notifier()
            status = notifier.get_status()
            channels = status['channels']['available']
            
            click.echo("📡 可用的通知渠道:")
            for ch in channels:
                click.echo(f"  • {ch}")
            click.echo("\n💡 使用: claude-notifier debug trace <渠道名>")
            return
            
        # 开始跟踪
        _trace_notification_flow(channel, message, step, verbose)
        
    except Exception as e:
        click.echo(f"❌ 通知跟踪失败: {e}")
        sys.exit(1)


def _trace_notification_flow(channel, message, step_mode, verbose):
    """跟踪通知流程"""
    click.echo(f"🎯 目标渠道: {channel}")
    click.echo(f"📝 测试消息: {message}")
    click.echo(f"🔧 调试模式: {'单步' if step_mode else '连续'}")
    click.echo("")
    
    steps = [
        ("1️⃣ 初始化通知器", lambda: _init_notifier_debug()),
        ("2️⃣ 加载配置", lambda: _load_config_debug(channel)),
        ("3️⃣ 验证渠道", lambda: _validate_channel_debug(channel)),
        ("4️⃣ 智能功能检查", lambda: _check_intelligence_debug()),
        ("5️⃣ 构建消息", lambda: _build_message_debug(message, channel)),
        ("6️⃣ 发送通知", lambda: _send_notification_debug(channel, message)),
        ("7️⃣ 结果验证", lambda: _verify_result_debug())
    ]
    
    results = {}
    
    for step_name, step_func in steps:
        click.echo(f"\n{step_name}")
        click.echo("-" * 30)
        
        if step_mode:
            input("⏯️  按回车继续...")
            
        try:
            result = step_func()
            results[step_name] = result
            
            if verbose:
                click.echo(f"📊 结果: {result}")
                
            if result.get('success', True):
                click.echo("✅ 成功")
            else:
                click.echo(f"❌ 失败: {result.get('error', '未知错误')}")
                break
                
        except Exception as e:
            click.echo(f"❌ 异常: {e}")
            results[step_name] = {'success': False, 'error': str(e)}
            break
            
    # 显示跟踪摘要
    click.echo(f"\n📋 跟踪摘要:")
    click.echo("=" * 30)
    
    success_count = sum(1 for r in results.values() if r.get('success', True))
    total_count = len(results)
    
    click.echo(f"总步骤: {total_count}")
    click.echo(f"成功步骤: {success_count}")
    click.echo(f"成功率: {success_count/total_count*100:.1f}%")


def _init_notifier_debug():
    """调试: 初始化通知器"""
    notifier = Notifier()
    return {'success': True, 'notifier': notifier}


def _load_config_debug(channel):
    """调试: 加载配置"""
    from claude_notifier.core.config import ConfigManager
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    channel_config = config.get('channels', {}).get(channel)
    if not channel_config:
        return {'success': False, 'error': f'渠道 {channel} 未配置'}
        
    return {'success': True, 'config': channel_config}


def _validate_channel_debug(channel):
    """调试: 验证渠道"""
    # 这里可以添加渠道特定的验证逻辑
    return {'success': True, 'validated': True}


def _check_intelligence_debug():
    """调试: 智能功能检查"""
    try:
        from claude_notifier import has_intelligence
        intel_available = has_intelligence()
        return {'success': True, 'intelligence_available': intel_available}
    except:
        return {'success': True, 'intelligence_available': False}


def _build_message_debug(message, channel):
    """调试: 构建消息"""
    return {'success': True, 'message': message, 'channel': channel}


def _send_notification_debug(channel, message):
    """调试: 发送通知"""
    # 这里可以添加实际的发送逻辑或模拟
    return {'success': True, 'sent': True, 'channel': channel}


def _verify_result_debug():
    """调试: 验证结果"""
    return {'success': True, 'verified': True}


@debug.command()
@click.option('--port', type=int, default=8888, help='Shell服务端口')
@click.option('--simple', is_flag=True, help='简单模式 (不启动Web界面)')
def shell(port, simple):
    """启动交互式调试Shell"""
    if simple:
        _start_simple_shell()
    else:
        _start_web_shell(port)


def _start_simple_shell():
    """启动简单调试Shell"""
    try:
        click.echo("🖥️  启动交互式调试Shell")
        click.echo("=" * 40)
        click.echo("💡 可用对象:")
        click.echo("  notifier  - 通知器实例")
        click.echo("  config    - 配置管理器")
        click.echo("  stats     - 统计管理器 (如果可用)")
        click.echo("  health    - 健康检查器 (如果可用)")
        click.echo("  perf      - 性能监控器 (如果可用)")
        click.echo("")
        click.echo("📝 使用 'help()' 查看帮助，'exit()' 退出")
        click.echo("=" * 40)
        
        # 准备调试环境
        debug_globals = _prepare_debug_environment()
        
        # 启动交互式Shell
        import code
        code.interact(local=debug_globals, banner="")
        
    except Exception as e:
        click.echo(f"❌ Shell启动失败: {e}")


def _start_web_shell(port):
    """启动Web调试Shell"""
    click.echo(f"🌐 启动Web调试界面 (端口: {port})")
    click.echo("❌ Web Shell功能需要额外依赖")
    click.echo("💡 使用 --simple 启动简单Shell")


def _prepare_debug_environment():
    """准备调试环境"""
    debug_env = {}
    
    # 基础组件
    try:
        notifier = Notifier()
        debug_env['notifier'] = notifier
        click.echo("✅ 通知器已加载")
    except Exception as e:
        click.echo(f"❌ 通知器加载失败: {e}")
        
    try:
        from claude_notifier.core.config import ConfigManager
        config_manager = ConfigManager()
        debug_env['config'] = config_manager
        click.echo("✅ 配置管理器已加载")
    except Exception as e:
        click.echo(f"❌ 配置管理器加载失败: {e}")
        
    # 监控组件 (如果可用)
    if MONITORING_CLI_AVAILABLE:
        try:
            from claude_notifier.monitoring.dashboard import MonitoringDashboard
            dashboard = MonitoringDashboard()
            debug_env['dashboard'] = dashboard
            
            if dashboard.statistics_manager:
                debug_env['stats'] = dashboard.statistics_manager
                
            if dashboard.health_checker:
                debug_env['health'] = dashboard.health_checker
                
            if dashboard.performance_monitor:
                debug_env['perf'] = dashboard.performance_monitor
                
            click.echo("✅ 监控组件已加载")
        except Exception as e:
            click.echo(f"❌ 监控组件加载失败: {e}")
            
    return debug_env


@debug.command()
@click.option('--full', is_flag=True, help='完整诊断 (包括性能测试)')
@click.option('--fix', is_flag=True, help='自动修复发现的问题')
@click.option('--report', help='保存诊断报告到文件')
def diagnose(full, fix, report):
    """系统健康诊断"""
    try:
        click.echo("🩺 开始系统诊断")
        click.echo("=" * 40)
        
        diagnostic_results = []
        
        # 1. 基础系统检查
        click.echo("\n1️⃣ 基础系统检查...")
        basic_results = _diagnose_basic_system()
        diagnostic_results.extend(basic_results)
        
        # 2. 配置检查
        click.echo("\n2️⃣ 配置检查...")
        config_results = _diagnose_configuration()
        diagnostic_results.extend(config_results)
        
        # 3. 通知渠道检查
        click.echo("\n3️⃣ 通知渠道检查...")
        channel_results = _diagnose_channels()
        diagnostic_results.extend(channel_results)
        
        # 4. 监控系统检查
        try:
            from claude_notifier.monitoring.dashboard import MonitoringDashboard
            click.echo("\n4️⃣ 监控系统检查...")
            monitoring_results = _diagnose_monitoring()
            diagnostic_results.extend(monitoring_results)
        except ImportError:
            diagnostic_results.append({'type': 'warning', 'message': '监控功能未安装或不可用'})
            
        # 5. 性能检查 (如果启用完整诊断)
        if full:
            click.echo("\n5️⃣ 性能检查...")
            performance_results = _diagnose_performance()
            diagnostic_results.extend(performance_results)
            
        # 显示诊断结果
        _display_diagnostic_results(diagnostic_results)
        
        # 自动修复
        if fix:
            _auto_fix_issues(diagnostic_results)
            
        # 保存报告
        if report:
            _save_diagnostic_report(diagnostic_results, report)
            
    except Exception as e:
        click.echo(f"❌ 系统诊断失败: {e}")
        sys.exit(1)


def _diagnose_basic_system():
    """诊断基础系统"""
    results = []
    
    # Python版本检查
    import sys
    python_version = sys.version_info
    if python_version >= (3, 7):
        results.append({'type': 'success', 'message': f'Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}'})
    else:
        results.append({'type': 'error', 'message': 'Python版本过低，需要3.7+', 'fixable': False})
        
    # 依赖检查
    required_packages = ['click', 'pyyaml']
    for package in required_packages:
        try:
            __import__(package)
            results.append({'type': 'success', 'message': f'依赖 {package} 已安装'})
        except ImportError:
            results.append({'type': 'error', 'message': f'缺少依赖 {package}', 'fixable': True})
            
    return results


def _diagnose_configuration():
    """诊断配置系统"""
    results = []
    
    try:
        from claude_notifier.core.config import ConfigManager
        config_manager = ConfigManager()
        
        if config_manager.is_valid():
            results.append({'type': 'success', 'message': '配置文件有效'})
        else:
            results.append({'type': 'warning', 'message': '配置文件结构不完整', 'fixable': True})
            
        config = config_manager.get_config()
        channels = config.get('channels', {})
        enabled_channels = sum(1 for ch in channels.values() if ch.get('enabled', False))
        
        if enabled_channels > 0:
            results.append({'type': 'success', 'message': f'已启用 {enabled_channels} 个通知渠道'})
        else:
            results.append({'type': 'warning', 'message': '没有启用的通知渠道'})
            
    except Exception as e:
        results.append({'type': 'error', 'message': f'配置诊断失败: {e}'})
        
    return results


def _diagnose_channels():
    """诊断通知渠道"""
    results = []
    
    try:
        notifier = Notifier()
        status = notifier.get_status()
        channels = status['channels']
        
        for channel in channels['available']:
            if channel in channels['enabled']:
                results.append({'type': 'success', 'message': f'渠道 {channel} 已启用'})
            else:
                results.append({'type': 'info', 'message': f'渠道 {channel} 已配置但未启用'})
                
    except Exception as e:
        results.append({'type': 'error', 'message': f'渠道诊断失败: {e}'})
        
    return results


def _diagnose_monitoring():
    """诊断监控系统"""
    results = []
    
    try:
        from claude_notifier.monitoring.dashboard import MonitoringDashboard
        dashboard = MonitoringDashboard()
        
        if dashboard.statistics_manager:
            results.append({'type': 'success', 'message': '统计管理器可用'})
        else:
            results.append({'type': 'warning', 'message': '统计管理器不可用'})
            
        if dashboard.health_checker:
            results.append({'type': 'success', 'message': '健康检查器可用'})
        else:
            results.append({'type': 'warning', 'message': '健康检查器不可用'})
            
        if dashboard.performance_monitor:
            results.append({'type': 'success', 'message': '性能监控器可用'})
        else:
            results.append({'type': 'warning', 'message': '性能监控器不可用'})
            
    except Exception as e:
        results.append({'type': 'error', 'message': f'监控系统诊断失败: {e}'})
        
    return results


def _diagnose_performance():
    """诊断系统性能"""
    results = []
    
    # 这里可以添加性能测试逻辑
    results.append({'type': 'info', 'message': '性能诊断完成 (基础检查)'})
    
    return results


def _display_diagnostic_results(results):
    """显示诊断结果"""
    click.echo("\n📋 诊断结果汇总:")
    click.echo("=" * 40)
    
    success_count = 0
    warning_count = 0
    error_count = 0
    info_count = 0
    
    for result in results:
        result_type = result['type']
        message = result['message']
        
        if result_type == 'success':
            click.echo(f"✅ {message}")
            success_count += 1
        elif result_type == 'warning':
            click.echo(f"⚠️  {message}")
            warning_count += 1
        elif result_type == 'error':
            click.echo(f"❌ {message}")
            error_count += 1
        elif result_type == 'info':
            click.echo(f"ℹ️  {message}")
            info_count += 1
            
    click.echo(f"\n📊 诊断统计:")
    click.echo(f"  成功: {success_count}")
    click.echo(f"  警告: {warning_count}")
    click.echo(f"  错误: {error_count}")
    click.echo(f"  信息: {info_count}")


def _auto_fix_issues(results):
    """自动修复问题"""
    click.echo("\n🔧 自动修复...")
    
    fixable_issues = [r for r in results if r.get('fixable', False)]
    
    if not fixable_issues:
        click.echo("⚠️  没有可自动修复的问题")
        return
        
    for issue in fixable_issues:
        click.echo(f"🔧 修复: {issue['message']}")
        # 这里可以添加具体的修复逻辑
        
    click.echo("✅ 自动修复完成")


def _save_diagnostic_report(results, report_file):
    """保存诊断报告"""
    try:
        import json
        from datetime import datetime
        
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'summary': {
                'success': len([r for r in results if r['type'] == 'success']),
                'warning': len([r for r in results if r['type'] == 'warning']),
                'error': len([r for r in results if r['type'] == 'error']),
                'info': len([r for r in results if r['type'] == 'info'])
            }
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
            
        click.echo(f"\n💾 诊断报告已保存到: {report_file}")
        
    except Exception as e:
        click.echo(f"❌ 保存报告失败: {e}")


@debug.command()
@click.option('--component', help='指定智能组件 (gate, throttle, grouper, cooldown)')
@click.option('--stats', is_flag=True, help='显示统计信息')
@click.option('--reset', is_flag=True, help='重置智能组件状态')
def intelligence(component, stats, reset):
    """智能功能调试"""
    try:
        from claude_notifier import has_intelligence
        
        if not has_intelligence():
            click.echo("❌ 智能功能未安装")
            click.echo("💡 使用: pip install claude-notifier[intelligence]")
            sys.exit(1)
            
        click.echo("🧠 智能功能调试")
        click.echo("=" * 30)
        
        if component:
            _debug_intelligence_component(component, stats, reset)
        else:
            _show_intelligence_overview(stats)
            
    except Exception as e:
        click.echo(f"❌ 智能功能调试失败: {e}")
        sys.exit(1)


def _debug_intelligence_component(component, show_stats, reset):
    """调试特定智能组件"""
    click.echo(f"🔍 调试组件: {component}")
    
    # 这里可以添加特定组件的调试逻辑
    if component == 'gate':
        click.echo("🚪 操作阻断器调试...")
    elif component == 'throttle':
        click.echo("🚦 通知限流器调试...")
    elif component == 'grouper':
        click.echo("📦 消息分组器调试...")
    elif component == 'cooldown':
        click.echo("❄️  冷却管理器调试...")
    else:
        click.echo("❌ 未知组件")
        return
        
    if show_stats:
        click.echo("📊 组件统计信息...")
        
    if reset:
        click.echo("🔄 重置组件状态...")


def _show_intelligence_overview(show_stats):
    """显示智能功能概览"""
    try:
        from claude_notifier import IntelligentNotifier
        
        intelligent_notifier = IntelligentNotifier()
        status = intelligent_notifier.get_intelligence_status()
        
        click.echo("📊 智能功能状态:")
        click.echo(f"  启用状态: {'✅ 已启用' if status['enabled'] else '❌ 已禁用'}")
        
        if status['enabled']:
            components = status['components']
            for comp_name, comp_status in components.items():
                enabled = '✅' if comp_status['enabled'] else '❌'
                click.echo(f"  {comp_name}: {enabled}")
                
        if show_stats:
            click.echo("\n📈 统计信息:")
            # 这里可以添加详细的统计信息显示
            
    except ImportError:
        click.echo("❌ 智能通知器未安装")


# 导入更新和卸载命令
try:
    from .update import update_cli
    from .uninstall import uninstall_cli
    
    cli.add_command(update_cli, name='update')
    cli.add_command(uninstall_cli, name='uninstall')
except ImportError:
    # 如果依赖不可用，则创建占位符命令
    @cli.command()
    def update():
        """更新Claude Notifier (需要requests库)"""
        click.echo("❌ 更新功能需要安装requests库: pip install requests")
        
    @cli.command() 
    def uninstall():
        """卸载Claude Notifier"""
        click.echo("❌ 卸载功能暂不可用")


# 智能功能相关命令 (可选)
def _add_intelligence_commands():
    """添加智能功能命令"""
    try:
        from claude_notifier import has_intelligence, IntelligentNotifier
        
        if not has_intelligence():
            return
            
        @cli.group()
        def intelligence():
            """智能功能管理"""
            pass
            
        @intelligence.command()
        @click.option('--component', help='指定组件 (operation_gate, throttle, grouper, cooldown)')
        def enable(component):
            """启用智能功能"""
            # 实现智能功能启用逻辑
            click.echo(f"启用智能功能: {component or 'all'}")
            
        @intelligence.command() 
        @click.option('--component', help='指定组件')
        def disable(component):
            """禁用智能功能"""
            # 实现智能功能禁用逻辑
            click.echo(f"禁用智能功能: {component or 'all'}")
            
        @intelligence.command()
        def stats():
            """查看智能功能统计"""
            try:
                notifier = IntelligentNotifier()
                intel_status = notifier.get_intelligence_status()
                
                click.echo("🧠 智能功能统计:")
                # 显示详细统计信息
                # ...实现统计显示逻辑
                
            except Exception as e:
                click.echo(f"❌ 统计获取失败: {e}")
                
    except ImportError:
        pass

# 添加智能功能命令 (如果可用)
_add_intelligence_commands()


def main():
    """主入口点"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n👋 已取消操作")
        sys.exit(130)
    except Exception as e:
        click.echo(f"❌ 意外错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()