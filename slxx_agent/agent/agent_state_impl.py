
# agent state provided by service when calling agent
# state contained within message list
# which includes message history and other info covering
# account, login, and session

class AgentStateImpl:
    def __init__(self, message_list):
        self.message_list = message_list
