#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉通知渠道
从原有channels/dingtalk.py迁移而来，适配新轻量化架构
"""

import time
import hmac
import hashlib
import base64
import urllib.parse
import json
from typing import Dict, Any

# 可选依赖处理
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

from .base import BaseChannel


class DingtalkChannel(BaseChannel):
    """钉钉机器人通知渠道"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化钉钉渠道
        
        Args:
            config: 钉钉配置字典
        """
        super().__init__(config)
        self.webhook = config.get('webhook', '')
        self.secret = config.get('secret', '')
        
    def validate_config(self) -> bool:
        """验证钉钉配置
        
        Returns:
            配置是否有效
        """
        if not REQUESTS_AVAILABLE:
            self.logger.error("钉钉渠道需要requests库: pip install requests")
            return False
            
        if not self.webhook:
            self.logger.error("钉钉webhook URL未配置")
            return False
            
        if not self.webhook.startswith('https://oapi.dingtalk.com/robot/send'):
            self.logger.error("钉钉webhook URL格式不正确")
            return False
            
        return True
        
    def _sign_webhook(self) -> str:
        """生成签名后的webhook URL
        
        Returns:
            签名后的URL
        """
        if not self.secret:
            return self.webhook
            
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f'{self.webhook}&timestamp={timestamp}&sign={sign}'
        
    def _send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息到钉钉
        
        Args:
            message: 钉钉消息格式
            
        Returns:
            发送是否成功
        """
        if not REQUESTS_AVAILABLE:
            self.logger.error("requests库不可用")
            return False
            
        try:
            url = self._sign_webhook()
            
            response = requests.post(
                url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(message),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    self.logger.debug("钉钉通知发送成功")
                    return True
                else:
                    self.logger.error(f"钉钉通知发送失败: {result}")
                    return False
            else:
                self.logger.error(f"钉钉API请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"钉钉通知发送异常: {e}")
            return False
            
    def send_notification(self, template_data: Dict[str, Any], event_type: str = 'generic') -> bool:
        """发送钉钉通知
        
        Args:
            template_data: 模板数据
            event_type: 事件类型
            
        Returns:
            发送是否成功
        """
        if not self.is_enabled():
            return False
            
        if not self.validate_config():
            return False
            
        try:
            # 格式化消息
            formatted_data = self.format_message_for_channel(template_data)
            
            # 构建钉钉消息
            message = self._build_dingtalk_message(formatted_data, event_type)
            
            # 发送消息
            return self._send_message(message)
            
        except Exception as e:
            self.logger.error(f"钉钉通知处理异常: {e}")
            return False
            
    def _build_dingtalk_message(self, data: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """构建钉钉消息格式
        
        Args:
            data: 消息数据
            event_type: 事件类型
            
        Returns:
            钉钉消息格式
        """
        # 获取基础信息
        title = data.get('title', '通知')
        content = data.get('content', data.get('message', ''))
        
        # 根据事件类型选择图标
        icons = {
            'permission': '🔐',
            'completion': '✅',
            'task_completion': '✅',
            'test': '🧪',
            'custom_event': '🔔',
            'rate_limit': '⚠️',
            'error': '❌',
            'session_start': '🚀',
            'idle_detected': '😴',
            'sensitive_operation': '🚨',
            'generic': '📢'
        }
        
        icon = icons.get(event_type, '📢')
        
        # 构建markdown文本
        markdown_text = f"## {icon} {title}\n\n{content}"
        
        # 添加额外信息
        if data.get('project'):
            markdown_text += f"\n\n**项目**: {data['project']}"
            
        if data.get('operation'):
            markdown_text += f"\n\n**操作**: {data['operation']}"
            
        if data.get('timestamp'):
            markdown_text += f"\n\n**时间**: {data['timestamp']}"
            
        # 截断过长内容
        markdown_text = self.truncate_content(markdown_text, 4000)
        
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown_text
            }
        }
        
    def get_max_content_length(self) -> int:
        """钉钉消息最大长度
        
        Returns:
            最大内容长度
        """
        return 4000
        
    def supports_rich_content(self) -> bool:
        """钉钉支持Markdown格式
        
        Returns:
            是否支持富文本
        """
        return True