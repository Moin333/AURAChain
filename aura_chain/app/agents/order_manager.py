# app/agents/order_manager.py
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.api_clients import groq_client
from app.config import get_settings
import json

settings = get_settings()

class OrderManagerAgent(BaseAgent):
    """Order processing using Gemini Flash Lite"""
    
    def __init__(self):
        super().__init__(
            name="OrderManager",
            model=settings.ORDER_MANAGER_MODEL,
            api_client=groq_client
        )
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            prompt = f"""Process this order request and create a plan:

{request.query}

Parameters: {json.dumps(request.parameters)}

Provide a detailed order processing plan."""
            
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.3
            )
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data={"plan": response.get("text", "Order processing plan")}
            )
            
        except Exception as e:
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )