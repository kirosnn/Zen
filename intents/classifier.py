import os
from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

load_dotenv()

def classify_intent(query: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("MODEL", "gpt-5-nano-2025-08-07")

    heuristic = _heuristic_intent(query)

    if OpenAI is None or not api_key:
        return heuristic

    try:
        client = OpenAI()
        system = (
            "You are a routing classifier for an AI assistant named Zen. "
            "Decide if the user wants web research, Python code execution, or computer/browser automation. "
            "Return only a JSON object with keys 'intent' and 'confidence'. "
            "Valid intents: 'web', 'code', 'computer', 'chat'."
        )
        user = (
            f"Query: {query}\n\n"
            "Decide the best intent:\n"
            "- Use 'web' for questions that require up-to-date information, facts, citations, or searching the internet.\n"
            "- Use 'code' for tasks requiring writing/executing Python (math, data manipulation, quick scripts).\n"
            "- Use 'computer' for web browser automation, interacting with websites, clicking, typing, screenshotting, etc.\n"
            "- Use 'chat' for general conversation, opinions, advice, or casual questions.\n"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        import json
        data = json.loads(content)
        intent = data.get("intent", "web").lower()
        if intent not in {"web", "code", "computer", "chat"}:
            return heuristic
        return intent
    except Exception:
        return heuristic

def _heuristic_intent(query: str) -> str:
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
