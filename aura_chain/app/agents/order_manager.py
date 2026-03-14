# app/agents/order_manager.py
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.api_clients import groq_client
from app.core.streaming import streaming_service
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
            # Notify start
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    30,
                    "Drafting purchase order...",
                    {}
                )
                
            prompt = f"""Process this order request and create a plan:

{request.query}

Parameters: {json.dumps(request.parameters)}

Provide a detailed order processing plan."""
            
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.3
            )
            
            # Notify completion
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    90,
                    "Order plan ready for approval",
                    {}
                )
            
            order_plan = response.get("text", "Order processing plan")
            
            # Publish curated findings for downstream agents (e.g., Notifier)
            await self.publish_findings(request.workflow_id, {
                "order_created": True,
                "plan_summary": order_plan[:500] if len(order_plan) > 500 else order_plan
            })
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data={"plan": order_plan}
            )
            
        except Exception as e:
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )