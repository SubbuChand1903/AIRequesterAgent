import os
import requests
import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
from slxx_agent.config.local_config import LocalConfig


def main():
    print('Test slxx API Connection')

    current_file_directory = os.path.dirname(os.path.abspath(__file__))

    app_dir = os.path.dirname(current_file_directory)

    local_config = LocalConfig(app_dir)
    base_url = local_config.base_endpoint
    url = f"{base_url}/api/v1/jwt/auth"

    username = "system"
    password = "Ph!los0ph!c@l"
    alias = "bhsrel"

    headers = {
        "X-Slx-Alias": f"{alias}",
        "Content-Type": "application/json"
    }

    payload = {
        "username": f"{username}",
        "password": f"{password}"
    }

    response = requests.Session().post(url, headers=headers, json=payload)

    if response.status_code == 200:
        print("Authentication successful.")
        print("Response JSON:", response.json())
    else:
        print("Failed to authenticate.")
        print("Status code:", response.status_code)
        print("Response:", response.text)


if __name__ == "__main__":
    main()
