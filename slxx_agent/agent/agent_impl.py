import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from ai_haley_kg_domain.model.KGChatBotMessage import KGChatBotMessage
from ai_haley_kg_domain.model.KGChatUserMessage import KGChatUserMessage
from ai_haley_kg_domain.model.KGToolRequest import KGToolRequest
from ai_haley_kg_domain.model.KGToolResult import KGToolResult
from ai_haley_kg_domain.model.KGAgent import KGAgent
from com_vitalai_aimp_domain.model.AIMPIntent import AIMPIntent
from com_vitalai_aimp_domain.model.AIMPResponseMessage import AIMPResponseMessage
from com_vitalai_aimp_domain.model.AgentMessageContent import AgentMessageContent
from com_vitalai_aimp_domain.model.UserMessageContent import UserMessageContent
from com_vitalai_haleyai_question_domain.model.HaleyContainer import HaleyContainer
from com_vitalai_haleyai_question_domain.model.KGPropertyMap import KGPropertyMap
from kgraphplanner.agent.kg_planning_agent import KGPlanningAgent
from kgraphplanner.checkpointer.memory_checkpointer import MemoryCheckpointer
from kgraphplanner.tool_manager.tool_manager import ToolManager
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from slxx_agent.agent.agent_context import AgentContext
from slxx_agent.config.local_config import LocalConfig
from slxx_agent.manager.slxx_manager import slxxManager
from slxx_agent.tools.get_shift_requests import GetShiftRequests
from slxx_agent.tools.search_employees_tool import SearchEmployeesTool
from slxx_agent.tools.approve_deny_shift_request import ApproveDenyShiftRequest
from slxx_agent.tools.get_pto_requests import GetPTORequests
from slxx_agent.tools.approve_deny_pto_request import ApproveDenyPTORequest
from slxx_agent.tools.get_pto_request_detail import GetPTORequestDetail
from starlette.websockets import WebSocket
from vital_agent_container.handler.aimp_message_handler_inf import AIMPMessageHandlerInf
from vital_agent_kg_utils.vitalsignsutils.vitalsignsutils import VitalSignsUtils
from vital_ai_vitalsigns.utils.uri_generator import URIGenerator
from vital_ai_vitalsigns.vitalsigns import VitalSigns
import os
import opik
from opik.integrations.langchain import OpikTracer

def print_stream(stream, messages_out: list = []):
    for s in stream:
        message = s["messages"][-1]
        messages_out.append(message)
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()


def get_timestamp() -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return timestamp


class LoggingHandler(BaseCallbackHandler):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def on_llm_start(self, serialized: dict, prompts: list, **kwargs):
        self.logger.info(f"LLM Request: {prompts}")

    def on_llm_end(self, response, **kwargs):
        self.logger.info(f"LLM Response: {response.generations}")


class AgentImpl:
    def __init__(self):
        pass

    async def handle_error_message(self, websocket: WebSocket, started_event: asyncio.Event, auth_message):
        logging_handler = LoggingHandler()
        logger = logging.getLogger(__name__)

        vs = VitalSigns()

        response_msg = AIMPResponseMessage()
        response_msg.URI = URIGenerator.generate_uri()
        response_msg.aIMPIntentType = "http://vital.ai/ontology/vital-aimp#AIMPIntentType_CHAT"

        agent_msg_content = AgentMessageContent()
        agent_msg_content.URI = URIGenerator.generate_uri()
        agent_msg_content.text = auth_message

        message = [response_msg, agent_msg_content]

        message_json = vs.to_json(message)

        await websocket.send_text(message_json)
        logger.info(f"Sent Message: {message_json}")
        started_event.set()
        logger.info("Completed Event.")

    async def handle_chat_message(
        self,
        manager: slxxManager,
        websocket: WebSocket,
        started_event: asyncio.Event,
        agent_context: AgentContext,
        message_list
    ):
        logger = logging.getLogger(__name__)
        vs = VitalSigns()
        message_text = ""

        # load key and endpoint from slxsettings in database using JWT
        loop = asyncio.get_running_loop()
        slxx_api = manager.api
        
        # Fetch all app settings in one call (this runs in a thread pool executor)
        settings_dict = await loop.run_in_executor(None, slxx_api.get_all_app_settings)
        
        # Look for the required keys
        azure_key = settings_dict.get("AzureOpenAIKey")
        azure_endpoint = settings_dict.get("AzureOpenAIBaseEndpoint")
        azure_deployment = settings_dict.get("AzureOpenAIDeployment")
        azure_api_version = settings_dict.get("AzureOpenAIApiVersion")
        opik_request_handler_project = settings_dict.get("OpikRequestHandlerProject")
        
        if not azure_key or not azure_endpoint:
            error_message = "You have not set your OpenAI key and/or endpoint."
            await self.handle_error_message(websocket, started_event, error_message)
            return

        for go in message_list:
            if isinstance(go, UserMessageContent):
                user_text = go.text
                message_text = str(user_text)
            if isinstance(go, AgentMessageContent):
                agent_context.context_data = json.loads(str(go.text))
                if agent_context.context_data:
                    if len(agent_context.context_data) > 3:
                        agent_context.context_data = agent_context.context_data[-3:]

        logger.info(f"Message Text: {message_text}")

        container = VitalSignsUtils.get_object_type(
            message_list,
            "http://vital.ai/ontology/haley-ai-question#HaleyContainer"
        )

        history_list = []

        if container and container._properties['http://vital.ai/ontology/haley-ai-question#hasSerializedContainer'].value != '':
        # if container:
            container_list = VitalSignsUtils.unpack_container(container)
            VitalSignsUtils.log_object_list("Container", container_list)

            # for now, add tool requests/responses from previous history as raw JSON
            # later, do so in a more clean way
            history_count = []
            message_count = 0
            temp_conversation = []
            for c in container_list:
                if isinstance(c, KGAgent):
                    agent_called_before = str(c.kGAgentName)
                if isinstance(c, KGChatUserMessage):
                    text = str(c.kGChatMessageText)
                    temp_conversation.append(("human", text))
                    message_count += 1
                if isinstance(c, KGChatBotMessage):
                    text = str(c.kGChatMessageText)
                    temp_conversation.append(("ai", text))
                    history_list.extend(temp_conversation)
                    message_count += 1
                    history_count.append(message_count)
                    message_count = 0
                    temp_conversation = []

        logging_handler = LoggingHandler()

        llm = AzureChatOpenAI(
            azure_deployment=azure_deployment, 
            api_version=azure_api_version,
            callbacks=[logging_handler],
            seed = 42,
            temperature=0,
            top_p=0.1,
            presence_penalty=0,
            frequency_penalty=0,
            openai_api_key=azure_key,
            azure_endpoint=azure_endpoint
        )

        get_shift_requests_tool = GetShiftRequests({}, manager, agent_context)
        search_employee_tool = SearchEmployeesTool({}, manager, agent_context)
        approve_deny_shift_request_tool = ApproveDenyShiftRequest({}, manager, agent_context)
        get_pto_request_tool = GetPTORequests({}, manager, agent_context)
        approve_deny_pto_request_tool = ApproveDenyPTORequest({}, manager, agent_context)
        get_pto_request_details_tool = GetPTORequestDetail({}, manager, agent_context)

        tool_config = {}
        tool_manager = ToolManager(tool_config)

        tool_manager.add_tool(get_shift_requests_tool)
        tool_manager.add_tool(search_employee_tool)
        tool_manager.add_tool(approve_deny_shift_request_tool)
        tool_manager.add_tool(get_pto_request_tool)
        tool_manager.add_tool(approve_deny_pto_request_tool)
        tool_manager.add_tool(get_pto_request_details_tool)

        # getting tools to use in agent into a function list
        get_shift_requests_tool_name = GetShiftRequests.get_tool_cls_name()
        search_employee_tool_name = SearchEmployeesTool.get_tool_cls_name()
        approve_deny_shift_request_tool_name = ApproveDenyShiftRequest.get_tool_cls_name()
        get_pto_request_tool_name = GetPTORequests.get_tool_cls_name()
        approve_deny_pto_request_tool_name = ApproveDenyPTORequest.get_tool_cls_name()
        get_pto_request_details_tool_name = GetPTORequestDetail.get_tool_cls_name()

        # function list
        tool_list = [
            tool_manager.get_tool(get_shift_requests_tool_name).get_tool_function(),
            tool_manager.get_tool(search_employee_tool_name).get_tool_function(),
            tool_manager.get_tool(approve_deny_shift_request_tool_name).get_tool_function(),
            tool_manager.get_tool(get_pto_request_tool_name).get_tool_function(),
            tool_manager.get_tool(approve_deny_pto_request_tool_name).get_tool_function(),
            tool_manager.get_tool(get_pto_request_details_tool_name).get_tool_function(),
        ]

        # today = datetime.today()
        today = datetime.now(ZoneInfo('America/New_York'))

        # Find the immediate Sunday before or equal to today's date
        sunday_before = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today

        # Find the following Saturday after the Sunday
        saturday_after = sunday_before + timedelta(days=6)

        # Format the dates as 'MM-DD-YYYY'
        today_str = today.strftime('%m-%d-%Y')
        sunday_before_str = sunday_before.strftime('%m-%d-%Y')
        saturday_after_str = saturday_after.strftime('%m-%d-%Y')
        agent = KGPlanningAgent(llm, tools=tool_list)
        graph = agent.compile()

        # --- ReAct Prompt Template ---
        system_prompt = f"""

        ## Agent Persona & Core Mission

        * **Role**: You are the "Request Handler Agent," an AI assisting healthcare facilities with staffing requests and leave requests for healthcare facilities.
        * **Objective**: Accurately interpret user queries, call appropriate tools to fetch, approve or deny requests by employees in healthcare sector, and return well-formatted responses.
        * **Constraint**: You can only approve or deny *present or future* open shift requests. Past-dated requests are not permitted.

        ---

        ## Operational Context & Data

        * **Current Date & Time**:
            * Today: {today_str}
            * Current Shift Week: {sunday_before_str} to {saturday_after_str}
            * *Note*: Always calculate dates relative to today.
        * **User's Organizational Scope**: Your actions and information retrieval are limited to the 'Department' Level, as the user is logged in at {agent_context.orgleveltype}.
        * **Domain Expertise**: You must understand healthcare administration terminology and operations.

        ---

        ## Date Interpretation Guidelines

        When interpreting dates, use these rules. If a date and day conflict, ask the user to clarify.

        * "Monday" (or any day name): Refers to that day *within the current shift week*.
        * "Last Monday" / "Previous Monday": Refers to that day *in the week prior* to the current shift week.
        * "Next Monday": Refers to that day *in the week following* the current shift week.
        * "This week": Refers to the *current shift week*.
        * "Next week": Refers to the week *after* the current shift week.
        * "Last week": Refers to the week *before* the current shift week.

        ---

        ## Action & Tool Usage Instructions

        ### General Guidelines

        * **Strict Process**: You **MUST** think step-by-step and **STRICTLY** follow the ReAct pattern: **Thought**, **Action**, **Observation**. You **MUST** repeat this cycle until you have a final answer or have completed the user's request. **DO NOT** deviate from this structure.
        * **Tool Parameters - Date Format**: **IMPORTANT**: Always use the date format **YYYY-MM-DD** for all tool calls. Only format dates as **MM-DD-YYYY** when presenting information directly to the user in your final response.
        * **Accuracy First**: You **MUST NOT** invent, assume, or guess values. You **MUST** use tools to get accurate and verified data.
        * **Default Date**: If a user doesn't specify a date for a request, use **today's date** by default for tool calls.
        * **Tool Verification**: You **MUST** always call the appropriate tool to perform a task. **NEVER** state something is completed or provide information without tool verification, even if similar information seems present in previous conversation history.

        ### Using Previous Context & History

        * **Context Data**: You have access to the **3 most recent tool call responses** as JSON in `agent_context.context_data`. Use this data as arguments to tools for follow-up conversations if the user refers to an index, row, or name from this data.
        * **Conversation History**: You have access to the **5 most recent conversational turns**. Use this for context. Be aware that older history might be truncated. If data from older history is needed but not in context data, you **MUST** call the relevant tools again to retrieve it.
        * **HTML History**: Ignore HTML formatting in conversation history; extract relevant IDs/data from the structured `context_data`.

        ### Specific Tool Instructions

        * **get_shift_requests**: This tool gets requests for one date. To get data for a whole week or multiple days, you **MUST** call this tool multiple times with different dates.
        * **PTO Approvals/Denials**: When approving or denying any PTO or leave request, you **MUST** always ask if the user wants to add a comment.
        * **Output Full Data**: When presenting PTO request data, you **MUST** always provide the complete data from the tool; do not truncate any information.

        ---

        ## PTO Request Scenarios (Examples)

        This section shows how to handle common PTO request flows. You **MUST** follow these examples closely, adapting them to the specific user input and tool outputs.

        **Scenario 1: Detailed PTO Inquiry & Action**
        1.  **User**: 'Do I have any time off requests for tomorrow?' or 'Do I have any time off requests?'
            * **Thought**: The user wants to see PTO requests. I need to call the `get_pto_requests` tool. Since no date is specified, I will use today's date to get requests for "tomorrow" by calculating tomorrow's date in YYYY-MM-DD format.
            * **Action**: `get_pto_requests({{"date": "YYYY-MM-DD_tomorrow"}})` (e.g., `get_pto_requests({{"date": "2025-05-31"}})` if today is 2025-05-30)
            * **Observation**: [Tool output, e.g., list of PTO requests with IDs]
            * **Thought**: I have successfully retrieved the high-level PTO requests. I need to present them to the user in the specified table format and then prompt for further action.
            * **AI Response Format**: Display a high-level summary table (Employee, Date Range, Reason, Remaining Balance) using MM-DD-YYYY for dates, then ask if they need details or want to approve/deny any PTO request.
                ```
                Yes, here are the requests for tomorrow:
                | Employee | Date Range (Count of Shifts) | Reason | Remaining Balance |
                | John Smith | 05-20-2025 - 05-30-2025 (12) | PTO | 10 |
                | Susie Jones | 06-04-2025 (1) | Sick | -20 |
                Let me know which PTO request do you need details for or if you want to approve/deny any PTO request?
                ```
        2.  **User**: 'Yes Show the details of 1st PTO'
            * **Thought**: The user wants details for a specific PTO request. I will extract the `request_id` for the 1st PTO from the most recent tool output (from the Context Data) and use the `get_pto_request_details` tool.
            * **Action**: `get_pto_request_details({{"request_id": "ID_from_previous_observation"}})`
            * **Observation**: [Tool output, e.g., detailed PTO request]
            * **Thought**: I have successfully retrieved the detailed PTO request. I need to display this information to the user in the specified format and then ask for approval/denial confirmation.
            * **AI Response Format**: Display a detailed table (Employee, Date Requested, Shift, Remaining Balance) using MM-DD-YYYY for dates, then ask for approval/denial confirmation.
                ```
                | Employee | Date Requested | Shift | Remaining Balance |
                John Smith  05-20-2025   6a - 3p 3
                John Smith  05-21-2025   6a - 3p 6
                John Smith  05-22-2025   12a - 10p   10
                Do you want to approve/deny this PTO request?
                ```
        3.  **User**: 'Yes Approve it'
            * **Thought**: The user wants to approve the last requested PTO. I will use the `request_id` from the context data and call the `approve_deny_pto_request` tool with the action "approve". After that, I must ask about adding a comment.
            * **Action**: `approve_deny_pto_request({{"request_id": "ID_from_context", "action": "approve"}})`
            * **Observation**: [Tool output, e.g., confirmation of approval]
            * **Thought**: The PTO request has been successfully approved. I need to confirm this with the user and then ask if they wish to add a comment.
            * **AI Response**: "PTO request approved. Do you want to add a comment?"

        **Scenario 2: Direct PTO Detail Inquiry**
        1.  **User**: 'Does John Smith have any time off requests?'
            * **Thought**: The user wants to see all PTO requests for a specific employee. I will first call `get_pto_requests` for "John Smith" to get a list of high-level requests. Then, for each request returned, I will call `get_pto_request_details` to get its full details. Finally, I will display all collected details.
            * **Action**: `get_pto_requests({{"employee_name": "John Smith"}})`
            * **Observation**: [Tool output, e.g., list of PTO requests for John Smith with IDs]
            * **Thought**: I have retrieved the high-level PTO requests for John Smith. Now, I need to get the full details for each of these requests by calling `get_pto_request_details` for each `request_id` from the previous observation.
            * **Action**: `get_pto_request_details({{"request_id": "ID_1_from_previous_observation"}})`
            * **Observation**: [Tool output for ID_1]
            * **Action**: `get_pto_request_details({{"request_id": "ID_2_from_previous_observation"}})`
            * **Observation**: [Tool output for ID_2]
            * **Thought**: I have retrieved all necessary details for John Smith's PTO requests. I will now present all the details in the specified tabular format.
            * **AI Response**: [Formatted table with all PTO details for John Smith using MM-DD-YYYY dates]

        ---

        ## ReAct Format Reminder

        You **MUST** always follow this strict format for your internal reasoning and actions. **DO NOT** deviate from this structure.

        **Thought**: Your reasoning process. What do you need to do? What tool to call? Why? What information do you need to extract from previous observations or context?
        **Action**: The exact tool call, e.g., `tool_name({{"param1": "value1", "param2": "value2"}})`
        **Observation**: The raw result returned by the tool.
        ... (This Thought/Action/Observation cycle can repeat multiple times if needed)
        **Thought**: I now know the final answer or have completed the user's request based on all observations. I will formulate my final response to the user.
        **Final Answer**: [Your response to the user, formatted as specified in the "AI Response Format" sections above]

        ---

        ## Final Output Verification

        Before providing your **Final Answer**:

        1.  **Verify completion**: Confirm you've addressed all parts of the user's query and strictly followed all instructions.
        2.  **Verify tools**: Confirm you've used the correct tools with proper parameters (using **YYYY-MM-DD** for tool call dates).
        3.  **Verify format**: Ensure your final response adheres to all specified formatting requirements (using **MM-DD-YYYY** for display dates).
        4.  **Conciseness**: Remove any unnecessary text to keep the response direct and concise.

        """
                # --- End ReAct Prompt Template ---


        context_data_prompt = ""

        if len(agent_context.context_data) == 1:
            context_data_prompt = f"""
            * You have access to prior fetched request data as follows (most recent):
                ```json
                {json.dumps(agent_context.context_data[-1], indent=4)}
                ```
            * If user is referring to an index or row or name from this data, use details from this context for tools.
            """
        elif len(agent_context.context_data) == 2:
            context_data_prompt = f"""
            * You have access to prior fetched request data as follows:
                * Second last data fetched:
                    ```json
                    {json.dumps(agent_context.context_data[-2], indent=4)}
                    ```
                * Most recent data fetched:
                    ```json
                    {json.dumps(agent_context.context_data[-1], indent=4)}
                    ```
            * If user is referring to an index or row or name from this data, use details from this context for tools.
            """
        elif len(agent_context.context_data) == 3:
            context_data_prompt = f"""
            * You have access to prior fetched request data as follows (oldest to most recent):
                * Oldest data fetched:
                    ```json
                    {json.dumps(agent_context.context_data[-3], indent=4)}
                    ```
                * Second last data fetched:
                    ```json
                    {json.dumps(agent_context.context_data[-2], indent=4)}
                    ```
                * Most recent data fetched:
                    ```json
                    {json.dumps(agent_context.context_data[-1], indent=4)}
                    ```
            * If user is referring to an index or row or name from this data, use details from this context for tools.
            """
        else:
            context_data_prompt = ""
        
        dynamic_system_prompt = system_prompt + context_data_prompt
        chat_message_list = [("system", dynamic_system_prompt)]

        for h in history_list:
            chat_message_list.append(h)

        chat_message_list.append(("human", message_text))

        logger.info(chat_message_list)

        inputs = {"messages": chat_message_list}

        # Added Opik tracing
        opik.configure(use_local=False)
        opik_tracer = OpikTracer(graph=graph.get_graph(xray=True),
                                tags=["Alias: "+ agent_context.alias, 
                                      "Username: " + agent_context.username, 
                                      "Org Level Id: " + str(agent_context.org_level_id), 
                                      "Org Level: " + agent_context.orgleveltype],
                                project_name=opik_request_handler_project)

        messages_out = []
        print_stream(graph.stream(inputs, config={"callbacks":[opik_tracer]}, stream_mode="values"), messages_out)
        history_out_list = []

        if history_list:
            if len(history_count) > 2:
                history_list = history_list[history_count[0]:]

            for role, message in history_list:
                if role == 'assistant':
                    agent_name_history = KGAgent()
                    agent_name_history.URI = URIGenerator.generate_uri()
                    agent_name_history.kGAgentName = message
                    history_out_list.append(agent_name_history)
                if role == 'human':
                    user_message = KGChatUserMessage()
                    user_message.URI = URIGenerator.generate_uri()
                    user_message.kGChatMessageText = message
                    history_out_list.append(user_message)
                if role == 'ai':
                    if message.startswith('** AI Prior Tool Request: '):
                        tool_request = KGToolRequest()
                        tool_request.URI = URIGenerator.generate_uri()
                        tool_request.kGToolRequestType = "urn:langgraph_openai_tool_request"
                        tool_request_string = message.split('** AI Prior Tool Request: ')[-1]
                        tool_request.kGJSON = tool_request_string
                        history_out_list.append(tool_request)
                    elif message.startswith('** AI Prior Tool Result: '):
                        tool_result = KGToolResult()
                        tool_result.URI = URIGenerator.generate_uri()
                        tool_result.kGToolResultType = "urn:langgraph_openai_tool_result"
                        tool_result_json = message.split('** AI Prior Tool Result: ')[-1]
                        tool_result.kGJSON = tool_result_json
                        history_out_list.append(tool_result)
                    else:
                        bot_message = KGChatBotMessage()
                        bot_message.URI = URIGenerator.generate_uri()
                        bot_message.kGChatMessageText = message
                        history_out_list.append(bot_message)

        for m in messages_out:
            t = type(m)
            logger.info(f"History ({t}): {m}")
            if isinstance(m, HumanMessage):
                agent_called = KGAgent()
                agent_called.URI = URIGenerator.generate_uri()
                agent_called.kGAgentName = 'AI_Agent_RequestHandler'
                history_out_list.append(agent_called)
                user_message = KGChatUserMessage()
                user_message.URI = URIGenerator.generate_uri()
                user_message.kGChatMessageText = m.content
                history_out_list.append(user_message)
            if isinstance(m, AIMessage):
                if m.tool_calls:
                    tool_request = KGToolRequest()
                    tool_request.URI = URIGenerator.generate_uri()
                    tool_request.kGToolRequestType = "urn:langgraph_openai_tool_request"
                    tool_request.kGJSON = m.tool_calls
                    history_out_list.append(tool_request)
                    logger.info(tool_request.to_json(pretty_print=False))
                else:
                    bot_message = KGChatBotMessage()
                    bot_message.URI = URIGenerator.generate_uri()
                    bot_message.kGChatMessageText = m.content
                    history_out_list.append(bot_message)
            if isinstance(m, ToolMessage):
                tool_result = KGToolResult()
                tool_result.URI = URIGenerator.generate_uri()
                tool_result.kGToolResultType = "urn:langgraph_openai_tool_result"
                tool_result.kGJSON = m.content
                history_out_list.append(tool_result)
                logger.info(tool_result.to_json(pretty_print=False))

        container = HaleyContainer()
        container.URI = URIGenerator.generate_uri()

        if len(history_out_list) > 0:
            logger.info(f"Outgoing container size is: {len(history_out_list)}")
            container = VitalSignsUtils.pack_container(container, history_out_list)

        last_message = messages_out[-1]
        response_text = last_message.content
        logger.info(f"Response Text: {response_text}")

        response_msg = AIMPResponseMessage()
        response_msg.URI = URIGenerator.generate_uri()
        response_msg.aIMPIntentType = "http://vital.ai/ontology/vital-aimp#AIMPIntentType_CHAT"

        agent_msg_content = AgentMessageContent()
        agent_msg_content.URI = URIGenerator.generate_uri()
        agent_msg_content.text = response_text

        context_data = AgentMessageContent()
        context_data.URI = URIGenerator.generate_uri()
        context_data.text = json.dumps(agent_context.context_data, indent=4)

        message = [response_msg, agent_msg_content, container, context_data]
        message_json = vs.to_json(message)

        await websocket.send_text(message_json)
        logger.info(f"Sent Message: {message_json}")

        started_event.set()
        logger.info("Completed Event.")
