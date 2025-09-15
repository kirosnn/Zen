import os
import requests
from datetime import datetime
import locale
from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from dotenv import load_dotenv
import subprocess
import sys

try:
    from crewai_tools import CodeInterpreterTool
except Exception:
    try:
        from crewai_tools.tools.code_interpreter_tool import CodeInterpreterTool
    except Exception as _import_err:
        CodeInterpreterTool = None
        _CODE_INTERPRETER_IMPORT_ERROR = _import_err

load_dotenv()

class LocalCodeInterpreterTool(BaseTool):
    name: str = "Local Code Interpreter"
    description: str = "Execute short Python snippets locally using a subprocess (fallback when crewai-tools CodeInterpreter is unavailable)."

    def _run(self, code: str, **kwargs) -> str:
        try:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=False,
            )
            return completed.stdout
        except Exception as e:
            return f"Execution error: {e}"

def create_code_interpreter_agent():
    if CodeInterpreterTool is None:
        code_interpreter_tool = LocalCodeInterpreterTool()
    else:
        use_unsafe = os.getenv("CODE_INTERPRETER_UNSAFE", "true").lower() in ("1", "true", "yes", "on")
        code_interpreter_tool = CodeInterpreterTool(unsafe_mode=use_unsafe)
    return Agent(
        role="Code Interpreter Agent",
        goal="Execute Python code to solve problems",
        backstory="An expert Python programmer who can write and execute code to solve complex problems.",
        tools=[code_interpreter_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        memory=True
    )

def create_code_task(agent, query):
    return Task(
        description=f"Write and execute Python code to solve: {query}",
        expected_output="The result of the code execution.",
        agent=agent
    )

def run_code_interpreter(query):
    agent = create_code_interpreter_agent()
    task = create_code_task(agent, query)
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )
    
    result = crew.kickoff()
    return result
