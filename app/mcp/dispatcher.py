import time
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.mcp.inventory_server import InventoryMCPServer
from app.mcp.analytics_server import AnalyticsMCPServer
from app.mcp.pool_server import PoolMCPServer
from app.mcp.knowledge_server import KnowledgeMCPServer
from app.mcp.registry_server import RegistryMCPServer
from app.database.models import AgentToolCall
from app.core.logging import logger

# Explicit Tool-to-Server Mapping
TOOL_REGISTRY = {
    # Inventory MCP
    "get_stock": (InventoryMCPServer.get_stock, True),  # (function, requires_business_id)
    "list_low_stock": (InventoryMCPServer.list_low_stock, True),
    "record_sale": (InventoryMCPServer.record_sale, True),
    "record_purchase": (InventoryMCPServer.record_purchase, True),
    "receive_delivery": (InventoryMCPServer.receive_delivery, True),
    "adjust_stock": (InventoryMCPServer.adjust_stock, True),
    "undo_event": (InventoryMCPServer.undo_event, True),
    # Analytics MCP
    "get_metric": (AnalyticsMCPServer.get_metric, True),
    "get_sales_summary": (AnalyticsMCPServer.get_sales_summary, True),
    "list_alerts": (AnalyticsMCPServer.list_alerts, True),
    # Pool MCP
    "draft_group_request": (PoolMCPServer.draft_group_request, True),
    "get_bid_status": (PoolMCPServer.get_bid_status, False),
    "compare_bids": (PoolMCPServer.compare_bids, False),
    "submit_group_request": (PoolMCPServer.submit_group_request, True),
    # Knowledge MCP
    "search_knowledge": (KnowledgeMCPServer.search_knowledge, True),
    "match_product": (KnowledgeMCPServer.match_product, True),
    # Registry MCP
    "verify_credential": (RegistryMCPServer.verify_credential, False),
    "propose_anchor": (RegistryMCPServer.propose_anchor, False),
}

# Strict Agent Tool Allowlists
AGENT_ALLOWLISTS = {
    "capture": ["match_product", "record_sale", "get_stock"],
    "inventory": ["get_stock", "list_low_stock", "adjust_stock"],
    "analytics": ["get_metric", "get_sales_summary", "list_alerts", "get_stock"],
    "procurement": ["draft_group_request", "get_bid_status", "compare_bids", "submit_group_request", "list_low_stock"],
    "policy": ["undo_event"],
    "verification": ["verify_credential", "propose_anchor", "receive_delivery"],
}


class MCPDispatcher:
    @classmethod
    def dispatch(
        cls,
        db: Session,
        agent_name: str,
        tool_name: str,
        args: Dict[str, Any],
        business_id: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches tool call to appropriate MCP server with strict security:
        - Validates agent tool allowlist
        - Injects verified server-side business_id (models cannot choose tenant ID)
        - Logs execution in agent_tool_calls
        """
        start_time = time.time()

        # Enforce Tool Allowlist
        allowed_tools = AGENT_ALLOWLISTS.get(agent_name, [])
        if tool_name not in allowed_tools:
            latency = time.time() - start_time
            if task_id:
                call_log = AgentToolCall(
                    task_id=task_id,
                    agent=agent_name,
                    tool=tool_name,
                    args_json=args,
                    status="rejected_policy",
                    latency=latency
                )
                db.add(call_log)
                db.commit()
            raise PermissionError(
                f"Security Policy Violation: Agent '{agent_name}' is not authorized to call tool '{tool_name}'."
            )

        if tool_name not in TOOL_REGISTRY:
            raise KeyError(f"Tool '{tool_name}' does not exist on any registered MCP server.")

        func, req_biz = TOOL_REGISTRY[tool_name]

        # Call function with verified business_id
        try:
            if req_biz:
                result = func(db=db, business_id=business_id, **args)
            else:
                result = func(db=db, **args) if "db" in func.__code__.co_varnames else func(**args)

            latency = time.time() - start_time
            if task_id:
                call_log = AgentToolCall(
                    task_id=task_id,
                    agent=agent_name,
                    tool=tool_name,
                    args_json=args,
                    status="executed",
                    latency=latency
                )
                db.add(call_log)
                db.commit()
            return result
        except Exception as e:
            latency = time.time() - start_time
            if task_id:
                call_log = AgentToolCall(
                    task_id=task_id,
                    agent=agent_name,
                    tool=tool_name,
                    args_json=args,
                    status="failed",
                    latency=latency
                )
                db.add(call_log)
                db.commit()
            raise e
