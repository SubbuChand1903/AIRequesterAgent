import logging
from typing import Callable, TypedDict, Optional, List, Dict, Any
from kgraphplanner.tool_manager.abstract_tool import AbstractTool
from kgraphplanner.tool_manager.tool_request import ToolRequest
from kgraphplanner.tool_manager.tool_response import ToolResponse
from langchain_core.tools import tool

from slxx_agent.agent.agent_context import AgentContext
from slxx_agent.manager.slxx_manager import slxxManager

class ShiftRequests(TypedDict):
    """Structure for schedule data grouped by position, shift, and unit."""
    metadata: Dict[str, Any]
    request_messages: Dict[str, Any]

class GetShiftRequests(AbstractTool):

    def __init__(self, config, manager: slxxManager, agent_context: AgentContext):
        super().__init__(config)
        self.manager = manager
        self.agent_context = agent_context

    def handle_request(self, tool_request: ToolRequest) -> ToolResponse:
        logger = logging.getLogger(__name__)

        # Get parameters from the request
        date_on = tool_request.get_parameter('date_on')

        # Date is mandatory
        if not date_on:
            error_msg = "Date parameter is required"
            logger.error(error_msg)
            tool_response = ToolResponse()
            tool_response.add_parameter("error", error_msg)
            return tool_response

        # Get the current org level ID from context
        org_level_id = self.agent_context.org_level_id

        # Fetch schedule hours data with optional filters
        schedule_data = self.manager.get_shift_requests(
            date_on=date_on,
            org_level_id=org_level_id
        )
        logger.info(f"Shift Request Response: {schedule_data}")
        # Build the ToolResponse
        tool_response = ToolResponse()
        tool_response.add_parameter("results", schedule_data)
        schedule_tool_data = {
            "type": "Staff Request Response Data",
            "Data": schedule_data
        }
        self.agent_context.context_data.append(schedule_tool_data)
        return tool_response

    def get_sample_text(self) -> str:
        return "Get Open Shift Requests"

    def get_tool_function(self) -> Callable:

        @tool
        def get_shift_requests(
            date_on: str
        ) -> ShiftRequests:
            """
            Use this tool to retrieve open shift requests by employees
            
            Args:
                date_on: Date for Open Shift requests data (MM-DD-YYYY) - REQUIRED

            Returns:
                ShiftRequests: Dict with following fields
                        "metadata": {
                            "request date": str,
                            "shift_id": int,
                            "shift_name": str,
                            "shift_group_id": int,
                            "shift_group_name": str,
                            "position_id": int,
                            "position_name": str,
                            "unit_id": int,
                            "unit_name": str
                        }
                        "request messages": Dict
            """
            params = {
                'date_on': date_on
            }
            
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            
            tool_request = ToolRequest(parameters=params)
            tool_response = self.handle_request(tool_request)
            results = tool_response.get_parameter("results")

            return results

        return get_shift_requests