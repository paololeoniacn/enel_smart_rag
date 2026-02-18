from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from orchestrator import Orchestrator
import config

console = Console()

def main():
    console.print(Panel.fit(
        f"[bold blue]⚡ Enel Smart RAG CLI[/bold blue]\n[dim]Model: {config.model_name}[/dim]",
        border_style="blue"
    ))
    
    orch = Orchestrator()
    
    while True:
        try:
            user_input = console.input("[bold green]Tu:[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Uscita.[/dim]")
            break
        
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            break
        
        with console.status("[cyan]Ragionamento in corso...[/cyan]"):
            response = orch.query(user_input)
        
        console.print()
        console.print(Markdown(response))
        console.print()


if __name__ == "__main__":
    main()
