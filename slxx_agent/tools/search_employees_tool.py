import logging
from typing import Callable, TypedDict, List
from kgraphplanner.tool_manager.abstract_tool import AbstractTool
from kgraphplanner.tool_manager.tool_request import ToolRequest
from kgraphplanner.tool_manager.tool_response import ToolResponse
from langchain_core.tools import tool

from slxx_agent.agent.agent_context import AgentContext
from slxx_agent.manager.slxx_manager import slxxManager


class EmployeeSearchRecord(TypedDict):
    """
    EmployeeSearchRecord is a dictionary that represents an employee from an employee list that matches a search

    Attributes:
        employee_name (str): Name of Employee
        employee_identifier (str): Identifier of Employee
        search_match_score (float): Search match score
    """

    employee_name: str  # Name of Employee
    employee_identifier: str  # Identifier of Employee
    search_match_score: float  # Search match score


class SearchEmployeesTool(AbstractTool):
    def __init__(self, config, manager: slxxManager, agent_context: AgentContext):
        super().__init__(config)
        self.manager = manager
        self.agent_context = agent_context

    def handle_request(self, tool_request: ToolRequest) -> ToolResponse:

        logger = logging.getLogger(__name__)

        logger.info(f"SearchEmployeesTool Parameters: {tool_request.parameters}")

        employee_search_string = tool_request.get_parameter('employee_search_string')

        logger.info(f"employee_search_string: {employee_search_string}")

        tool_response = ToolResponse()


        top_matches = self.manager.find_employees(employee_search_string)

        if top_matches:
            employee_search_list = []

            for (distance, closest_id, closest_word) in top_matches:

                employee_search_record = EmployeeSearchRecord()
                employee_search_record['employee_name'] = closest_word  # "John Smith"
                employee_search_record['employee_identifier'] = closest_id  # "123-456-789"
                employee_search_record['search_match_score'] = distance  # 0.8

                employee_search_list.append(employee_search_record)
            search_employee_data = {
                "type": "Search Employees",
                "data": employee_search_list
            }
            self.agent_context.context_data.append(search_employee_data)
            if len(employee_search_list) == 0:
                result = f"{employee_search_string} was not found in the current organization level, please search another organizational level or revise your search."
                tool_response.add_parameter("results", result)
            else:
                tool_response.add_parameter("results", employee_search_list)

            return tool_response

        # None found
        result = f"{employee_search_string} was not found in the current organization level, please search another organizational level or revise your search."
        tool_response.add_parameter("results", result)
        return tool_response

    def get_sample_text(self) -> str:
        pass

    def get_tool_function(self) -> Callable:

        @tool
        def search_employees(employee_search_string: str):
            """
            Use this to search employees using the name of a person and get employee identifier for an employee
            Partial or close matches will be returned.
            Returns a list of matching employees or an empty list if no matching employees are found.

            :param employee_search_string: Employee Name Search String
            :type employee_search_string: str
            :return: List of matching employees or an empty list if no matching employees are found.
            """

            logger = logging.getLogger(__name__)

            logger.info(f"tool search_employees: employee_search_string: {employee_search_string}")

            params = {'employee_search_string': employee_search_string}

            tool_request = ToolRequest(parameters=params)

            tool_response = self.handle_request(tool_request)

            employee_search_list = tool_response.get_parameter("results")
            return employee_search_list

        return search_employees
