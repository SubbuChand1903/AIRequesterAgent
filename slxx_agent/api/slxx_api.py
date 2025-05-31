import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from slxx_agent.config.local_config import LocalConfig
from slxx_agent.websocket_validate import jwt_decode

class slxxAPI:
    def __init__(self, local_config: LocalConfig, jwt):
        self.local_config = local_config
        self.jwt = jwt
        _, self.alias, self.user_id, self.expiry, self.role = jwt_decode(self.jwt)

        self.auth_headers = {
            "X-Slx-Alias": self.alias,
            "x-slx-ms-userLogin": self.user_id,
            "Content-Type": "application/json"
        }
        self.headers = {
            "X-Slx-Alias": self.alias,
            "x-slx-ms-userLogin": self.user_id,
            "Content-Type": "application/json"
        }

        # We'll store the token if needed
        self.token = None

        # Create a session
        self.session = requests.Session()

        # Define retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def authenticate(self):
        """
        Authenticates by setting the bearer token if a JWT is supplied.
        """
        if self.jwt:
            self.token = self.jwt
            self.headers['Authorization'] = f"Bearer {self.token}"
        else:
            raise Exception("Failed to authenticate.")
        
    def get_all_app_settings(self) -> dict:
        """
        Get all app settings
        """
        
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/app/settings"
        response = self.session.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        settings = response.json()
        
        return {
            item["key"]: item["value"]
            for item in settings.get("data", [])
            if "key" in item and "value" in item
        }
    
    def get_employee_short_info(self, *, employee_id):
        """
        Get a single employee's short info using the new endpoint:
        GET /api/v1/employees/{employeeId}/shortInfo
        """
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/employees/{employee_id}/shortInfo"
        response = self.session.get(url, headers=self.headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    
    def get_all_employee_list(self, *, active_only=True):
        """
        Retrieve a list of employees for corporate level
        """
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/lookup/employees"
        params = {
            "orgLevelId": 1,
            "isActive": str(active_only).lower()
        }
        response = self.session.get(url, headers=self.headers, params=params, timeout=10)
        return response.json()
    
    def get_shift_requests(self, date_on, org_level_id):
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/schedule/{date_on}/orglevel/{org_level_id}/openShift"
        response = self.session.post(url, headers=self.headers, timeout=10)
        return response.json()
    
    def approve_shift_request(self, date_on, employee_id, shift_id, unit_id, position_id, message_id):
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/messages/{message_id}/approveShift"
        payload = {
            "DateOn": date_on,
            "EmployeeId": employee_id,
            "ShiftId": shift_id,
            "UnitId": unit_id,
            "PositionId": position_id
        }
        response = self.session.post(url, headers=self.headers, json=payload, timeout=10)
        return response
    
    def deny_shift_request(self, date_on, employee_id, shift_id, unit_id, position_id, message_id):
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/messages/{message_id}/denyShift"
        payload = {
            "DateOn": date_on,
            "EmployeeId": employee_id,
            "ShiftId": shift_id,
            "UnitId": unit_id,
            "PositionId": position_id
        }
        response = self.session.post(url, headers=self.headers, json=payload, timeout=10)
        return response
    
    def get_pto_requests(self, org_level_id, start_date, end_date):
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/schedule/orglevel/{org_level_id}/leaveRequests"
        params = {
            "startDate": start_date,
            "endDate": end_date
        }
        response = self.session.get(url, headers=self.headers, params=params, timeout=10)
        return response.json()
    
    def get_pto_request_detail(self, org_level_id, leave_request_id):
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/schedule/orglevel/{org_level_id}/leaveRequests/{leave_request_id}/details"
        response = self.session.get(url, headers=self.headers, timeout=10)
        return response.json()
    
    def approve_pto_request(self, org_level_id, leave_request_id, comment):
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/schedule/orglevel/{org_level_id}/leaveRequests/{leave_request_id}/approve"
        if not comment:
            payload = {}
        else:
            payload = {"comment": comment}
        response = self.session.post(url, headers=self.headers, json=payload, timeout=10)
        return response
    
    def deny_pto_request(self, org_level_id, leave_request_id, comment):
        self.authenticate()
        base_url = self.local_config.base_endpoint
        url = f"{base_url}/api/v1/schedule/orglevel/{org_level_id}/leaveRequests/{leave_request_id}/deny"
        if not comment:
            payload = {}
        else:
            payload = {"comment": comment}
        response = self.session.post(url, headers=self.headers, json=payload, timeout=10)
        return response