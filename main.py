import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from orchestrator import Orchestrator
from config import config

console = Console()


def run_single_query(query: str):
    """Esegue una singola query e stampa il risultato."""
    console.print(Panel.fit(
        f"[bold blue]⚡ Energy Smart RAG[/bold blue]\n"
        f"[dim]Model: {config.model_name} | One-shot mode[/dim]",
        border_style="blue"
    ))
    console.print(f"\n[bold green]Query:[/bold green] {query}\n")

    orch = Orchestrator()
    response = orch.query(query)

    console.print()
    console.print(Panel(Markdown(response), title="[bold cyan]Risposta[/bold cyan]", border_style="cyan"))
    console.print()


def run_interactive():
    """REPL interattiva."""
    console.print(Panel.fit(
        f"[bold blue]⚡ Energy Smart RAG CLI[/bold blue]\n"
        f"[dim]Model: {config.model_name} | Interactive mode[/dim]",
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
    if len(sys.argv) > 1:
        # One-shot: python main.py "la tua domanda"
        query = " ".join(sys.argv[1:])
        run_single_query(query)
    else:
        # Interactive REPL
        run_interactive()
