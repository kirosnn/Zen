from tools.search import run_zen_research
from tools.code_interpreter import run_code_interpreter
from tools.computer_use import ComputerUseAgent
from tools.chat import ChatTool

def route_query(intent: str, query: str):
    if intent == "code":
        return run_code_interpreter(query)
    elif intent == "web":
        return run_zen_research(query)
    elif intent == "computer":
        agent = ComputerUseAgent()
        return agent.run(query)
    elif intent == "chat":
        tool = ChatTool()
        return tool._run(message=query)
    else:
        tool = ChatTool()
        return tool._run(message=query)
