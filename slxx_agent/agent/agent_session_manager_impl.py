

# session state is ephemeral and lasts only to process a single message
# for agents using multiple steps to process a message, it may be handy
# to manage this ephemeral state across the steps until processing is complete


class AgentSessionManager:
    def __init__(self):
        pass
