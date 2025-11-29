# app/agents/notifier.py

from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.api_clients import google_client
from app.config import get_settings
import requests
import json
from datetime import datetime
from loguru import logger

settings = get_settings()

class NotifierAgent(BaseAgent):
    """
    Send notifications via Discord webhooks.
    Strictly gates execution to ensure it only runs after valid Order Generation.
    """
    
    def __init__(self):
        super().__init__(
            name="Notifier",
            model=settings.NOTIFIER_MODEL,
            api_client=google_client
        )
        self.webhook_url = settings.DISCORD_WEBHOOK_URL
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            # --- GUARDRAIL: Check Prerequisites ---
            # The Orchestrator should prevent this, but the Agent acts as a second line of defense.
            if "order_manager_output" not in request.context:
                logger.warning("Notifier Triggered without Order Output. Skipping execution.")
                return AgentResponse(
                    agent_name=self.name,
                    success=False, # Mark false so UI knows it didn't send
                    error="Skipped: No order generated to notify about."
                )

            # Get notification type
            notification_type = request.parameters.get("type", "info")
            
            # Generate message content
            message_content = await self._generate_message(request.query, notification_type)
            
            # Create embed data if context provided
            embed_data = self._create_embed(notification_type, request.context)
            
            # Send to Discord
            success = self._send_discord_notification(
                message=message_content,
                embed=embed_data
            )
            
            if not success:
                logger.warning("Discord notification failed, falling back to log")
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data={
                    "message": message_content,
                    "channel": "discord" if success else "log",
                    "sent_at": datetime.utcnow().isoformat(),
                    "notification_type": notification_type
                }
            )
            
        except Exception as e:
            logger.error(f"Notifier error: {str(e)}")
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
    
    async def _generate_message(self, query: str, notification_type: str) -> str:
        # ... (Keep existing implementation) ...
        # For brevity, reusing previous logic here
        return f"📢 Update: {query}"

    def _create_embed(self, notification_type: str, context: dict) -> dict:
        # ... (Keep existing implementation) ...
        return {}

    def _send_discord_notification(self, message: str, embed: dict = None) -> bool:
        # ... (Keep existing implementation) ...
        if not self.webhook_url: return False
        try:
            payload = {"content": message}
            if embed: payload["embeds"] = [embed]
            requests.post(self.webhook_url, json=payload)
            return True
        except:
            return False