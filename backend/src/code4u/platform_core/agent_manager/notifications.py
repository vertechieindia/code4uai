"""Notification Service - Push notifications to devices and channels."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    """Types of notifications."""
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_APPROVED = "review_approved"
    REVIEW_REJECTED = "review_rejected"
    APPROVAL_NEEDED = "approval_needed"
    MEETING_SUMMARY = "meeting_summary"
    MENTION = "mention"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Notification priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    PUSH = "push"           # Mobile push
    EMAIL = "email"         # Email
    IN_APP = "in_app"       # In-app notification
    SLACK = "slack"         # Slack
    TEAMS = "teams"         # Teams
    DISCORD = "discord"     # Discord
    SMS = "sms"             # SMS


@dataclass
class Notification:
    """A notification."""
    id: str
    user_id: str
    
    # Content
    type: NotificationType
    title: str
    body: str
    
    # Priority
    priority: NotificationPriority = NotificationPriority.NORMAL
    
    # Context
    task_id: Optional[str] = None
    approval_id: Optional[str] = None
    meeting_id: Optional[str] = None
    
    # Action
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    
    # Delivery
    channels: List[NotificationChannel] = field(default_factory=list)
    delivered_to: List[str] = field(default_factory=list)
    
    # Status
    read: bool = False
    read_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


@dataclass
class NotificationPreferences:
    """User notification preferences."""
    user_id: str
    
    # Enabled channels
    channels: List[NotificationChannel] = field(default_factory=lambda: [
        NotificationChannel.PUSH,
        NotificationChannel.IN_APP,
    ])
    
    # Type preferences (which types to receive)
    enabled_types: List[NotificationType] = field(default_factory=lambda: list(NotificationType))
    
    # Do not disturb
    dnd_enabled: bool = False
    dnd_start: Optional[str] = None  # "22:00"
    dnd_end: Optional[str] = None    # "08:00"
    
    # Frequency
    batch_notifications: bool = False
    batch_interval_minutes: int = 30
    
    # Email
    email: Optional[str] = None
    
    # Mobile
    push_token: Optional[str] = None
    
    # Integrations
    slack_user_id: Optional[str] = None
    teams_user_id: Optional[str] = None


class NotificationService:
    """
    Notification service for code4u.ai.
    
    Delivers notifications across:
    - Mobile push (iOS/Android)
    - Email
    - In-app
    - Slack/Teams/Discord
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize notification service."""
        self.tenant_id = tenant_id
        self._notifications: Dict[str, List[Notification]] = {}  # user_id -> notifications
        self._preferences: Dict[str, NotificationPreferences] = {}
    
    async def send(
        self,
        user_id: str,
        type: NotificationType,
        title: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        task_id: Optional[str] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        channels: Optional[List[NotificationChannel]] = None,
    ) -> Notification:
        """Send a notification.
        
        Args:
            user_id: User to notify
            type: Notification type
            title: Notification title
            body: Notification body
            priority: Priority level
            task_id: Related task
            action_url: URL for action button
            action_label: Label for action button
            channels: Override delivery channels
            
        Returns:
            Created notification
        """
        # Get preferences
        prefs = self._preferences.get(user_id) or NotificationPreferences(user_id=user_id)
        
        # Check if type is enabled
        if type not in prefs.enabled_types:
            return None
        
        # Check DND
        if prefs.dnd_enabled and self._is_dnd_active(prefs):
            # Queue for later or skip based on priority
            if priority not in [NotificationPriority.HIGH, NotificationPriority.URGENT]:
                return None
        
        # Determine channels
        delivery_channels = channels or prefs.channels
        
        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            priority=priority,
            task_id=task_id,
            action_url=action_url,
            action_label=action_label,
            channels=delivery_channels,
        )
        
        # Store
        if user_id not in self._notifications:
            self._notifications[user_id] = []
        self._notifications[user_id].insert(0, notification)
        
        # Deliver
        await self._deliver(notification, prefs)
        
        return notification
    
    async def _deliver(
        self,
        notification: Notification,
        prefs: NotificationPreferences,
    ) -> None:
        """Deliver notification to channels."""
        for channel in notification.channels:
            try:
                if channel == NotificationChannel.PUSH:
                    await self._send_push(notification, prefs)
                elif channel == NotificationChannel.EMAIL:
                    await self._send_email(notification, prefs)
                elif channel == NotificationChannel.IN_APP:
                    # Already stored, websocket will pick it up
                    pass
                elif channel == NotificationChannel.SLACK:
                    await self._send_slack(notification, prefs)
                elif channel == NotificationChannel.TEAMS:
                    await self._send_teams(notification, prefs)
                
                notification.delivered_to.append(channel.value)
            except Exception:
                pass
    
    async def _send_push(
        self,
        notification: Notification,
        prefs: NotificationPreferences,
    ) -> None:
        """Send push notification."""
        if not prefs.push_token:
            return
        
        # Would use Firebase/APNs
        # await firebase.send(
        #     token=prefs.push_token,
        #     title=notification.title,
        #     body=notification.body,
        #     data={"task_id": notification.task_id},
        # )
    
    async def _send_email(
        self,
        notification: Notification,
        prefs: NotificationPreferences,
    ) -> None:
        """Send email notification."""
        if not prefs.email:
            return
        
        # Would use email service
        # await email_service.send(
        #     to=prefs.email,
        #     subject=notification.title,
        #     body=notification.body,
        # )
    
    async def _send_slack(
        self,
        notification: Notification,
        prefs: NotificationPreferences,
    ) -> None:
        """Send Slack notification."""
        if not prefs.slack_user_id:
            return
        
        # Would use Slack API
        # await slack.send_dm(
        #     user_id=prefs.slack_user_id,
        #     text=f"*{notification.title}*\n{notification.body}",
        # )
    
    async def _send_teams(
        self,
        notification: Notification,
        prefs: NotificationPreferences,
    ) -> None:
        """Send Teams notification."""
        if not prefs.teams_user_id:
            return
        
        # Would use Teams API
    
    def _is_dnd_active(self, prefs: NotificationPreferences) -> bool:
        """Check if DND is currently active."""
        if not prefs.dnd_start or not prefs.dnd_end:
            return False
        
        now = datetime.utcnow().strftime("%H:%M")
        
        if prefs.dnd_start <= prefs.dnd_end:
            # Same day range (e.g., 09:00-17:00)
            return prefs.dnd_start <= now <= prefs.dnd_end
        else:
            # Overnight range (e.g., 22:00-08:00)
            return now >= prefs.dnd_start or now <= prefs.dnd_end
    
    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Notification]:
        """Get notifications for a user.
        
        Args:
            user_id: User identifier
            unread_only: Only unread notifications
            limit: Maximum number to return
            
        Returns:
            List of notifications
        """
        notifications = self._notifications.get(user_id, [])
        
        if unread_only:
            notifications = [n for n in notifications if not n.read]
        
        return notifications[:limit]
    
    def mark_read(
        self,
        notification_id: str,
        user_id: str,
    ) -> bool:
        """Mark a notification as read."""
        for notif in self._notifications.get(user_id, []):
            if notif.id == notification_id:
                notif.read = True
                notif.read_at = datetime.utcnow()
                return True
        return False
    
    def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read."""
        count = 0
        for notif in self._notifications.get(user_id, []):
            if not notif.read:
                notif.read = True
                notif.read_at = datetime.utcnow()
                count += 1
        return count
    
    def update_preferences(
        self,
        user_id: str,
        **updates,
    ) -> NotificationPreferences:
        """Update notification preferences."""
        prefs = self._preferences.get(user_id) or NotificationPreferences(user_id=user_id)
        
        for key, value in updates.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)
        
        self._preferences[user_id] = prefs
        return prefs
    
    def get_preferences(self, user_id: str) -> NotificationPreferences:
        """Get notification preferences."""
        return self._preferences.get(user_id) or NotificationPreferences(user_id=user_id)
    
    def get_unread_count(self, user_id: str) -> int:
        """Get unread notification count."""
        return len([n for n in self._notifications.get(user_id, []) if not n.read])

