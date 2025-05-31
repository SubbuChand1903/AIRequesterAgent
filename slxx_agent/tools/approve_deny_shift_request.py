import logging
from datetime import datetime, date
from typing import Callable, TypedDict, Optional, List, Dict, Any
from kgraphplanner.tool_manager.abstract_tool import AbstractTool
from kgraphplanner.tool_manager.tool_request import ToolRequest
from kgraphplanner.tool_manager.tool_response import ToolResponse
from langchain_core.tools import tool

from slxx_agent.agent.agent_context import AgentContext
from slxx_agent.manager.slxx_manager import slxxManager

class ShiftRequestResponse(TypedDict):
    """Structure for shift request approval/denial response."""
    status: str  # "success" or "error"
    data: Optional[Dict[str, Any]]  # Response data if status is success and status_code is 200
    message: Optional[str]  # Error message if status is error
    status_code: Optional[int]  # HTTP status code if status is error

class ApproveDenyShiftRequest(AbstractTool):

    def __init__(self, config, manager: slxxManager, agent_context: AgentContext):
        super().__init__(config)
        self.manager = manager
        self.agent_context = agent_context


    def handle_request(self, tool_request: ToolRequest) -> ToolResponse:
        logger = logging.getLogger(__name__)

        # Get parameters from the request
        date_on = tool_request.get_parameter('date_on')
        request_for = tool_request.get_parameter('request_for')
        employee_id = tool_request.get_parameter('employee_id')
        shift_id = tool_request.get_parameter('shift_id')
        unit_id = tool_request.get_parameter('unit_id')
        position_id = tool_request.get_parameter('position_id')
        message_id = tool_request.get_parameter('message_id')

        try:
            request_date = datetime.strptime(date_on, "%m-%d-%Y").date()
            if request_date < date.today():
                return ToolResponse(
                    parameters={"results": {
                        "status": "error",
                        "data": None,
                        "message": f"Date {date_on} is in the past. Only requests for today and future are allowed to be approved or denied."
                    }}
                )
        except ValueError:
            return ToolResponse(
                parameters={"results": {
                    "status": "error",
                    "data": None,
                    "message": f"Invalid date format: {date_on}. Expected MM-DD-YYYY."
                }}
            )

        # Fetch schedule hours data with optional filters
        response = self.manager.approve_deny_shift_request(
            date_on=date_on,
            request_for=request_for, 
            employee_id=employee_id, 
            shift_id=shift_id, 
            unit_id=unit_id, 
            position_id=position_id, 
            message_id=message_id
        )
        logger.info(f"Approve Deny Response: {response}")
        # Build the ToolResponse
        tool_response = ToolResponse()
        tool_response.add_parameter("results", response)
        return tool_response

    def get_sample_text(self) -> str:
        return "Approve or Deny shift request"

    def get_tool_function(self) -> Callable:

        @tool
        def approve_deny_shift_request(
            date_on: str,
            request_for: str,
            employee_id: int,
            shift_id: int,
            unit_id: int,
            position_id: int,
            message_id: int
        ) -> ShiftRequestResponse:
            """
            Use this tool to either approve or deny shift request
            
            Args:
                date_on: Date for Open Shift request (Always in format MM-DD-YYYY)
                request_for: Either 'Approve' or 'Deny' based on user request
                employee_id: employee identifier from the request
                shift_id: shift identifier from the request
                unit_id: unit identifier from the request
                position_id: position identifier from the request
                message_id: message identifier from the request

            Returns:
                ShiftRequestResponse: Status of approve or deny
            """
            params = {
                'date_on': date_on,
                'request_for': request_for,
                'employee_id': employee_id,
                'shift_id': shift_id,
                'unit_id': unit_id,
                'position_id': position_id,
                'message_id': message_id
            }
            
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            
            tool_request = ToolRequest(parameters=params)
            tool_response = self.handle_request(tool_request)
            results = tool_response.get_parameter("results")

            return results

        return approve_deny_shift_request