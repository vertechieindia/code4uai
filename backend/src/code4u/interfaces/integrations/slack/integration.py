"""Slack integration for starting tasks and receiving notifications."""

from __future__ import annotations
import os
import re
import hashlib
import hmac
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class SlackConfig:
    """Slack integration configuration."""
    bot_token: str = ""
    signing_secret: str = ""
    app_id: str = ""
    
    # Channels
    notification_channel: Optional[str] = None
    
    # Features
    enable_slash_commands: bool = True
    enable_mentions: bool = True
    enable_threads: bool = True


@dataclass
class SlackMessage:
    """A Slack message."""
    channel: str
    user: str
    text: str
    thread_ts: Optional[str] = None
    ts: Optional[str] = None
    
    # Parsed
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)


class SlackIntegration:
    """
    Slack integration for code4u.ai.
    
    Features:
    - Slash commands (/code4u refactor, /code4u analyze)
    - Bot mentions (@code4u can you...)
    - Notifications (task complete, review needed)
    - Thread-based conversations
    """
    
    def __init__(self, config: Optional[SlackConfig] = None):
        """Initialize Slack integration.
        
        Args:
            config: Slack configuration
        """
        self.config = config or SlackConfig(
            bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
            signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
        )
        self._client = None
    
    def verify_request(
        self,
        signature: str,
        timestamp: str,
        body: bytes,
    ) -> bool:
        """Verify Slack request signature.
        
        Args:
            signature: X-Slack-Signature header
            timestamp: X-Slack-Request-Timestamp header
            body: Request body
            
        Returns:
            True if valid
        """
        if not self.config.signing_secret:
            return False
        
        # Check timestamp (prevent replay attacks)
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
        
        # Compute signature
        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        computed = "v0=" + hmac.new(
            self.config.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(computed, signature)
    
    async def handle_slash_command(
        self,
        command: str,
        text: str,
        user_id: str,
        channel_id: str,
        response_url: str,
    ) -> Dict[str, Any]:
        """Handle a slash command.
        
        Args:
            command: The command (e.g., /code4u)
            text: Command text
            user_id: Slack user ID
            channel_id: Channel ID
            response_url: URL for async response
            
        Returns:
            Immediate response
        """
        parts = text.strip().split(maxsplit=1)
        action = parts[0] if parts else "help"
        args = parts[1] if len(parts) > 1 else ""
        
        if action == "help":
            return self._help_response()
        
        elif action == "refactor":
            return await self._handle_refactor(args, user_id, channel_id, response_url)
        
        elif action == "analyze":
            return await self._handle_analyze(args, user_id, channel_id, response_url)
        
        elif action == "status":
            return await self._handle_status(user_id)
        
        else:
            return {
                "response_type": "ephemeral",
                "text": f"Unknown command: `{action}`. Use `/code4u help` for available commands.",
            }
    
    def _help_response(self) -> Dict[str, Any]:
        """Generate help response."""
        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🚀 code4u.ai Commands"}
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*Available Commands:*\n\n"
                            "• `/code4u refactor <description>` - Start a refactoring task\n"
                            "• `/code4u analyze <file>` - Analyze impact of changes\n"
                            "• `/code4u status` - Show running tasks\n"
                            "• `/code4u help` - Show this help\n\n"
                            "*Examples:*\n"
                            "• `/code4u refactor rename email to primaryEmail in users.py`\n"
                            "• `/code4u analyze api/routes.py`"
                        ),
                    },
                },
            ],
        }
    
    async def _handle_refactor(
        self,
        args: str,
        user_id: str,
        channel_id: str,
        response_url: str,
    ) -> Dict[str, Any]:
        """Handle refactor command."""
        if not args:
            return {
                "response_type": "ephemeral",
                "text": "Please provide a refactoring description. Example: `/code4u refactor rename email to primaryEmail`",
            }
        
        # Would trigger actual refactoring task
        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🔧 *Refactoring started*\n\n<@{user_id}> requested:\n> {args}",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "⏳ Analyzing codebase..."},
                    ],
                },
            ],
        }
    
    async def _handle_analyze(
        self,
        args: str,
        user_id: str,
        channel_id: str,
        response_url: str,
    ) -> Dict[str, Any]:
        """Handle analyze command."""
        if not args:
            return {
                "response_type": "ephemeral",
                "text": "Please provide a file to analyze. Example: `/code4u analyze api/routes.py`",
            }
        
        return {
            "response_type": "ephemeral",
            "text": f"🔍 Analyzing `{args}`... Results will be posted shortly.",
        }
    
    async def _handle_status(self, user_id: str) -> Dict[str, Any]:
        """Handle status command."""
        return {
            "response_type": "ephemeral",
            "text": "📊 No active tasks. Use `/code4u refactor` to start one.",
        }
    
    async def handle_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle Slack event.
        
        Args:
            event: Slack event payload
            
        Returns:
            Response or None
        """
        event_type = event.get("type")
        
        if event_type == "app_mention":
            return await self._handle_mention(event)
        
        elif event_type == "message":
            # Handle DMs or thread replies
            if event.get("channel_type") == "im":
                return await self._handle_dm(event)
        
        return None
    
    async def _handle_mention(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle @code4u mention."""
        text = event.get("text", "")
        user = event.get("user", "")
        channel = event.get("channel", "")
        
        # Remove the mention
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        
        return {
            "channel": channel,
            "text": f"Hi <@{user}>! I received your message: \"{text}\"\n\nUse `/code4u help` to see what I can do.",
            "thread_ts": event.get("ts"),
        }
    
    async def _handle_dm(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle direct message."""
        text = event.get("text", "")
        user = event.get("user", "")
        channel = event.get("channel", "")
        
        return {
            "channel": channel,
            "text": f"Thanks for your message! Use `/code4u help` to see available commands.",
        }
    
    async def send_notification(
        self,
        channel: str,
        message: str,
        blocks: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a notification to Slack.
        
        Args:
            channel: Channel ID
            message: Message text
            blocks: Optional rich blocks
            thread_ts: Thread timestamp for replies
            
        Returns:
            Slack API response
        """
        # Would use Slack API client
        return {
            "ok": True,
            "channel": channel,
            "message": {"text": message},
        }
    
    async def notify_task_complete(
        self,
        channel: str,
        user_id: str,
        task_description: str,
        success: bool,
        details: Optional[str] = None,
    ) -> None:
        """Notify that a task completed.
        
        Args:
            channel: Channel to notify
            user_id: User who started the task
            task_description: Task description
            success: Whether task succeeded
            details: Additional details
        """
        emoji = "✅" if success else "❌"
        status = "completed successfully" if success else "failed"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *Task {status}*\n\n<@{user_id}>'s task:\n> {task_description}",
                },
            },
        ]
        
        if details:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": details},
                ],
            })
        
        await self.send_notification(channel, f"Task {status}", blocks)
    
    async def notify_review_needed(
        self,
        channel: str,
        user_id: str,
        description: str,
        files_affected: int,
        review_url: str,
    ) -> None:
        """Notify that a review is needed.
        
        Args:
            channel: Channel to notify
            user_id: User who needs to review
            description: Change description
            files_affected: Number of files
            review_url: URL to review
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"👀 *Review requested*\n\n<@{user_id}>, please review:\n> {description}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"📁 {files_affected} files affected"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Review Changes"},
                        "url": review_url,
                        "style": "primary",
                    },
                ],
            },
        ]
        
        await self.send_notification(channel, "Review requested", blocks)

