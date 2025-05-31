import asyncio
import json
import logging
import httpx
from com_vitalai_aimp_domain.model.AIMPIntent import AIMPIntent
from com_vitalai_aimp_domain.model.AIMPMessage import AIMPMessage
from com_vitalai_aimp_domain.model.AIMPResponseMessage import AIMPResponseMessage
from com_vitalai_aimp_domain.model.AgentMessageContent import AgentMessageContent
from com_vitalai_aimp_domain.model.UserMessageContent import UserMessageContent
from starlette.websockets import WebSocket
from vital_agent_container.handler.aimp_message_handler_inf import AIMPMessageHandlerInf
from vital_ai_vitalsigns.utils.uri_generator import URIGenerator
from vital_ai_vitalsigns.vitalsigns import VitalSigns
from slxx_agent.agent.agent_context import AgentContext
from slxx_agent.agent.agent_impl import AgentImpl
from slxx_agent.agent.agent_state_impl import AgentStateImpl
from slxx_agent.api.slxx_api import slxxAPI
from slxx_agent.config.local_config import LocalConfig
from slxx_agent.manager.slxx_manager import slxxManager

from slxx_agent.websocket_validate import validate_jwt, is_jwt, jwt_decode


class slxxMessageHandler(AIMPMessageHandlerInf):

    def __init__(self, agent: AgentImpl, app_home: str):
        self.agent = agent
        self.app_home = app_home

        self.local_config = LocalConfig(app_home)
        self.api = None
        self.manager = None

    async def process_message(self, config, client: httpx.AsyncClient, websocket: WebSocket, data: str,
                              started_event: asyncio.Event):

        logger = logging.getLogger(__name__)

        try:
            logger.info(f"Handler Received Message: {data}")

            vs = VitalSigns()

            message_list = []

            json_list = json.loads(data)

            try:
                for m in json_list:
                    logger.info(f"Object: {m}")
                    m_string = json.dumps(m)
                    go = vs.from_json(m_string)
                    message_list.append(go)
            except Exception as e:
                logger.error(e)

            if len(message_list) > 0:

                aimp_message: AIMPMessage = message_list[0]

                if not aimp_message.jwtEncodedString:
                    await websocket.close(code=1011, reason=json.dumps({'code': 401, 'error': 'Unauthenticated.'}))
                    return
                else:
                    jwt_token = str(aimp_message.jwtEncodedString)

                    if is_jwt(jwt_token):
                        issuer, alias, user_id, expiry_date, role = jwt_decode(jwt_token)
                        auth_message, isvalid = await validate_jwt(websocket, alias, user_id, issuer, expiry_date)
                        if not isvalid:
                            await self.agent.handle_error_message(websocket, started_event, auth_message)
                            return
                    else:
                        await websocket.close(code=1011, reason=json.dumps({'code': 401, 'error': 'Unauthenticated.'}))
                        return
                
                orgleveltype = str(aimp_message.sourceUserName)
                logger.info(f"Org Level Type: {orgleveltype}")
                if orgleveltype != 'Department':
                    auth_message = "This information is available only at the following organization levels: Department. Please move to department level."
                    await self.agent.handle_error_message(websocket, started_event, auth_message)
                    return
                
                for go in message_list:
                    if isinstance(go, UserMessageContent):
                        user_text = go.text
                        message_text = str(user_text)

                self.api = slxxAPI(self.local_config, jwt_token)

                self.manager = slxxManager(self.local_config, self.api, message_text)

                # these come from message
                # account_id = "urn:account_123"
                # login_id = "urn:login_456"
                # session_id = "urn:session_789"

                session_id = str(aimp_message.sessionID)

                account_id = str(aimp_message.accountURI)
                login_id = str(aimp_message.userID)
                username = str(aimp_message.username)

                logger.info(f"Session ID: {session_id}")
                logger.info(f"Account ID: {account_id}")
                logger.info(f"Login ID: {login_id}")
                logger.info(f"Username: {username}")

                # For this example, we assume org_level_id comes from masterUserID
                org_level_id = str(aimp_message.masterUserID)
                org_level_id = int(org_level_id)

                logger.info(f"Org Level ID: {org_level_id}")

                agent_context = AgentContext(
                    alias=alias,
                    session_id=session_id,
                    account_id=account_id,
                    login_id=login_id,
                    username=username,
                    org_level_id=org_level_id,
                    orgleveltype=orgleveltype,
                    context_data=[]
                )

                agent_state = AgentStateImpl(message_list)

                if isinstance(aimp_message, AIMPIntent):

                    intent_type = str(aimp_message.aIMPIntentType)

                    if intent_type == "http://vital.ai/ontology/vital-aimp#AIMPIntentType_CHAT":
                        await self.agent.handle_chat_message(self.manager, websocket, started_event,
                                                             agent_context, message_list)
                        return

            # handle unknown type

        except asyncio.CancelledError:
            raise
