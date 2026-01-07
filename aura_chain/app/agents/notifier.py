# app/agents/notifier.py
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.api_clients import groq_client
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
            api_client=groq_client
        )
        self.webhook_url = settings.DISCORD_WEBHOOK_URL
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            # --- GUARDRAIL: Check Prerequisites ---
            if "order_manager_output" not in request.context:
                logger.warning("Notifier Triggered without Order Output. Skipping execution.")
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="Skipped: No order generated to notify about."
                )

            # Get notification type
            notification_type = request.parameters.get("type", "info")
            
            # Generate message content using Groq
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
        """Use LLM to draft a professional notification"""
        prompt = f"""You are a Supply Chain Notification Bot.
        
        Draft a short, professional {notification_type} notification regarding: "{query}"
        
        Rules:
        - Keep it under 280 characters if possible.
        - Use urgency appropriate to the type ({notification_type}).
        - No markdown formatting in the text body.
        """
        
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                max_tokens=150
            )
            return response.get("text", f"Update: {query}")
        except Exception:
            return f"Update: {query}"

    def _create_embed(self, notification_type: str, context: dict) -> dict:
        """Create Discord embed structure"""
        color_map = {
            "info": 3447003,    # Blue
            "warning": 16776960, # Yellow
            "alert": 15158332,   # Red
            "success": 3066993   # Green
        }
        
        embed = {
            "title": f"Supply Chain {notification_type.title()}",
            "color": color_map.get(notification_type, 3447003),
            "timestamp": datetime.utcnow().isoformat(),
            "fields": []
        }
        
        # Add order details if available
        if "order_manager_output" in context:
            order = context["order_manager_output"].get("order_details", {})
            if order:
                embed["fields"].append({
                    "name": "Order Details",
                    "value": str(order)[:1024],
                    "inline": False
                })
                
        return embed

    def _send_discord_notification(self, message: str, embed: dict = None) -> bool:
        """Post to Discord Webhook"""
        if not self.webhook_url:
            logger.warning("No Discord Webhook URL configured")
            return False
            
        try:
            payload = {"content": message}
            if embed:
                payload["embeds"] = [embed]
            
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Failed to send Discord webhook: {e}")
            return False