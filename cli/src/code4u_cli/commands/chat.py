"""Interactive chat commands."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live

from ..client import Code4uClient

app = typer.Typer(help="Chat with the AI agent")
console = Console()


@app.callback(invoke_without_command=True)
def chat_interactive(
    ctx: typer.Context,
    message: Optional[str] = typer.Argument(None, help="Single message (or omit for interactive mode)"),
):
    """Start an interactive chat session or send a single message."""
    if ctx.invoked_subcommand is not None:
        return
    
    if message:
        asyncio.run(_chat_single(message))
    else:
        asyncio.run(_chat_interactive())


async def _chat_single(message: str):
    """Send a single message and get response."""
    console.print(f"\n[bold cyan]You:[/bold cyan] {message}\n")
    
    async with Code4uClient() as client:
        response_text = ""
        
        try:
            async for chunk in client.chat_stream(message):
                response_text += chunk
                console.print(chunk, end="")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    console.print("\n")


async def _chat_interactive():
    """Interactive chat session."""
    console.print(Panel(
        Markdown("""
# code4u.ai Chat

Interactive AI assistant for code engineering.

**Commands:**
- Type your message and press Enter
- `/clear` - Clear conversation
- `/exit` or `Ctrl+C` - Exit

**Examples:**
- "How do I add authentication to my API?"
- "Explain this function: [paste code]"
- "Refactor this to use async/await"
        """),
        title="💬 code4u.ai Chat",
        border_style="cyan",
    ))
    
    conversation_id = None
    
    async with Code4uClient() as client:
        while True:
            try:
                # Get user input
                console.print()
                user_input = console.input("[bold cyan]You:[/bold cyan] ")
                
                if not user_input.strip():
                    continue
                
                # Handle commands
                if user_input.lower() == "/exit":
                    break
                if user_input.lower() == "/clear":
                    conversation_id = None
                    console.clear()
                    console.print("[dim]Conversation cleared[/dim]")
                    continue
                if user_input.lower() == "/help":
                    console.print("[dim]Commands: /clear, /exit, /help[/dim]")
                    continue
                
                # Get response
                console.print()
                console.print("[bold green]code4u.ai:[/bold green] ", end="")
                
                try:
                    async for chunk in client.chat_stream(user_input, conversation_id):
                        console.print(chunk, end="")
                    console.print()
                except Exception as e:
                    console.print(f"\n[red]Error: {e}[/red]")
                
            except KeyboardInterrupt:
                console.print("\n\n[dim]Goodbye![/dim]")
                break
            except EOFError:
                break
    
    console.print()


@app.command("ask")
def chat_ask(
    question: str = typer.Argument(..., help="Question to ask"),
):
    """Ask a single question."""
    asyncio.run(_chat_single(question))

