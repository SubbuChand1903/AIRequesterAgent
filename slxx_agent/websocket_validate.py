import base64
import json
import asyncio

from websockets.exceptions import WebSocketException
from websockets.server import WebSocketServerProtocol
from starlette.websockets import WebSocket
import time
import os


def is_jwt(jwt_value):
    try:

        parts = jwt_value.split('.')
        if len(parts) != 3:
            return False
        
        header = base64.urlsafe_b64decode(parts[0] + '==').decode('utf-8')
        payload = base64.urlsafe_b64decode(parts[1] + '==').decode('utf-8')
        
        json.loads(header)
        json.loads(payload)
        
        return True
    except (ValueError, json.JSONDecodeError, base64.binascii.Error):
        return False

def jwt_decode(jwt_token):
    parts = jwt_token.split('.')
    payload = base64.urlsafe_b64decode(parts[1] + '==').decode('utf-8')
    payload_dict = json.loads(payload)
    issuer = payload_dict.get("iss")
    alias = payload_dict.get("alias")
    user_id = payload_dict.get("user_id")
    expiry_date = payload_dict.get("exp")
    role = payload_dict.get("role")
    return issuer, alias, user_id, expiry_date, role


async def validate_jwt(websocket: WebSocket, alias, user_id, issuer, expiry_date):
    if not issuer or issuer != 'slxx':
        error = 'Error: Unauthenticated request.'
        return error, False
    if not alias:
        error = 'Error: Unauthenticated request without whitelisted alias.'
        return error, False
    if not user_id:
        error = 'Error: Unauthenticated request without user id'
        return error, False
    if expiry_date < int(time.time()):
        error = 'Error: Unauthenticated. Expired token.'
        return error, False
    return 'successfully authenticated', True

