

# use to manage internal state when processing an incoming message
# this may include state from agent function calls or queries of knowledge graph

class AgentSessionImpl:
    def __init__(self, account_id, login_id, session_id):
        self.account_id = account_id
        self.login_id = login_id
        self.session_id = session_id


