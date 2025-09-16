import os
import json
import logging
from typing import Literal, Optional
from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from tools.search import run_zen_research
from tools.code_interpreter import run_code_interpreter
from tools.computer_use import ComputerUseAgent
from tools.chat import ChatTool

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Intent = Literal["web", "code", "computer", "chat"]
VALID_INTENTS = {"web", "code", "computer", "chat"}


def classify_intent(query: str) -> Intent:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("MODEL", "gpt-5-nano")

    heuristic = _heuristic_intent(query)

    if OpenAI is None or not api_key:
        logger.debug("OpenAI not available, falling back to heuristic intent")
        return heuristic

    try:
        client = OpenAI(api_key=api_key)
        system_msg = (
            "You are a routing classifier for an AI assistant named Zen. "
            "Return only a JSON object with keys 'intent' and 'confidence'. "
            "Valid intents: 'web', 'code', 'computer', 'chat'."
        )
        user_msg = (
            f"Query: {query}\n\n"
            "Rules:\n"
            "- Use 'web' for questions requiring internet search or fresh info.\n"
            "- Use 'code' for Python code execution tasks.\n"
            "- Use 'computer' for automation (browsing, clicking, typing).\n"
            "- Use 'chat' for general advice, conversation, or opinions.\n"
            "- Always return a JSON object only."
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
        )

        content = resp.choices[0].message.content
        data = json.loads(content)
        intent = data.get("intent", heuristic).lower()

        if intent not in VALID_INTENTS:
            logger.warning("Invalid intent from API: %s. Falling back to heuristic.", intent)
            return heuristic
        return intent

    except Exception as e:
        logger.error("Intent classification failed: %s", e)
        return heuristic


def _heuristic_intent(query: str) -> Intent:
    q = query.lower()
    code_keywords = [
        "python", "write code", "implement", "calculate", "plot", "script",
        "function", "class", "regex", "pandas", "numpy", "matplotlib",
        "execute", "run code", "simulate", "algorithm", "solve"
    ]
    computer_keywords = [
        "browse", "navigate", "click", "type", "screenshot", "automate",
        "website", "webpage", "browser", "scroll", "hover", "extract text",
        "fill form", "upload", "download", "search web"
    ]
    if any(k in q for k in code_keywords):
        return "code"
    if any(k in q for k in computer_keywords):
        return "computer"
    return "chat"


def route_query(intent: Intent, query: str):
    routes = {
        "code": run_code_interpreter,
        "web": run_zen_research,
        "computer": lambda q: ComputerUseAgent().run(q),
        "chat": lambda q: ChatTool()._run(message=q),
    }
    handler = routes.get(intent, routes["chat"])
    try:
        return handler(query)
    except Exception as e:
        logger.error("Error routing query: %s", e)
        return ChatTool()._run(message=query)
