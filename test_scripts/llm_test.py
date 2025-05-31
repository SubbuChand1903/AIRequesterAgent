import json
import requests
import asyncio
import os
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
from slxx_agent.api.slxx_api import slxxAPI
from slxx_agent.config.local_config import LocalConfig


def test_azure_openai():
  jwt_token = ""
  current_file_directory = os.path.dirname(os.path.abspath(__file__))

  app_dir = os.path.dirname(current_file_directory)

  local_config = LocalConfig(app_dir)

  base_url = local_config.base_endpoint
  url = f"{base_url}/api/v1/jwt/auth"
  headers = {
      "X-Slx-Alias": "",
      "Content-Type": "application/json"
  }
  payload = {
  "username": "system",
  "password": "P!c@l"
}
  response = requests.Session().post(url, headers=headers, json=payload, timeout=10)
  jwt_token = response.json().get("data").get("response").get("token")
  api = slxxAPI(local_config, jwt_token)
  # Fetch all app settings in one call (this runs in a thread pool executor)
  settings_dict = api.get_all_app_settings()
  
  # Look for the required keys
  azure_key = settings_dict.get("AzureOpenAIKey")
  azure_endpoint = settings_dict.get("AzureOpenAIBaseEndpoint")
      
  llm = AzureChatOpenAI(
          azure_deployment="gpt-4o",
          api_version="2024-08-01-preview",
          temperature=0,
          openai_api_key=azure_key,
          azure_endpoint=azure_endpoint
      )

  test_message = "Hello! How can you help me?"

  response = llm([HumanMessage(content=test_message)])

  print(f"Response from Azure Open AI: {response}")

if __name__ == "__main__":
  test_azure_openai()
