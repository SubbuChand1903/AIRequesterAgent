import json
import requests
import asyncio
import os
import sys
import websockets
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
from slxx_agent.api.slxx_api import slxxAPI
from slxx_agent.config.local_config import LocalConfig

async def test_websocket():
    uri = "ws://localhost:7009/ws"

    jwt_token = ""
    current_file_directory = os.path.dirname(os.path.abspath(__file__))

    app_dir = os.path.dirname(current_file_directory)

    local_config = LocalConfig(app_dir)

    base_url = local_config.base_endpoint
    url = f"{base_url}/api/v1/jwt/auth"
    headers = {
        "X-Slx-Alias": "bhsrel",
        "Content-Type": "application/json"
    }
    payload = {
    "username": "system",
    "password": "Ph!los0ph!c@l"
}
    response = requests.Session().post(url, headers=headers, json=payload, timeout=10)
    jwt_token = response.json().get("data").get("response").get("token")

    test_message = json.dumps(
        [
            {
        "URI": "http://vital.ai/vital.ai/vitalsigns/b34bcaaf-2b2d-41bc-aabf-9af80a1b13de",
        "http://vital.ai/ontology/vital-aimp#hasAIMPIntentType": "http://vital.ai/ontology/vital-aimp#AIMPIntentType_CHAT",
        "http://vital.ai/ontology/vital#hasAccountURI": "urn:account_1",
        "http://vital.ai/ontology/vital-aimp#hasMasterUserID": 300039,
        "http://vital.ai/ontology/vital-aimp#hasSourceUserName": 'Department',
        "http://vital.ai/ontology/vital-core#hasUsername": 'user_1',
        "http://vital.ai/ontology/vital-core#hasSessionID": "140406814246456",
        "http://vital.ai/ontology/vital-aimp#hasAuthSessionID": "140406814246456",
        "http://vital.ai/ontology/vital-aimp#hasJwtEncodedString": jwt_token,
        "type": "http://vital.ai/ontology/vital-aimp#AIMPIntent",
        "http://vital.ai/ontology/vital-core#vitaltype": "http://vital.ai/ontology/vital-aimp#AIMPIntent",
        "types": [
          "http://vital.ai/ontology/vital-aimp#AIMPIntent"
        ]
      },
      {
        "URI": "http://vital.ai/vital.ai/vitalsigns/5a54343c-ba66-47b0-b6b7-a9b23432f53f",
        "http://vital.ai/ontology/vital-aimp#hasText": "hi",
        "type": "http://vital.ai/ontology/vital-aimp#UserMessageContent",
        "http://vital.ai/ontology/vital-core#vitaltype": "http://vital.ai/ontology/vital-aimp#UserMessageContent",
        "types": [
          "http://vital.ai/ontology/vital-aimp#UserMessageContent"
        ]
      }
        ]
    )
    try:

        print('Test slxx API: Websocket Test')
        async with websockets.connect(uri) as websocket:
            print("Connected to Websocket")
            await websocket.send(test_message)
            print(f"Sent message: {test_message}")

            response = await websocket.recv()
            print(f"Received response: {response}")
    except Exception as e:
        print(f"Websocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
