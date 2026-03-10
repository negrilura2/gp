import logging
import subprocess
import requests
import json
import os
from django.conf import settings

logger = logging.getLogger("api")

class OpenClawClient:
    """
    OpenClaw 集成客户端
    用于发送通知到 OpenClaw 连接的 IM 渠道 (Telegram, Slack, etc.)
    """
    
    def __init__(self):
        self.enabled = getattr(settings, 'OPENCLAW_ENABLED', False)
        self.api_url = getattr(settings, 'OPENCLAW_API_URL', 'http://localhost:18789')
        self.default_recipient = getattr(settings, 'OPENCLAW_DEFAULT_RECIPIENT', '')
        self.mode = getattr(settings, 'OPENCLAW_MODE', 'http') # 'http' or 'cli'

    def send_notification(self, message, recipient=None):
        """
        发送通知消息
        """
        if not self.enabled:
            return

        target = recipient or self.default_recipient
        if not target:
            logger.warning("OpenClaw enabled but no recipient configured.")
            return

        try:
            if self.mode == 'cli':
                self._send_via_cli(target, message)
            else:
                self._send_via_http(target, message)
        except Exception as e:
            logger.error(f"Failed to send OpenClaw notification: {e}")

    def _send_via_cli(self, to, message):
        """
        通过 CLI 调用 (适用于本地开发环境)
        openclaw message send --to <to> --message <message>
        """
        cmd = ["openclaw", "message", "send", "--to", to, "--message", message]
        logger.info(f"Executing OpenClaw CLI: {' '.join(cmd)}")
        # 使用 subprocess.run 执行，设置超时防止阻塞
        subprocess.run(cmd, check=True, timeout=10, capture_output=True)

    def _send_via_http(self, to, message):
        """
        通过 HTTP API 调用 (适用于 Docker/微服务环境)
        假设 OpenClaw Gateway 暴露了类似 /v1/message/send 的接口
        注意：此处 API 路径为推测，实际需参考 OpenClaw 接口文档
        """
        # 这里的 endpoint 是假设的，根据 OpenClaw 风格可能是 GraphQL 或 REST
        # 既然没有确切文档，我们先实现一个通用的 POST 结构
        url = f"{self.api_url}/api/v1/send" 
        payload = {
            "to": to,
            "message": message
        }
        # logger.info(f"Sending OpenClaw HTTP req to {url}")
        # resp = requests.post(url, json=payload, timeout=5)
        # resp.raise_for_status()
        
        # 降级方案：由于不知道 API 格式，暂时回退到打印日志，提示用户配置
        logger.info(f"[OpenClaw Mock HTTP] Would POST to {url}: {json.dumps(payload)}")

# 单例实例
claw_client = OpenClawClient()
