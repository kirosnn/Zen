import os
import sys
from tools.search import run_zen_research
from tools.code_interpreter import run_code_interpreter
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

load_dotenv()

from intents.classifier import classify_intent
from intents.router import route_query

def main():
    console = Console()
    welcome_text = Text("✻ Welcome to Zen", style="bold blue")
    panel = Panel(welcome_text, border_style="blue", expand=False)
    console.print(panel)
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        intent = classify_intent(query)
        print(f"Routing intent: {intent} | Query: {query}")
        result = route_query(intent, query)
        try:
            print("\n⏺  " + result.raw)
        except Exception:
            print("\n⏺  " + str(result))
    else:
        console.print("[dim]Enter your query (or [blue]'quit'[/blue] to exit)[/dim]", style="dim")
        try:
            while True:
                query = input("\n> ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    console.print("\n[dim]Goodbye![/dim]", style="dim")
                    break
                
                if not query:
                    console.print("[dim]Please enter a valid query.[/dim]", style="dim")
                    continue
                
                intent = classify_intent(query)
                print(f"\nRouting intent: {intent}")
                try:
                    result = route_query(intent, query)
                    try:
                        print("\n⏺  " + result.raw)
                    except Exception:
                        print("\n⏺  " + str(result))
                except Exception as e:
                    print(f"Error: {e}")
                    print("Please try again with a different query.")
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]", style="dim")

if __name__ == "__main__":
    main()