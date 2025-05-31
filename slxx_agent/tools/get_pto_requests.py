import logging
from typing import Callable, TypedDict, Optional, List, Dict, Any
from kgraphplanner.tool_manager.abstract_tool import AbstractTool
from kgraphplanner.tool_manager.tool_request import ToolRequest
from kgraphplanner.tool_manager.tool_response import ToolResponse
from langchain_core.tools import tool

from slxx_agent.agent.agent_context import AgentContext
from slxx_agent.manager.slxx_manager import slxxManager

class PTORequests(TypedDict):
    """Structure for schedule data grouped by position, shift, and unit."""
    leave_request_id: int
    employee_id: int
    employee_name: str
    department_id: int
    department_name: str
    position_id: int
    position_name: str
    start: str
    end: str
    reason: str
    status: str
    accruals: list

class GetPTORequests(AbstractTool):

    def __init__(self, config, manager: slxxManager, agent_context: AgentContext):
        super().__init__(config)
        self.manager = manager
        self.agent_context = agent_context

    def handle_request(self, tool_request: ToolRequest) -> ToolResponse:
        logger = logging.getLogger(__name__)

        # Get parameters from the request
        start_date = tool_request.get_parameter('start_date')
        end_date = tool_request.get_parameter('end_date')

        # Get the current org level ID from context
        org_level_id = self.agent_context.org_level_id

        # Fetch schedule hours data with optional filters
        pto_requests = self.manager.get_pto_requests(
            org_level_id=org_level_id,
            start_date=start_date,
            end_date=end_date
        )
        logger.info(f"PTO Requests Response: {pto_requests}")
        # Build the ToolResponse
        tool_response = ToolResponse()
        tool_response.add_parameter("results", pto_requests)
        pto_requests_tool_data = {
            "type": "PTO Requests Response Data",
            "Data": pto_requests
        }
        self.agent_context.context_data.append(pto_requests_tool_data)
        return tool_response

    def get_sample_text(self) -> str:
        return "Get PTO requests"

    def get_tool_function(self) -> Callable:

        @tool
        def get_pto_requests(
            start_date: str, end_date: str
        ) -> List[PTORequests]:
            """
            Use this tool to retrieve PTO requests submitted by employees(This will return just the list of PTO requests, details can be taken from another tool). If only one date is given then start date and end date will be the same.
            Always use date in MM-DD-YYYY format
            
            Args:
                start_date: Start date for PTO requests (MM-DD-YYYY) - REQUIRED
                end_date: End date for PTO requests (MM-DD-YYYY) - REQUIRED

            Returns:
                List[PTORequests]
            """
            params = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            
            tool_request = ToolRequest(parameters=params)
            tool_response = self.handle_request(tool_request)
            results = tool_response.get_parameter("results")

            return results

        return get_pto_requests