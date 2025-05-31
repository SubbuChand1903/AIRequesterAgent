import logging
import time
import json
import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
import datetime

from slxx_agent.api.slxx_api import slxxAPI
from datasketch import MinHash, MinHashLSH
from rapidfuzz import fuzz
from slxx_agent.config.local_config import LocalConfig

class slxxManager:
    def __init__(self, local_config: LocalConfig, api: slxxAPI, user_prompt):
        self.api = api
        self.local_config = local_config
        self.user_prompt = user_prompt

        # For fuzzy search: a simple cache
        self.ids_to_names = None
        self.lsh_index = None
        self.employee_data_timestamp = None
        self.employee_data_ttl = timedelta(hours=1)

    # --------------------------------------------------------------------------
    # Fuzzy Employee Searching
    # --------------------------------------------------------------------------
    def find_employees(self, employee_query):
        """
        Uses a fuzzy-match index to find employees by name, or if the query
        looks like an ID (numeric), fetch that employee directly.
        """

        if employee_query.isdigit():
            single_emp = self.get_employee(employee_query)
            if not single_emp:
                return []
            candidate_name = single_emp["employee_name"]
            return [(100, employee_query, candidate_name)]

        self.ids_to_names, self.lsh_index = self.build_employee_index()

        top_matches = self.find_closest_string(employee_query, self.lsh_index, self.ids_to_names)
        return top_matches
    
    def build_employee_index(self):
        logger = logging.getLogger(__name__)
        response = self.api.get_all_employee_list()
        employees = response["data"]

        ids_to_names = {}
        for emp in employees:
            emp_id = emp.get("id")
            emp_name = emp.get("fullName")
            ids_to_names[emp_id] = emp_name

        lsh_index = MinHashLSH(threshold=0.1, num_perm=64)
        for eid, name in ids_to_names.items():
            mh = self.get_minhash(name)
            lsh_index.insert(str(eid), mh)

        logger.info(f"ids_to_names: {ids_to_names}")
        return ids_to_names, lsh_index

    def get_minhash(self, text):
        m = MinHash(num_perm=64)
        n = 3
        for i in range(len(text) - n + 1):
            m.update(text[i:i+n].lower().encode("utf8"))
        return m

    def find_closest_string(self, query_string, index, ids_to_names):
        logger = logging.getLogger(__name__)
        logger.info(f"Fuzzy searching for: {query_string}")
        query_hash = self.get_minhash(query_string)
        result_ids = index.query(query_hash)
        logger.info(f"result_ids: {result_ids}")
        scored = []
        for rid in result_ids:
            candidate_name = ids_to_names.get(int(rid), "")
            score = fuzz.WRatio(candidate_name, query_string)
            scored.append((score, rid, candidate_name))
        top_matches = sorted(scored, reverse=True)[:10]
        return top_matches

    def rearrange_name(self, name):
        parts = name.split(",")
        parts = [p.strip() for p in parts]
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
        return name
    
    def get_employee(self, employee_id):
        # First, try to get the basic employee info (from vector cache or API)
        logger = logging.getLogger(__name__)
        response = self.api.get_employee_short_info(employee_id=employee_id)
        logger.info(f"Employee info response: {response}")
        if not response:
            return None
        data = response.get("data")
        if not data:
            return None

        full_name = data.get("fullName")
        if not full_name:
            first_name = data.get("firstName", "")
            last_name = data.get("lastName", "")
            full_name = f"{first_name} {last_name}".strip()

        emp_map = {
            "employee_id": employee_id,
            "employee_name": full_name,
            "employee_type": data.get("type"),
            "hire_date": data.get("dateHired"),
            "employee_email": data.get("email"),
        }
        return emp_map
    
    # --------------------------------------------------------------------------
    # Open Shift Requests
    # --------------------------------------------------------------------------

    def get_shift_requests(self, date_on, org_level_id):
        """
        Get Open shift Requests for a date in that org level
        
        Args:
            date_on (str): Date in format 'YYYY-MM-DD'
            org_level_id (int): Organization level ID
        
        Returns:
            Dict: Open Shift Request Data
        """
        shift_request_response = self.api.get_shift_requests(date_on, org_level_id)
        shift_request_response_data = shift_request_response.get("data", {})
        if not shift_request_response_data:
            return {}
        
        shift_request_response_details = shift_request_response_data.get("details", [])
        if not shift_request_response_details:
            return {}
        
        shift_requests = []
        for shifts in shift_request_response_details:
            messages = shifts.get("messages", [])
            if not messages:
                continue
            shift_id = shifts.get("shift").get("id")
            shift_name = shifts.get("shift").get("name")
            shift_group_id = shifts.get("shiftGroup").get("id")
            shift_group_name = shifts.get("shiftGroup").get("name")
            position_id = shifts.get("position").get("id")
            position_name = shifts.get("position").get("name")
            unit_id = shifts.get("unit").get("id")
            unit_name = shifts.get("unit").get("name")

            for message in messages:
                shift_requests.append(
                    {
                        "metadata": {
                            "request date": date_on,
                            "shift_id":shift_id,
                            "shift_name": shift_name,
                            "shift_group_id": shift_group_id,
                            "shift_group_name": shift_group_name,
                            "position_id": position_id,
                            "position_name": position_name,
                            "unit_id": unit_id,
                            "unit_name": unit_name
                        },
                        "request messages": message
                        }
                )
        return shift_requests

    # --------------------------------------------------------------------------
    # Approve/Deny Open Shift Requests
    # --------------------------------------------------------------------------

    def approve_deny_shift_request(self, date_on, request_for, employee_id, shift_id, unit_id, position_id, message_id):
        if request_for == 'Approve':
            response = self.api.approve_shift_request(date_on=date_on, 
                                                employee_id=employee_id, 
                                                shift_id=shift_id,
                                                unit_id=unit_id, 
                                                position_id=position_id,
                                                message_id=message_id)
        else:
            response = self.api.deny_shift_request(date_on=date_on, 
                                                employee_id=employee_id, 
                                                shift_id=shift_id,
                                                unit_id=unit_id, 
                                                position_id=position_id,
                                                message_id=message_id)

        if hasattr(response, "status_code"):
            if response.status_code in [200, 204]:
                return {"status": "success", "data": response.json() if response.status_code == 200 else None}
            else:
                return {
                    "status": "error",
                    "message": response.text,
                    "status_code": response.status_code
                }
            
    # --------------------------------------------------------------------------
    # PTO Requests
    # --------------------------------------------------------------------------
    
    def get_pto_requests(self, org_level_id, start_date, end_date):
        logger = logging.getLogger(__name__)
        response = self.api.get_pto_requests(org_level_id, start_date, end_date)
        logger.info(f"PTO request API response: {response}")
        response_data = response.get("data", {})
        if not response_data:
            return []
        requests = response_data.get("requests", [])
        if not requests:
            return []
        pto_requests = []

        for request in requests:
            if request.get("status") == "Denied" or request.get("status") == "Approved":
                continue
            pto_requests.append(
                {
                    "leave_request_id": request.get("id"),
                    "employee_id": request.get("employee").get("id"),
                    "employee_name": request.get("employee").get("name"),
                    "department_id": request.get("department").get("id"),
                    "department_name": request.get("department").get("name"),
                    "position_id": request.get("position").get("id"),
                    "position_name": request.get("position").get("name"),
                    "start": request.get("start"),
                    "end": request.get("end"),
                    "reason": request.get("reason"),
                    "status": request.get("status"),
                    "accruals": request.get("accruals")
                }
            )
        return pto_requests
    
    def get_pto_request_detail(self, org_level_id, leave_request_id):
        response = self.api.get_pto_request_detail(org_level_id, leave_request_id)
        logger = logging.getLogger(__name__)
        logger.info(f"PTO request Detail API response: {response}")
        response_data = response.get("data")
        if not response_data:
            return []
        details = response_data.get("details")
        pto_details = []
        if not details:
            return []
        for pto in details:
            pto_details.append(
                {
                    "date": pto.get("date"),
                    "shift_id": pto.get("shift").get("id"),
                    "shift_name": pto.get("shift").get("name"),
                    "shift_start": pto.get("shift").get("start"),
                    "shift_end": pto.get("shift").get("end"),
                    "shift_duration": pto.get("shift").get("duration"),
                    "unit_id": pto.get("unit").get("id"),
                    "unit_name": pto.get("unit").get("name"),
                    "absence_code": pto.get("absenceReason").get("code"),
                    "absence_description": pto.get("absenceReason").get("description"),
                    "isAccruaBalanceAvailable": pto.get("isAccruaBalanceAvailable"),
                    "accrualBalance": pto.get("accrualBalance"),
                    "approvedAbsences": pto.get("approvedAbsences"),
                    "submittedAbsences": pto.get("submittedAbsences"),

                }
            )
        return pto_details
        
    
    # --------------------------------------------------------------------------
    # Approve/Deny PTO Requests
    # --------------------------------------------------------------------------
    
    def approve_deny_pto_request(self, org_level_id, leave_request_id, request_for, comment):
        if request_for == 'Approve':
            response = self.api.approve_pto_request(org_level_id=org_level_id,
                                                    leave_request_id=leave_request_id,
                                                    comment=comment)
        else:
            response = self.api.deny_pto_request(org_level_id=org_level_id,
                                                leave_request_id=leave_request_id,
                                                comment=comment)

        if hasattr(response, "status_code"):
            if response.status_code in [200, 204]:
                return {"status": "success", "data": response.json() if response.status_code == 200 else None}
            else:
                return {
                    "status": "error",
                    "message": response.text,
                    "status_code": response.status_code
                }