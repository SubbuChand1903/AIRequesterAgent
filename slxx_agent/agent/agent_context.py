
class AgentContext:
    def __init__(self, *,
                 alias: str = None,
                 session_id: str = None,
                 account_id: str = None,
                 login_id: str = None,
                 username: str = None,
                 org_level_id: int = None,
                 orgleveltype: int = None,
                 context_data: int = None):
        self.alias = alias
        self.session_id = session_id
        self.account_id = account_id
        self.login_id = login_id
        self.username = username
        self.org_level_id = org_level_id
        self.orgleveltype = orgleveltype
        self.context_data = context_data





