import os
import asyncio
import base64
import io
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path
from PIL import Image
import numpy as np
from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from dotenv import load_dotenv
import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from browser_use import Agent as BrowserAgent, ChatOpenAI
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
    BrowserAgent = None
    ChatOpenAI = None

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Install with: pip install playwright")

load_dotenv()

class EnhancedComputerUseTool(BaseTool):
    name: str = "Enhanced Computer Use"
    description: str = """
    Advanced web browser automation with visual feedback. Capabilities:
    - Navigate and interact with any website
    - Take and annotate screenshots with element highlighting
    - Visual element detection and interaction
    - Form filling and data extraction
    - Multi-step workflow automation
    - Session management and cookies handling
    """
    screenshot_dir: Optional[Path] = None
    session_data: Dict[str, Any] = {}
    browser: Optional[Any] = None
    page: Optional[Any] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        self.session_data = {}
        self.browser = None
        self.page = None
        
        if not BROWSER_USE_AVAILABLE and not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Neither Browser Use nor Playwright is installed. Install with:\n"
                "pip install browser-use playwright\n"
                "playwright install chromium"
            )

    async def _init_browser(self):
        if PLAYWRIGHT_AVAILABLE and not self.browser:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=False,
                args=['--start-maximized']
            )
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self.page = await context.new_page()
            
    async def _close_browser(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None

    def _run(
        self,
        action: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            result = asyncio.run(self._execute_action(
                action=action,
                url=url,
                selector=selector,
                text=text,
                **kwargs
            ))
            return result
        except Exception as e:
            logger.error(f"Error in browser action: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "action": action
            }

    async def _execute_action(
        self,
        action: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if PLAYWRIGHT_AVAILABLE:
            await self._init_browser()
        
        action = action.lower()
        result = {"status": "success", "action": action}
        
        try:
            if action == "navigate":
                result.update(await self._navigate(url))
                
            elif action == "click":
                result.update(await self._click(selector, **kwargs))
                
            elif action == "type":
                result.update(await self._type(selector, text, **kwargs))
                
            elif action == "screenshot":
                result.update(await self._screenshot(**kwargs))
                
            elif action == "extract":
                result.update(await self._extract(selector, **kwargs))
                
            elif action == "scroll":
                result.update(await self._scroll(**kwargs))
                
            elif action == "wait":
                result.update(await self._wait(selector, **kwargs))
                
            elif action == "hover":
                result.update(await self._hover(selector))
                
            elif action == "select":
                result.update(await self._select(selector, text))
                
            elif action == "upload":
                result.update(await self._upload(selector, kwargs.get('file_path')))
                
            elif action == "execute_script":
                result.update(await self._execute_script(kwargs.get('script')))
                
            else:
                result = {
                    "status": "error",
                    "message": f"Unknown action: {action}",
                    "supported_actions": [
                        "navigate", "click", "type", "screenshot", "extract",
                        "scroll", "wait", "hover", "select", "upload", "execute_script"
                    ]
                }
                
        except Exception as e:
            result = {
                "status": "error",
                "action": action,
                "message": str(e)
            }
            
        return result

    async def _navigate(self, url: str) -> Dict[str, Any]:
        if not url:
            return {"error": "URL is required for navigation"}
            
        if self.page:
            response = await self.page.goto(url, wait_until='networkidle')
            await asyncio.sleep(1)
            
            screenshot_path = await self._take_screenshot(f"navigate_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return {
                "url": url,
                "status_code": response.status if response else None,
                "title": await self.page.title(),
                "screenshot": screenshot_path
            }
        else:
            return {"message": f"Navigated to {url}"}

    async def _click(self, selector: str, highlight: bool = True, **kwargs) -> Dict[str, Any]:
        if not selector:
            return {"error": "Selector is required for click action"}
            
        if self.page:
            if highlight:
                await self._highlight_element(selector)
                
            element = await self.page.wait_for_selector(selector, timeout=5000)
            
            before_screenshot = await self._take_screenshot(f"before_click_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            before_screenshot = await self._take_screenshot(f"before_click_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            await element.click()
            await asyncio.sleep(0.5)
            
            after_screenshot = await self._take_screenshot(f"after_click_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return {
                "selector": selector,
                "clicked": True,
                "screenshots": {
                    "before": before_screenshot,
                    "after": after_screenshot
                }
            }
        else:
            return {"message": f"Clicked element: {selector}"}

    async def _type(self, selector: str, text: str, clear_first: bool = True, **kwargs) -> Dict[str, Any]:
        if not selector or text is None:
            return {"error": "Selector and text are required for type action"}
            
        if self.page:
            element = await self.page.wait_for_selector(selector, timeout=5000)
            
            if clear_first:
                await element.click()
                await element.press('Control+a')
                await element.press('Delete')
                
            await element.type(text, delay=kwargs.get('delay', 50))
            
            screenshot_path = await self._take_screenshot(f"typed_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return {
                "selector": selector,
                "text": text,
                "typed": True,
                "screenshot": screenshot_path
            }
        else:
            return {"message": f"Typed '{text}' into {selector}"}

    async def _screenshot(self, annotate: bool = True, full_page: bool = False, **kwargs) -> Dict[str, Any]:
        if self.page:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = kwargs.get('filename', f'screenshot_{timestamp}')
            
            if annotate:
                await self._annotate_page()
            
            screenshot_path = await self._take_screenshot(
                filename,
                full_page=full_page,
                clip=kwargs.get('clip')
            )
            
            with open(screenshot_path, 'rb') as img_file:
                base64_image = base64.b64encode(img_file.read()).decode('utf-8')
            
            return {
                "screenshot_path": str(screenshot_path),
                "base64_image": base64_image,
                "timestamp": timestamp,
                "url": self.page.url,
                "title": await self.page.title(),
                "dimensions": await self.page.viewport_size()
            }
        else:
            return {"message": "Screenshot taken"}

    async def _extract(self, selector: str, attribute: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        if not selector:
            return {"error": "Selector is required for extract action"}
            
        if self.page:
            elements = await self.page.query_selector_all(selector)
            
            extracted_data = []
            for element in elements:
                if attribute:
                    value = await element.get_attribute(attribute)
                else:
                    value = await element.text_content()
                extracted_data.append(value)
            
            for element in elements:
                await self._highlight_element_object(element)
            
            screenshot_path = await self._take_screenshot(f"extracted_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return {
                "selector": selector,
                "count": len(extracted_data),
                "data": extracted_data,
                "screenshot": screenshot_path
            }
        else:
            return {"message": f"Extracted from {selector}"}

    async def _scroll(self, direction: str = "down", amount: int = 500, **kwargs) -> Dict[str, Any]:
        if self.page:
            if direction == "down":
                await self.page.mouse.wheel(0, amount)
            elif direction == "up":
                await self.page.mouse.wheel(0, -amount)
            elif direction == "bottom":
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "top":
                await self.page.evaluate("window.scrollTo(0, 0)")
            
            await asyncio.sleep(0.5)
            screenshot_path = await self._take_screenshot(f"scroll_{direction}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return {
                "direction": direction,
                "amount": amount,
                "screenshot": screenshot_path
            }
        else:
            return {"message": f"Scrolled {direction}"}

    async def _wait(self, selector: str, timeout: int = 30000, **kwargs) -> Dict[str, Any]:
        if self.page:
            try:
                await self.page.wait_for_selector(selector, timeout=timeout)
                return {"found": True, "selector": selector}
            except:
                return {"found": False, "selector": selector, "timeout": timeout}
        else:
            return {"message": f"Waited for {selector}"}

    async def _hover(self, selector: str) -> Dict[str, Any]:
        if self.page:
            element = await self.page.wait_for_selector(selector)
            await element.hover()
            await asyncio.sleep(0.5)
            
            screenshot_path = await self._take_screenshot(f"hover_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return {
                "selector": selector,
                "hovered": True,
                "screenshot": screenshot_path
            }
        else:
            return {"message": f"Hovered over {selector}"}

    async def _select(self, selector: str, value: str) -> Dict[str, Any]:
        if self.page:
            await self.page.select_option(selector, value)
            
            screenshot_path = await self._take_screenshot(f"select_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return {
                "selector": selector,
                "value": value,
                "selected": True,
                "screenshot": screenshot_path
            }
        else:
            return {"message": f"Selected {value} in {selector}"}

    async def _upload(self, selector: str, file_path: str) -> Dict[str, Any]:
        if self.page and file_path:
            element = await self.page.wait_for_selector(selector)
            await element.set_input_files(file_path)
            
            return {
                "selector": selector,
                "file_path": file_path,
                "uploaded": True
            }
        else:
            return {"message": f"Uploaded file to {selector}"}

    async def _execute_script(self, script: str) -> Dict[str, Any]:
        if self.page and script:
            result = await self.page.evaluate(script)
            return {
                "script": script[:100] + "..." if len(script) > 100 else script,
                "result": result
            }
        else:
            return {"message": "Script executed"}

    async def _take_screenshot(self, filename: str, full_page: bool = False, clip: Optional[Dict] = None) -> Path:
        if not filename.endswith('.png'):
            filename += '.png'
            
        screenshot_path = self.screenshot_dir / filename
        
        if self.page:
            screenshot_options = {"path": str(screenshot_path)}
            if full_page:
                screenshot_options["full_page"] = True
            if clip:
                screenshot_options["clip"] = clip
                
            await self.page.screenshot(**screenshot_options)
            
        return screenshot_path

    async def _highlight_element(self, selector: str):
        if self.page:
            try:
                await self.page.evaluate(f"""
                    const element = document.querySelector('{selector}');
                    if (element) {{
                        element.style.border = '3px solid red';
                        element.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
                        setTimeout(() => {{
                            element.style.border = '';
                            element.style.backgroundColor = '';
                        }}, 2000);
                    }}
                """)
            except:
                pass

    async def _highlight_element_object(self, element):
        if element:
            try:
                await element.evaluate("""
                    element => {
                        element.style.border = '2px solid blue';
                        element.style.backgroundColor = 'rgba(0, 0, 255, 0.1)';
                        setTimeout(() => {
                            element.style.border = '';
                            element.style.backgroundColor = '';
                        }, 2000);
                    }
                """)
            except:
                pass

    async def _annotate_page(self):
        if self.page:
            try:
                await self.page.evaluate("""
                    // Highlight all clickable elements
                    const clickables = document.querySelectorAll('a, button, input, select, textarea, [onclick]');
                    clickables.forEach((el, index) => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            el.style.outline = '1px dashed rgba(0, 123, 255, 0.5)';
                            
                            // Add index label
                            const label = document.createElement('div');
                            label.textContent = index + 1;
                            label.style.cssText = `
                                position: absolute;
                                top: ${rect.top + window.scrollY}px;
                                left: ${rect.left + window.scrollX - 20}px;
                                background: #007bff;
                                color: white;
                                padding: 2px 5px;
                                border-radius: 3px;
                                font-size: 11px;
                                z-index: 10000;
                                pointer-events: none;
                            `;
                            document.body.appendChild(label);
                            
                            // Remove after 3 seconds
                            setTimeout(() => {
                                el.style.outline = '';
                                label.remove();
                            }, 3000);
                        }
                    });
                """)
            except:
                pass


class WebSearchTool(BaseTool):
    name: str = "Web Search"
    description: str = "Perform web searches using Google via Serper API to get relevant information and sources."

    def _run(self, query: str, **kwargs) -> str:
        api_key = os.getenv('SERPER_API_KEY')
        if not api_key:
            return "Error: SERPER_API_KEY not found in environment variables"
        
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'q': query,
            'num': 7,
            **kwargs
        }
        
        try:
            response = requests.post("https://google.serper.dev/search", 
                                   headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            results = []
            sources = []
            if 'organic' in data:
                for idx, result in enumerate(data['organic'][:7], 1):
                    title = result.get('title', 'No title')
                    snippet = result.get('snippet', 'No description')
                    link = result.get('link', '')
                    results.append(f"- **{title}**: {snippet}")
                    sources.append(f"[{idx}]({link})")
            
            if results:
                return "\n".join(results) + "\n\nSources:\n" + "\n".join(sources)
            else:
                return "No results found."
            
        except Exception as e:
            return f"Error: {str(e)}"


class ComputerUseAgent:
    def __init__(self):
        self.tool = EnhancedComputerUseTool()
        self.web_search_tool = WebSearchTool()
        self.agent = self._create_agent()
        
    def _create_agent(self) -> Agent:
        return Agent(
            role="Advanced Computer Use Specialist",
            goal="Perform sophisticated web browser automation tasks with visual feedback and intelligent interaction",
            backstory="""
            An expert in web automation with advanced capabilities including:
            - Visual element detection and interaction
            - Multi-step workflow automation
            - Intelligent form filling and data extraction
            - Screenshot capture with annotations
            - Session and state management
            Specializes in creating seamless automation flows that mimic human interaction patterns.
            """,
            tools=[self.tool, self.web_search_tool],
            llm="gpt-4o-mini",
            verbose=True,
            allow_delegation=False,
            max_iter=10,
            memory=True
        )
    
    def create_task(self, description: str, expected_output: str = None) -> Task:
        return Task(
            description=description,
            expected_output=expected_output or "Complete the browser automation task and provide detailed results with screenshots.",
            agent=self.agent
        )
    
    def run(self, task_description: str) -> Any:
        task = self.create_task(task_description)
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        return crew.kickoff()


class BrowserAutomationWorkflow:
    def __init__(self):
        self.tool = EnhancedComputerUseTool()
        self.results = []
        
    async def execute_workflow(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for i, step in enumerate(steps):
            logger.info(f"Executing step {i+1}/{len(steps)}: {step.get('action')}")
            
            result = self.tool._run(**step)
            self.results.append(result)
            
            if result.get('status') == 'error':
                logger.error(f"Error in step {i+1}: {result.get('message')}")
                if not step.get('continue_on_error', False):
                    break
                    
            if 'delay' in step:
                await asyncio.sleep(step['delay'])
                
        return self.results
    
    def save_results(self, filename: str = "workflow_results.json"):
        output_path = Path("results") / filename
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
            
        logger.info(f"Results saved to {output_path}")
        return output_path


def navigate_to_website(url: str) -> Dict[str, Any]:
    tool = EnhancedComputerUseTool()
    return tool._run(action="navigate", url=url)

def click_element(selector: str, highlight: bool = True) -> Dict[str, Any]:
    tool = EnhancedComputerUseTool()
    return tool._run(action="click", selector=selector, highlight=highlight)

def type_text(selector: str, text: str, clear_first: bool = True) -> Dict[str, Any]:
    tool = EnhancedComputerUseTool()
    return tool._run(action="type", selector=selector, text=text, clear_first=clear_first)

def extract_text(selector: str, attribute: Optional[str] = None) -> Dict[str, Any]:
    tool = EnhancedComputerUseTool()
    return tool._run(action="extract", selector=selector, attribute=attribute)

def take_screenshot(filename: Optional[str] = None, annotate: bool = True, full_page: bool = False) -> Dict[str, Any]:
    tool = EnhancedComputerUseTool()
    return tool._run(action="screenshot", filename=filename, annotate=annotate, full_page=full_page)


if __name__ == "__main__":
    tool = EnhancedComputerUseTool()

    tool._run(action="navigate", url="https://kirosnn.fr")

    data = tool._run(action="extract", selector="html")

    screenshot = tool._run(action="screenshot", filename="kirosnn.png")
