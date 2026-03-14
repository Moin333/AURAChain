# app/core/workflow_visualizer.py
"""
Workflow Visualization — render DAG as JSON graph and Mermaid diagrams.

Uses networkx for graph operations. No frontend rendering — returns
structured data for API consumers and debugging tools.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx not installed — workflow visualization disabled")


class WorkflowVisualizer:
    """Render workflow plans as graph structures."""
    
    def build_graph(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a graph representation from a workflow plan.
        
        Returns:
            {
                "nodes": [{"id": "agent_name", "level": 0, ...}],
                "edges": [{"from": "a", "to": "b"}],
                "levels": [[...], [...]]
            }
        """
        execution_levels = plan.get("execution_levels", [])
        execution_plan = plan.get("execution_plan", [])
        
        nodes = []
        edges = []
        
        # Build nodes from levels
        agent_levels = {}
        for level_idx, level_agents in enumerate(execution_levels):
            for agent_name in level_agents:
                nodes.append({
                    "id": agent_name,
                    "level": level_idx,
                    "parallel_group": level_idx
                })
                agent_levels[agent_name] = level_idx
        
        # Build edges from execution_plan dependencies
        for step in execution_plan:
            agent = step.get("agent", "")
            depends_on = step.get("depends_on", [])
            for dep in depends_on:
                edges.append({"from": dep, "to": agent})
        
        # If no explicit depends_on, infer from levels
        if not edges and len(execution_levels) > 1:
            for i in range(1, len(execution_levels)):
                for agent in execution_levels[i]:
                    for prev_agent in execution_levels[i - 1]:
                        edges.append({"from": prev_agent, "to": agent})
        
        return {
            "nodes": nodes,
            "edges": edges,
            "levels": execution_levels,
            "total_agents": len(nodes),
            "total_levels": len(execution_levels)
        }
    
    def to_mermaid(self, plan: Dict[str, Any]) -> str:
        """
        Render workflow plan as a Mermaid diagram string.
        
        Example output:
            graph TD
                data_harvester --> trend_analyst
                data_harvester --> visualizer
                trend_analyst --> forecaster
                forecaster --> mcts_optimizer
        """
        graph = self.build_graph(plan)
        
        lines = ["graph TD"]
        
        # Add node labels
        for node in graph["nodes"]:
            node_id = node["id"].replace(" ", "_")
            display = node["id"].replace("_", " ").title()
            lines.append(f"    {node_id}[\"{display}\"]")
        
        # Add edges
        for edge in graph["edges"]:
            src = edge["from"].replace(" ", "_")
            tgt = edge["to"].replace(" ", "_")
            lines.append(f"    {src} --> {tgt}")
        
        return "\n".join(lines)
    
    def get_critical_path(self, plan: Dict[str, Any]) -> List[str]:
        """
        Compute the critical path (longest dependency chain) using networkx.
        
        Useful for performance tuning: the critical path determines
        minimum workflow execution time.
        """
        if not HAS_NETWORKX:
            return []
        
        try:
            graph_data = self.build_graph(plan)
            
            G = nx.DiGraph()
            for node in graph_data["nodes"]:
                G.add_node(node["id"])
            for edge in graph_data["edges"]:
                G.add_edge(edge["from"], edge["to"])
            
            if not nx.is_directed_acyclic_graph(G):
                logger.warning("Workflow graph has cycles — cannot compute critical path")
                return []
            
            # Find longest path in DAG
            longest = nx.dag_longest_path(G)
            return longest
            
        except Exception as e:
            logger.error(f"Failed to compute critical path: {e}")
            return []
    
    def get_execution_summary(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive execution summary for debugging.
        
        Combines graph structure, Mermaid diagram, and critical path.
        """
        graph = self.build_graph(plan)
        mermaid = self.to_mermaid(plan)
        critical_path = self.get_critical_path(plan)
        
        return {
            "graph": graph,
            "mermaid": mermaid,
            "critical_path": critical_path,
            "critical_path_length": len(critical_path)
        }


# Global instance
workflow_visualizer = WorkflowVisualizer()
