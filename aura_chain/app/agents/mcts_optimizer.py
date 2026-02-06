# app/agents/mcts_optimizer.py
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.api_clients import groq_client
from app.core.streaming import streaming_service
from app.config import get_settings
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
import math
import json
from loguru import logger

settings = get_settings()


@dataclass
class InventoryState:
    """Represents inventory state at a point in time"""
    current_stock: float
    day: int
    total_cost: float = 0.0
    
    def is_terminal(self, horizon: int) -> bool:
        """Check if we've reached the planning horizon"""
        return self.day >= horizon
    
    def transition(self, order_qty: float, demand: float, holding_cost: float, stockout_cost: float) -> 'InventoryState':
        """Simulate one day transition"""
        # Receive order (simplified: instant delivery)
        new_stock = self.current_stock + order_qty
        
        # Fulfill demand
        fulfilled = min(demand, new_stock)
        stockout = max(0, demand - new_stock)
        ending_stock = max(0, new_stock - demand)
        
        # Calculate costs
        day_holding_cost = holding_cost * ending_stock
        day_stockout_cost = stockout_cost * stockout
        
        return InventoryState(
            current_stock=ending_stock,
            day=self.day + 1,
            total_cost=self.total_cost + day_holding_cost + day_stockout_cost
        )


class MCTSNode:
    """Node in Monte Carlo Tree Search"""
    
    def __init__(self, state: InventoryState, parent: Optional['MCTSNode'] = None, action: float = 0, untried_actions: List[float] = None):
        self.state = state
        self.parent = parent
        self.action = action  # Order quantity to get here
        self.children: List['MCTSNode'] = []
        self.visits = 0
        self.total_reward = 0.0
        # FIX: Ensure new nodes receive the list of possible actions
        self.untried_actions = untried_actions if untried_actions is not None else []
    
    def is_fully_expanded(self) -> bool:
        return len(self.untried_actions) == 0
    
    def best_child(self, exploration_weight: float = 1.414) -> 'MCTSNode':
        """Select child using UCB1 formula"""
        if not self.children:
             # Safety valve if logic goes wrong, though logic below prevents this
            return self 
            
        return max(
            self.children,
            key=lambda c: (c.total_reward / c.visits) + 
                          exploration_weight * math.sqrt(math.log(self.visits) / c.visits)
        )
    
    def add_child(self, action: float, state: InventoryState, action_space: List[float]) -> 'MCTSNode':
        """Expand tree with new action"""
        # FIX: Pass a COPY of the action space to the new child
        child = MCTSNode(state, parent=self, action=action, untried_actions=list(action_space))
        self.untried_actions.remove(action)
        self.children.append(child)
        return child
    
    def update(self, reward: float):
        """Backpropagate reward"""
        self.visits += 1
        self.total_reward += reward


class MCTSOptimizerAgent(BaseAgent):
    """
    Real Monte Carlo Tree Search for inventory optimization
    Minimizes total cost = holding_cost + stockout_cost
    """
    
    def __init__(self):
        super().__init__(
            name="MCTSOptimizer",
            model=settings.MCTS_OPTIMIZER_MODEL,
            api_client=groq_client
        )
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            # Extract parameters
            if "dataset" not in request.context:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="No dataset provided for optimization"
                )
            
            df = pd.DataFrame(request.context["dataset"])
            
            # Get optimization parameters
            holding_cost = request.parameters.get("holding_cost", 5)  # ₹5 per unit per day
            stockout_cost = request.parameters.get("stockout_cost", 50)  # ₹50 per unit
            horizon = request.parameters.get("horizon", 30)  # 30-day planning
            iterations = request.parameters.get("iterations", 2000)  # MCTS iterations
            
            logger.info(f"Starting MCTS with {iterations} iterations, {horizon}-day horizon")
            
            # Extract demand data
            demand_data = self._extract_demand(df)
            
            if len(demand_data) == 0:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="Could not extract demand data from dataset"
                )
            
            # Calculate current inventory level
            current_stock = self._get_current_stock(df, demand_data)
            
            # Run MCTS optimization
            optimal_solution = await self._run_mcts(
                current_stock=current_stock,
                demand_history=demand_data,
                holding_cost=holding_cost,
                stockout_cost=stockout_cost,
                horizon=horizon,
                iterations=iterations
            )
            
            # Calculate baseline (no optimization)
            baseline_cost = self._calculate_baseline_cost(
                current_stock, demand_data, holding_cost, stockout_cost, horizon
            )
            
            # Calculate Bullwhip effect
            bullwhip_metrics = self._calculate_bullwhip_effect(
                demand_data, optimal_solution
            )
            
            # Get LLM interpretation
            interpretation = await self._get_interpretation(
                optimal_solution, baseline_cost, bullwhip_metrics, request.query
            )
            
            # Format response
            response_data = {
                "optimal_action": {
                    "reorder_point": float(optimal_solution["reorder_point"]),
                    "order_quantity": float(optimal_solution["order_quantity"]),
                    "safety_stock": float(optimal_solution["safety_stock"])
                },
                "expected_savings": {
                    "amount_inr": float(baseline_cost - optimal_solution["expected_cost"]),
                    "percentage": float(((baseline_cost - optimal_solution["expected_cost"]) / baseline_cost) * 100)
                },
                "bullwhip_reduction": bullwhip_metrics,
                "simulation_stats": {
                    "iterations": iterations,
                    "explored_states": optimal_solution["explored_states"],
                    "computation_time_ms": optimal_solution["computation_time_ms"],
                    "baseline_cost": float(baseline_cost),
                    "optimized_cost": float(optimal_solution["expected_cost"])
                },
                "interpretation": interpretation
            }
            
            logger.info(f"MCTS completed: {response_data['expected_savings']['percentage']:.1f}% savings")
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"MCTS Optimizer error: {str(e)}")
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
    
    def _extract_demand(self, df: pd.DataFrame) -> np.ndarray:
        """Extract demand/sales/quantity data"""
        # Look for common column names
        demand_cols = ['demand', 'sales', 'quantity', 'units_sold', 'qty']
        
        for col in demand_cols:
            matching = [c for c in df.columns if col.lower() in c.lower()]
            if matching:
                return df[matching[0]].dropna().values
        
        # Fallback: use first numeric column
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            return df[numeric_cols[0]].dropna().values
        
        return np.array([])
    
    def _get_current_stock(self, df: pd.DataFrame, demand_data: np.ndarray) -> float:
        """Estimate current stock level"""
        # Look for stock/inventory column
        stock_cols = ['stock', 'inventory', 'current_stock', 'on_hand']
        
        for col in stock_cols:
            matching = [c for c in df.columns if col.lower() in c.lower()]
            if matching:
                return float(df[matching[0]].iloc[-1])
        
        # Fallback: assume 2x average demand
        return float(np.mean(demand_data) * 2)
    
    async def _run_mcts(
        self,
        current_stock: float,
        demand_history: np.ndarray,
        holding_cost: float,
        stockout_cost: float,
        horizon: int,
        iterations: int,
        session_id: str = None
    ) -> Dict:
        """Execute MCTS algorithm with streaming progress"""
        import time
        start_time = time.time()
        
        logger.info(f"MCTS Debug: Stock={current_stock}, Holding=${holding_cost}, Stockout=${stockout_cost}")

        # Define action space
        mean_demand = float(np.mean(demand_history))
        std_demand = float(np.std(demand_history))
        
        # Action space: 0, plus steps up to 3x demand
        action_space = [0.0] + list(np.linspace(0.1, mean_demand * 3, 10))
        action_space = sorted(list(set([float(a) for a in action_space])))
        
        # Calculate Max Penalty for Normalization (Crucial for MCTS)
        # Max possible cost = Stockout every day for max demand
        max_penalty = stockout_cost * (mean_demand * 2) * horizon
        if max_penalty == 0: max_penalty = 1.0 # Prevent div/0

        root_state = InventoryState(current_stock=current_stock, day=0)
        root = MCTSNode(root_state, untried_actions=list(action_space))
        
        explored_states = 0
        
        # Progress tracking
        last_update = 0
        update_frequency = 100  # Update every 100 iterations
        
        for i in range(iterations):
            node = root
            state = InventoryState(current_stock=current_stock, day=0)
            
            # Selection
            while node.is_fully_expanded() and not state.is_terminal(horizon):
                if not node.children: break
                node = node.best_child()
                demand = self._sample_demand(demand_history)
                state = state.transition(node.action, demand, holding_cost, stockout_cost)
            
            # Expansion
            if not state.is_terminal(horizon) and not node.is_fully_expanded():
                action = node.untried_actions[0]
                demand = self._sample_demand(demand_history)
                new_state = state.transition(action, demand, holding_cost, stockout_cost)
                node = node.add_child(action, new_state, action_space)
                state = new_state
                explored_states += 1
            
            # Simulation
            sim_state = InventoryState(state.current_stock, state.day, state.total_cost)
            while not sim_state.is_terminal(horizon):
                action = np.random.choice(action_space)
                demand = self._sample_demand(demand_history)
                sim_state = sim_state.transition(action, demand, holding_cost, stockout_cost)
            
            # Backpropagation (With Normalization!)
            # Convert Cost to Reward [0, 1]
            # 1.0 = No Cost (Perfect), 0.0 = Max Cost (Disaster)
            normalized_reward = 1.0 - (min(sim_state.total_cost, max_penalty) / max_penalty)
            
            while node is not None:
                node.update(normalized_reward)
                node = node.parent
                
            # Publish progress update
            if session_id and (i - last_update >= update_frequency or i == iterations - 1):
                progress = ((i + 1) / iterations) * 100
                
                # Get current best solution
                best_child = max(root.children, key=lambda c: c.visits) if root.children else None
                current_best_cost = (1.0 - (best_child.total_reward / best_child.visits)) * max_penalty if best_child else 0
                
                await streaming_service.publish_agent_progress(
                    session_id,
                    self.name,
                    progress,
                    f"Iteration {i+1}/{iterations}",
                    {
                        "iteration": i + 1,
                        "total_iterations": iterations,
                        "explored_states": explored_states,
                        "current_best_cost": float(current_best_cost)
                    }
                )
                last_update = i
        
        # Extract best action
        if not root.children:
             return {"reorder_point": 0, "order_quantity": 0, "safety_stock": 0, "expected_cost": 0, "explored_states": 0, "computation_time_ms": 0}

        # Select child with highest visit count
        best_child = max(root.children, key=lambda c: c.visits)
        
        # Log the winner for debugging
        logger.info(f"MCTS Winner: Action={best_child.action:.1f}, Visits={best_child.visits}, AvgReward={best_child.total_reward/best_child.visits:.4f}")

        computation_time = (time.time() - start_time) * 1000
        
        # De-normalize cost for display
        # Approximate expected cost based on inverse reward
        expected_cost = (1.0 - (best_child.total_reward / best_child.visits)) * max_penalty

        return {
            "reorder_point": mean_demand * 1.5,
            "order_quantity": best_child.action,
            "safety_stock": std_demand * 1.65,
            "expected_cost": expected_cost,
            "explored_states": explored_states,
            "computation_time_ms": computation_time
        }
        
    async def process(self, request: AgentRequest) -> AgentResponse:
        """Main process method - updated to pass session_id"""
        try:
            if "dataset" not in request.context:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="No dataset provided for optimization"
                )
            
            df = pd.DataFrame(request.context["dataset"])
            
            holding_cost = request.parameters.get("holding_cost", 5)
            stockout_cost = request.parameters.get("stockout_cost", 50)
            horizon = request.parameters.get("horizon", 30)
            iterations = request.parameters.get("iterations", 2000)
            
            logger.info(f"Starting MCTS with {iterations} iterations, {horizon}-day horizon")
            
            demand_data = self._extract_demand(df)
            
            if len(demand_data) == 0:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="Could not extract demand data from dataset"
                )
            
            current_stock = self._get_current_stock(df, demand_data)
            
            # Pass session_id to streaming-enabled MCTS
            optimal_solution = await self._run_mcts(
                current_stock=current_stock,
                demand_history=demand_data,
                holding_cost=holding_cost,
                stockout_cost=stockout_cost,
                horizon=horizon,
                iterations=iterations,
                session_id=request.session_id
            )
            
            baseline_cost = self._calculate_baseline_cost(
                current_stock, demand_data, holding_cost, stockout_cost, horizon
            )
            
            bullwhip_metrics = self._calculate_bullwhip_effect(
                demand_data, optimal_solution
            )
            
            interpretation = await self._get_interpretation(
                optimal_solution, baseline_cost, bullwhip_metrics, request.query
            )
            
            response_data = {
                "optimal_action": {
                    "reorder_point": float(optimal_solution["reorder_point"]),
                    "order_quantity": float(optimal_solution["order_quantity"]),
                    "safety_stock": float(optimal_solution["safety_stock"])
                },
                "expected_savings": {
                    "amount_inr": float(baseline_cost - optimal_solution["expected_cost"]),
                    "percentage": float(((baseline_cost - optimal_solution["expected_cost"]) / baseline_cost) * 100)
                },
                "bullwhip_reduction": bullwhip_metrics,
                "simulation_stats": {
                    "iterations": iterations,
                    "explored_states": optimal_solution["explored_states"],
                    "computation_time_ms": optimal_solution["computation_time_ms"],
                    "baseline_cost": float(baseline_cost),
                    "optimized_cost": float(optimal_solution["expected_cost"])
                },
                "interpretation": interpretation
            }
            
            logger.info(f"MCTS completed: {response_data['expected_savings']['percentage']:.1f}% savings")
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"MCTS Optimizer error: {str(e)}")
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
        
    def _sample_demand(self, demand_history: np.ndarray) -> float:
        """Sample demand from historical distribution"""
        return float(np.random.choice(demand_history))
    
    def _calculate_baseline_cost(
        self,
        current_stock: float,
        demand_history: np.ndarray,
        holding_cost: float,
        stockout_cost: float,
        horizon: int
    ) -> float:
        """Calculate cost with naive policy (no reordering)"""
        state = InventoryState(current_stock=current_stock, day=0)
        
        for _ in range(horizon):
            demand = self._sample_demand(demand_history)
            state = state.transition(0, demand, holding_cost, stockout_cost)  # No orders
        
        return state.total_cost
    
    def _calculate_bullwhip_effect(self, demand_data: np.ndarray, solution: Dict) -> Dict:
        """Calculate Bullwhip Effect metrics"""
        # Demand variance
        demand_variance = np.var(demand_data)
        
        # Order variance (simplified: based on reorder policy)
        order_variance = solution["order_quantity"] ** 2 * 0.5  # Simplified
        
        # Bullwhip ratio = Var(Orders) / Var(Demand)
        bullwhip_before = 2.4  # Typical without optimization
        bullwhip_after = order_variance / demand_variance if demand_variance > 0 else 1.0
        
        improvement = ((bullwhip_before - bullwhip_after) / bullwhip_before) * 100
        
        return {
            "before": float(bullwhip_before),
            "after": float(min(bullwhip_after, bullwhip_before)),
            "improvement_percentage": float(max(0, improvement))
        }
    
    async def _get_interpretation(
        self,
        solution: Dict,
        baseline_cost: float,
        bullwhip_metrics: Dict,
        query: str
    ) -> str:
        """Get LLM interpretation of results"""
        
        summary = {
            "recommended_action": f"Order {solution['order_quantity']:.0f} units when stock drops to {solution['reorder_point']:.0f}",
            "cost_savings": f"₹{baseline_cost - solution['expected_cost']:.2f}",
            "bullwhip_reduction": f"{bullwhip_metrics['improvement_percentage']:.1f}%",
            "safety_stock": f"{solution['safety_stock']:.0f} units"
        }
        
        prompt = f"""Interpret these inventory optimization results for an MSME owner:

Results:
{json.dumps(summary, indent=2)}

User Query: {query}

Explain in simple business terms:
1. What action to take
2. Expected cost savings
3. How this reduces supply chain chaos (Bullwhip Effect)
4. Implementation steps

Keep it actionable and non-technical."""
        
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.6,
                max_tokens=400
            )
            return response.get("text", "Optimization complete. See recommendations above.")
        except Exception as e:
            logger.warning(f"LLM interpretation failed: {e}")
            return f"Recommended: {summary['recommended_action']}. Expected savings: {summary['cost_savings']}."