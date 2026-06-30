import asyncio
import pandas as pd
import numpy as np
import json
from app.agents.mcts_optimizer import MCTSOptimizerAgent
from app.agents.base_agent import AgentRequest

async def test_single_sku():
    print("\n--- Testing Single SKU Fallback Path ---")
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', '2024-02-01', freq='D')
    demand = np.random.poisson(10, len(dates))
    
    df = pd.DataFrame({
        'date': dates,
        'sales': demand,
        'current_stock': [20] * len(dates)
    })
    
    agent = MCTSOptimizerAgent()
    request = AgentRequest(
        query="Optimize inventory to reduce costs",
        context={"dataset": df.to_dict('records')},
        parameters={
            "holding_cost": 2,
            "stockout_cost": 20,
            "horizon": 15,
            "iterations": 100
        }
    )
    
    response = await agent.process(request)
    print(f"Success: {response.success}")
    if response.success:
        data = response.data
        print(f"Optimal Action: {data['optimal_action']}")
        print(f"Expected Savings: {data['expected_savings']}")
        print(f"Bullwhip metrics: {json.dumps(data['bullwhip_reduction'], indent=2)}")
    else:
        print(f"Error: {response.error}")

async def test_multi_sku():
    print("\n--- Testing Multi-SKU Joint Replenishment Path ---")
    np.random.seed(42)
    
    # Create dates where multiple products are sold together to test Apriori mining
    data = []
    dates = pd.date_range('2024-01-01', '2024-01-15', freq='D')
    
    for dt in dates:
        # High probability of co-ordering Electronics and Accessories
        if np.random.rand() > 0.2:
            data.append({"date": dt.strftime('%Y-%m-%d'), "sales": int(np.random.poisson(15)), "product_category": "Electronics"})
            data.append({"date": dt.strftime('%Y-%m-%d'), "sales": int(np.random.poisson(10)), "product_category": "Accessories"})
        else:
            data.append({"date": dt.strftime('%Y-%m-%d'), "sales": int(np.random.poisson(5)), "product_category": "Furniture"})
            
    df = pd.DataFrame(data)
    
    agent = MCTSOptimizerAgent()
    request = AgentRequest(
        query="Optimize joint inventory for our product catalog",
        context={"dataset": df.to_dict('records')},
        parameters={
            "holding_cost": 2,
            "stockout_cost": 20,
            "horizon": 15,
            "iterations": 200
        }
    )
    
    response = await agent.process(request)
    print(f"Success: {response.success}")
    if response.success:
        data = response.data
        print("Optimal Action (SKU Groups):")
        print(json.dumps(data['optimal_action'], indent=2))
        print("SKU Associations (Apriori):")
        print(json.dumps(data['sku_associations'], indent=2))
        print("Bullwhip Reduction Tiers:")
        print(json.dumps(data['bullwhip_reduction'], indent=2))
    else:
        print(f"Error: {response.error}")

async def main():
    await test_single_sku()
    await test_multi_sku()

if __name__ == "__main__":
    asyncio.run(main())