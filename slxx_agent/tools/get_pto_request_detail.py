import logging
from typing import Callable, TypedDict, Optional, List, Dict, Any
from kgraphplanner.tool_manager.abstract_tool import AbstractTool
from kgraphplanner.tool_manager.tool_request import ToolRequest
from kgraphplanner.tool_manager.tool_response import ToolResponse
from langchain_core.tools import tool

from slxx_agent.agent.agent_context import AgentContext
from slxx_agent.manager.slxx_manager import slxxManager

class PTORequestDetailMetadata(TypedDict):
    leave_request_id: int
    employee_id: int
    employee_name: str
    start_date: str
    end_date: str

class PTORequestDetailData(TypedDict):
    date: str
    shift_id: int
    shift_name: str
    shift_start: str
    shift_end: str
    shift_duration: str
    unit_id: int
    unit_name: str
    absence_code: str
    absence_description: str
    isAccruaBalanceAvailable: bool
    accrualBalance: float
    approvedAbsences: int
    submittedAbsences: int


class PTORequestDetail(TypedDict):
    """Structure for schedule data grouped by position, shift, and unit."""
    metadata: PTORequestDetailMetadata
    pto_request_details: PTORequestDetailData


class GetPTORequestDetail(AbstractTool):

    def __init__(self, config, manager: slxxManager, agent_context: AgentContext):
        super().__init__(config)
        self.manager = manager
        self.agent_context = agent_context

    def handle_request(self, tool_request: ToolRequest) -> ToolResponse:
        logger = logging.getLogger(__name__)

        # Get parameters from the request
        leave_request_id = tool_request.get_parameter('leave_request_id')
        employee_id = tool_request.get_parameter('employee_id')
        employee_name = tool_request.get_parameter('employee_name')
        start_date = tool_request.get_parameter('start_date')
        end_date = tool_request.get_parameter('end_date')

        # Get the current org level ID from context
        org_level_id = self.agent_context.org_level_id

        # Fetch schedule hours data with optional filters
        pto_requests = self.manager.get_pto_request_detail(
            org_level_id=org_level_id,
            leave_request_id=leave_request_id
        )
        logger.info(f"PTO Requests Details Response: {pto_requests}")

        pto_request_detail = {
              "metadata": {
                    "leave_request_id": leave_request_id,
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                    "start_date": start_date,
                    "end_date": end_date
              },
              "pto_request_details": pto_requests
        }
        # Build the ToolResponse
        tool_response = ToolResponse()
        tool_response.add_parameter("results", pto_request_detail)
        pto_requests_tool_data = {
            "type": "PTO Request Details Data",
            "Data": pto_request_detail
        }
        self.agent_context.context_data.append(pto_requests_tool_data)
        return tool_response

    def get_sample_text(self) -> str:
        return "Get PTO request Details"

    def get_tool_function(self) -> Callable:

        @tool
        def get_pto_request_details(
            leave_request_id: int, employee_id: int, employee_name: str, start_date: str, end_date: str
        ) -> List[PTORequestDetail]:
            """
            Use this tool to retrieve PTO requests details for a PTO request chosen by user. First the summary is displayed to the user and then when they choose one PTO then details can be displayed using this tool.
            
            Args:
                leave_request_id: Leave Request ID from summary
                employee_id: Employee ID of employee with PTO request
                employee_name: Employee Name of employee with PTO request


            Returns:
                List[PTORequestDetail]
            """
            params = {
                'leave_request_id': leave_request_id,
                'employee_id': employee_id,
                'employee_name': employee_name,
                'start_date': start_date,
                'end_date': end_date
            }
            
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            
            tool_request = ToolRequest(parameters=params)
            tool_response = self.handle_request(tool_request)
            results = tool_response.get_parameter("results")

            return results

        return get_pto_request_details