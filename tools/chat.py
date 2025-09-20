import os
import requests
import json
from typing import Optional, Dict, Any
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool
from dotenv import load_dotenv
from utils.install_ollama import OllamaInstaller
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class ChatTool(BaseTool):
    name: str = "Chat Tool"
    description: str = """
    A tool for having conversations with a local AI model via Ollama.
    Supports sending messages and receiving responses from various local LLM models.
    """
    model: str = "mistral:7b"    
    base_url: str = "http://localhost:11434"
    api_url: str = "http://localhost:11434/api/generate"
    system_prompt: Optional[str] = None

    def __init__(self, model: Optional[str] = None, base_url: str = "http://localhost:11434", system_prompt: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        if model is None:
            self.model = os.getenv("OLLAMA_MODEL", "mistral:7b")
        else:
            self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        self.system_prompt = system_prompt
        self._installer = None

    @property
    def installer(self):
        if self._installer is None:
            self._installer = OllamaInstaller(self.model, self.base_url)
        return self._installer

    def _ensure_ollama_ready(self) -> bool:
        try:
            installer = self.installer
            success, message = installer.ensure_ollama_ready()
            if success:
                logger.info("Ollama is ready to use")
                return True
            else:
                logger.error(f"Failed to set up Ollama: {message}")
                return False
        except Exception as e:
            logger.error(f"Error setting up Ollama: {str(e)}")
            return False

    def _run(self, message: str, stream: bool = False, **kwargs) -> str:
        if not message:
            return "Error: Message cannot be empty"

        if not self._ensure_ollama_ready():
            return "Error: Unable to set up Ollama. Please check the installation and try again."

        try:
            payload = {
                "model": self.model,
                "prompt": message,
                "stream": stream,
                **kwargs
            }
            
            if self.system_prompt:
                payload["system"] = self.system_prompt

            if stream:
                return self._handle_streaming_response(payload)
            else:
                response = requests.post(self.api_url, json=payload, timeout=300)

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "No response received from the model")
                else:
                    return f"Error: Ollama API returned status code {response.status_code}. Make sure Ollama is running and the model '{self.model}' is installed."

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error communicating with Ollama: {str(e)}")
            return f"Error: Could not connect to Ollama. Make sure it's running on {self.base_url}. Details: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return f"Error: Unexpected error occurred: {str(e)}"

    def _handle_streaming_response(self, payload: Dict[str, Any]) -> str:
        try:
            response = requests.post(self.api_url, json=payload, stream=True, timeout=600)
            
            if response.status_code != 200:
                return f"Error: Ollama API returned status code {response.status_code}. Make sure Ollama is running and the model '{self.model}' is installed."
            
            full_response = []
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        line = line[6:]
                    
                    try:
                        chunk = json.loads(line)
                        if 'response' in chunk:
                            full_response.append(chunk['response'])
                        if chunk.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
            
            return ''.join(full_response)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during streaming: {str(e)}")
            return f"Error: Could not connect to Ollama for streaming. Details: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during streaming: {str(e)}")
            return f"Error: Unexpected error during streaming: {str(e)}"


class ChatAgent:
    def __init__(self, model: Optional[str] = None, system_prompt: Optional[str] = None):
        if model is None:
            model = os.getenv("OLLAMA_MODEL", "mistral:7b")
        self.chat_tool = ChatTool(model=model, system_prompt=system_prompt)
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        ollama_llm = LLM(
            model=f"ollama/{self.chat_tool.model}",
            base_url=self.chat_tool.base_url
        )
        
        return Agent(
            role="AI Chat Assistant",
            goal="Facilitate natural conversations with users using local LLM via Ollama",
            backstory="""
            A conversational AI assistant powered by local language models.
            Specializes in engaging, helpful, and informative conversations on any topic.
            Uses Ollama to run models locally for privacy and offline capability.
            """,
            tools=[self.chat_tool],
            llm=ollama_llm,
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            memory=True
        )

    def create_task(self, user_message: str) -> Task:
        return Task(
            description=f"Have a conversation with the user: {user_message}",
            expected_output="A natural, helpful response to the user's message",
            agent=self.agent
        )

    def chat(self, message: str, stream: bool = False) -> str:
        try:
            if stream:
                return self.chat_tool._run(message, stream=True)
            else:
                task = self.create_task(message)
                crew = Crew(
                    agents=[self.agent],
                    tasks=[task],
                    verbose=True
                )
                result = crew.kickoff()
                return str(result)
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return self.chat_tool._run(message, stream=stream)


def simple_chat(message: str, model: Optional[str] = None, system_prompt: Optional[str] = None, stream: bool = False) -> str:
    if model is None:
        model = os.getenv("OLLAMA_MODEL", "mistral:7b")
    tool = ChatTool(model=model, system_prompt=system_prompt)
    return tool._run(message, stream=stream)