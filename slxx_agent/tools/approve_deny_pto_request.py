import logging
from datetime import datetime, date
from typing import Callable, TypedDict, Optional, List, Dict, Any
from kgraphplanner.tool_manager.abstract_tool import AbstractTool
from kgraphplanner.tool_manager.tool_request import ToolRequest
from kgraphplanner.tool_manager.tool_response import ToolResponse
from langchain_core.tools import tool

from slxx_agent.agent.agent_context import AgentContext
from slxx_agent.manager.slxx_manager import slxxManager

class PtoRequestResponse(TypedDict):
    """Structure for PTO request approval/denial response."""
    status: str  # "success" or "error"
    data: Optional[Dict[str, Any]]  # Response data if status is success and status_code is 200
    message: Optional[str]  # Error message if status is error
    status_code: Optional[int]  # HTTP status code if status is error

class ApproveDenyPTORequest(AbstractTool):

    def __init__(self, config, manager: slxxManager, agent_context: AgentContext):
        super().__init__(config)
        self.manager = manager
        self.agent_context = agent_context


    def handle_request(self, tool_request: ToolRequest) -> ToolResponse:
        logger = logging.getLogger(__name__)

        # Get parameters from the request
        leave_request_id = tool_request.get_parameter('leave_request_id')
        request_for = tool_request.get_parameter('request_for')
        comment = tool_request.get_parameter('comment')

        org_level_id = self.agent_context.org_level_id

        # Fetch schedule hours data with optional filters
        response = self.manager.approve_deny_pto_request(
            org_level_id=org_level_id,
            leave_request_id=leave_request_id,
            request_for=request_for, 
            comment=comment
        )
        logger.info(f"Approve Deny Response: {response}")
        # Build the ToolResponse
        tool_response = ToolResponse()
        tool_response.add_parameter("results", response)
        return tool_response

    def get_sample_text(self) -> str:
        return "Approve or Deny pto request"

    def get_tool_function(self) -> Callable:

        @tool
        def approve_deny_pto_request(
            leave_request_id: str,
            request_for: str,
            comment: str = None
        ) -> PtoRequestResponse:
            """
            Use this tool to either approve or deny PTO/leave requests. The leave request id here can be extracted from previously fetched leave requests.
            comment variable is optional here. Always ask if user wants to add a comment while approving or denying before caling the tool.
            
            Args:
                leave_request_id: Leave request id to approve or deny
                request_for: Either 'Approve' or 'Deny' based on user request
                comment: (optional) comment to add while approving or denying

            Returns:
                PtoRequestResponse: Status of approve or deny action
            """
            params = {
                'leave_request_id': leave_request_id,
                'request_for': request_for,
                'comment': comment
            }
            
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            
            tool_request = ToolRequest(parameters=params)
            tool_response = self.handle_request(tool_request)
            results = tool_response.get_parameter("results")

            return results

        return approve_deny_pto_request