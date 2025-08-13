import re  # Add this import
import os
import sys
import subprocess
import shutil
import platform
import signal
import pty
import select
import termios
import tty
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import readline
import json
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.live import Live
from rich.spinner import Spinner
from rich import box
from rich.markdown import Markdown
from rich.theme import Theme
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

from ai_agent import AIAgent
from ai_core import AICore 

class NLShell:
    def __init__(self):
        self.console = Console(theme=Theme(self._get_theme()))
        self.ai_core = AICore()
        self.ai_agent = AIAgent(self.ai_core)
        self.current_dir = os.getcwd()
        self.history = []
        self.session_start = datetime.now()
        self.command_count = 0
        
        
        load_dotenv()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialize readline for command history
        readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(' \t\n;')

    async def _handle_agent_query(self, user_input: str) -> bool:
        """Handle queries that should be executed automatically by the AI agent"""
        agent_suffix_pattern = r'.*-a$'

        is_agent_query = (
            re.match(agent_suffix_pattern, user_input.strip().lower()) is not None
        )
        
        if not is_agent_query:
            return False
        
        # Remove -a suffix for processing
        query = user_input[:-2].strip()
        
        self.console.print("[yellow]🤖 AI Agent is analyzing and executing safe commands...[/yellow]")
        
        with self.console.status("[blue]Agent working...[/blue]", spinner="dots"):
            agent_result = await self.ai_agent.process_agent_query(query, self.current_dir, self.history)
        
        # Handle different response types
        if agent_result['type'] == 'agent_response':
            # Commands were auto-executed
            if agent_result['executed_commands']:
                executed_panel = Panel(
                    "\n".join([f"[dim]✓[/dim] [green]{cmd}[/green]" for cmd in agent_result['executed_commands']]),
                    title="[bold blue]Auto-executed Commands[/bold blue]",
                    border_style="blue",
                    box=box.MINIMAL
                )
                self.console.print(executed_panel)
            
            # Show interpretation
            if agent_result.get('interpretation'):
                result_panel = Panel(
                    Markdown(agent_result['interpretation']),
                    title="[bold magenta]AI Agent Analysis[/bold magenta]",
                    border_style="magenta",
                    box=box.ROUNDED
                )
                self.console.print(result_panel)
            
            # Update history
            self.history.append({
                'input': user_input,
                'commands': agent_result['executed_commands'],
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'directory': self.current_dir,
                'agent_executed': True
            })
            
        elif agent_result['type'] == 'confirmation_needed':
            # Some commands need confirmation
            self.console.print(f"[yellow]Agent found commands but they need confirmation:[/yellow]")
            
            commands_needing_confirmation = [
                r['command'] for r in agent_result['results'] 
                if r.get('needs_confirmation', False)
            ]
            
            if commands_needing_confirmation:
                await self._execute_commands_with_confirmation(commands_needing_confirmation)
        
        else:
            # Regular response
            response_panel = Panel(
                agent_result['message'],
                title="[bold blue]AI Response[/bold blue]",
                border_style="blue",
                box=box.ROUNDED
            )
            self.console.print(response_panel)
        
        return True
    async def _handle_file_analysis(self, user_input: str) -> bool:
        """Handle file analysis requests"""
        
        # Pattern matching for file analysis
        file_patterns = [
            r"what'?s in (this|the) file (.+)",
            r"analyze file (.+)",
            r"read file (.+)",
            r"what is (.+\.\w+)",
            r"open (.+\.\w+)",
        ]
        
        filepath = None
        for pattern in file_patterns:
            match = re.search(pattern, user_input.lower())
            if match:
                # Get the last group (filename)
                filepath = match.groups()[-1].strip()
                break
        
        if not filepath:
            return False
        
        # Convert relative path to absolute if needed
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.current_dir, filepath)
        
        self.console.print(f"[yellow]🤖 Analyzing file: {filepath}[/yellow]")
        
        with self.console.status("[blue]Reading file...[/blue]", spinner="dots"):
            file_result = await self.ai_agent.analyze_file(filepath)
        
        if file_result.get('error'):
            self.console.print(f"[red]Error: {file_result['error']}[/red]")
            return True
        
        # Display file analysis
        content_info = []
        content_info.append(f"**File:** `{file_result['filepath']}`")
        content_info.append(f"**Size:** {file_result['size']:,} bytes")
        content_info.append(f"**Type:** {file_result.get('mime_type', 'Unknown')}")
        
        if 'content' in file_result:
            content = file_result['content']
            
            if content.get('type') == 'text':
                content_info.append(f"**Lines:** {content['lines']}")
                content_info.append(f"**Characters:** {content['characters']}")
                content_info.append(f"\n**Preview:**\n```\n{content['preview']}\n```")
            
            elif content.get('type') == 'json':
                content_info.append(f"**Structure:** {content['structure']}")
                if content.get('keys'):
                    content_info.append(f"**Keys:** {', '.join(content['keys'][:10])}")
                content_info.append(f"\n**Preview:**\n```json\n{content['preview']}\n```")
            
            elif content.get('type') == 'csv':
                content_info.append(f"**Rows:** {content['rows']}")
                content_info.append(f"**Columns:** {content['columns']}")
                if content.get('column_names'):
                    content_info.append(f"**Column Names:** {', '.join(content['column_names'])}")
                content_info.append(f"\n**Preview:**\n```\n{content['preview']}\n```")
            
            elif content.get('type') == 'pdf':
                content_info.append(f"**Pages:** {content['pages']}")
                if content.get('text_preview'):
                    content_info.append(f"\n**Text Preview:**\n```\n{content['text_preview']}\n```")
            
            elif content.get('type') == 'image':
                content_info.append(f"**Dimensions:** {content['dimensions']}")
                content_info.append(f"**Format:** {content['format']}")
                content_info.append(f"**Size:** {content['size_mb']} MB")
            
            elif content.get('error'):
                content_info.append(f"**Error:** {content['error']}")
        
        analysis_panel = Panel(
            Markdown("\n".join(content_info)),
            title="[bold green]File Analysis[/bold green]",
            border_style="green",
            box=box.ROUNDED
        )
        self.console.print(analysis_panel)
        
        return True
        
    def _get_theme(self):
        """Define the shell color theme"""
        return {
            "prompt": "bold cyan",
            "command": "bold green",
            "error": "bold red",
            "warning": "bold yellow",
            "success": "bold green",
            "info": "blue",
            "ai": "magenta",
            "thinking": "dim magenta",
            "system": "dim white"
        }
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        self.console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
    
    def _get_shell_prompt(self) -> str:
        """Generate dynamic prompt similar to zsh/bash"""
        # Get current environment (conda, venv, etc.)
        env_name = os.environ.get('CONDA_DEFAULT_ENV', 
                                 os.environ.get('VIRTUAL_ENV', '').split('/')[-1] if os.environ.get('VIRTUAL_ENV') else 'base')
        
        # Get current directory (show ~ for home)
        home = str(Path.home())
        current = self.current_dir
        if current.startswith(home):
            current = current.replace(home, '~', 1)
        
        # Get just the directory name if path is long
        if len(current) > 30:
            current = '...' + current[-27:]
        
        return f"({env_name}) ai_terminal {current} % "
    
    def _create_banner(self):
        """Create welcome banner"""
        banner_text = """
        # 🤖 Natural Language Shell 
        *Powered by AI with Thinking Capability • Type in plain English*


        **Commands:**
        • `!command` - Direct shell execution  
        • `query -q` - Ask AI questions
        • `agentic query -a` - Ask AI questions
        • `save_mem "key" "value"` - Save to memory
        • `show_thinking` - Show AI's thinking process
        • `exit` - Quit shell

                """
                
        panel = Panel(
            Markdown(banner_text),
            title="[bold cyan]Enhanced NL Shell[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )
        self.console.print(panel)
        self.console.print()
    
    def _is_direct_command(self, user_input: str) -> bool:
        """Check if command should be executed directly"""
        return (user_input.startswith('!') or user_input.endswith('!') or 
                user_input.startswith('! '))
    
    def _is_question(self, user_input: str) -> bool:
        """Check if input is a general question"""
        return user_input.endswith('-q')
    
    def _clean_direct_command(self, user_input: str) -> str:
        """Clean direct command of ! markers"""
        return user_input.strip('! ').strip()
    
    def _clean_question(self, user_input: str) -> str:
        """Clean question of -q marker"""
        return user_input[:-2].strip()
    
    def _is_interactive_command(self, command: str) -> bool:
        """Check if command is likely to be interactive"""
        interactive_patterns = [
            # Executable files (common extensions)
            lambda cmd: any(cmd.strip().startswith(f'./{ext}') or cmd.strip().endswith(f'.{ext}') 
                          for ext in ['exe', 'out', 'bin']),
            # Executable without extension (./program_name)
            lambda cmd: cmd.strip().startswith('./') and not any(ext in cmd for ext in ['.txt', '.log', '.conf']),
            # Programs that typically require input
            lambda cmd: any(prog in cmd.lower() for prog in ['python -i', 'node', 'irb', 'ghci']),
            # Custom compiled programs (no extension, executable)
            lambda cmd: '/' in cmd and os.path.isfile(cmd.strip().split()[0]) and os.access(cmd.strip().split()[0], os.X_OK)
        ]
        
        return any(pattern(command) for pattern in interactive_patterns)
    
    def _show_thinking_process(self):
        """Display the AI's thinking steps"""
        thinking_steps = self.ai_core.get_thinking_steps()
        
        if not thinking_steps:
            self.console.print("[yellow]No thinking steps recorded yet.[/yellow]")
            return
        
        thinking_text = "## AI Thinking Process\n\n"
        for i, step in enumerate(thinking_steps, 1):
            thinking_text += f"**Step {i}:** `{step.command}`\n"
            thinking_text += f"*Reasoning:* {step.reasoning}\n"
            thinking_text += f"*Output:* {step.output[:200]}{'...' if len(step.output) > 200 else ''}\n"
            thinking_text += f"*Next Action:* {step.next_action}\n\n"
        
        panel = Panel(
            Markdown(thinking_text),
            title="[bold thinking]🧠 AI Thinking Process[/bold thinking]",
            border_style="dim magenta",
            box=box.ROUNDED
        )
        self.console.print(panel)
    
    def _display_thinking_progress(self, message: str, commands: List[str]):
        """Display thinking progress with commands being explored"""
        thinking_panel = Panel(
            f"[thinking]{message}[/thinking]\n\n" +
            "[dim]Exploring:[/dim]\n" + 
            "\n".join([f"[dim]• {cmd}[/dim]" for cmd in commands]),
            title="[bold thinking]🧠 AI Thinking...[/bold thinking]",
            border_style="dim magenta",
            box=box.ROUNDED
        )
        self.console.print(thinking_panel)
    
    async def _execute_command(self, command: str) -> Tuple[int, str, str]:
        """Execute a shell command and return (returncode, stdout, stderr)"""
        try:
            # Handle cd command specially
            if command.strip().startswith('cd '):
                path = command.strip()[3:].strip()
                if not path:
                    path = str(Path.home())
                try:
                    os.chdir(os.path.expanduser(path))
                    self.current_dir = os.getcwd()
                    return 0, f"Changed directory to {self.current_dir}", ""
                except OSError as e:
                    return 1, "", str(e)
            
            # Check if this is an interactive command
            if self._is_interactive_command(command):
                return await self._execute_interactive_command(command)
            
            # Execute other commands normally
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.current_dir
            )
            
            stdout, stderr = await process.communicate()
            return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')
            
        except Exception as e:
            return 1, "", str(e)
    
    async def _execute_interactive_command(self, command: str) -> Tuple[int, str, str]:
        """Execute an interactive command using pty for real-time I/O"""
        try:
            self.console.print(f"\n[bold yellow]🔄 Running interactive program: {command}[/bold yellow]")
            self.console.print("[dim]Press Ctrl+C to interrupt the program[/dim]")
            self.console.print("=" * 50)
            
            # Create a subprocess with pty for real-time interaction
            master_fd, slave_fd = pty.openpty()
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.current_dir,
                preexec_fn=os.setsid
            )
            
            os.close(slave_fd)  # Close slave fd in parent
            
            # Set terminal to raw mode to capture all input
            old_settings = None
            try:
                old_settings = termios.tcgetattr(sys.stdin.fileno())
                tty.setraw(sys.stdin.fileno())
            except:
                pass  # Not a TTY, continue without raw mode
            
            output_buffer = ""
            
            try:
                while process.poll() is None:
                    # Use select to handle both user input and program output
                    ready, _, _ = select.select([sys.stdin, master_fd], [], [], 0.1)
                    
                    if sys.stdin in ready:
                        # Read user input and send to program
                        try:
                            user_input = sys.stdin.read(1)
                            if user_input:
                                os.write(master_fd, user_input.encode())
                        except:
                            break
                    
                    if master_fd in ready:
                        # Read program output and display it
                        try:
                            data = os.read(master_fd, 1024)
                            if data:
                                output = data.decode('utf-8', errors='ignore')
                                output_buffer += output
                                # Print output immediately (real-time)
                                print(output, end='', flush=True)
                        except:
                            break
                
                # Wait for process to complete
                returncode = process.wait()
                
                # Read any remaining output
                try:
                    while True:
                        ready, _, _ = select.select([master_fd], [], [], 0.1)
                        if not ready:
                            break
                        data = os.read(master_fd, 1024)
                        if not data:
                            break
                        output = data.decode('utf-8', errors='ignore')
                        output_buffer += output
                        print(output, end='', flush=True)
                except:
                    pass
                
            except KeyboardInterrupt:
                # Handle Ctrl+C - terminate the process
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=2)
                except:
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        process.wait(timeout=1)
                    except:
                        pass
                returncode = -1
                self.console.print(f"\n[yellow]Program interrupted[/yellow]")
            
            finally:
                # Restore terminal settings
                if old_settings:
                    try:
                        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                    except:
                        pass
                
                try:
                    os.close(master_fd)
                except:
                    pass
            
            self.console.print("\n" + "=" * 50)
            if returncode == 0:
                self.console.print("[bold green]✓ Program completed successfully[/bold green]")
            else:
                self.console.print(f"[bold red]✗ Program exited with code {returncode}[/bold red]")
            
            return returncode, output_buffer, ""
            
        except Exception as e:
            self.console.print(f"[bold red]Error running interactive command: {e}[/bold red]")
            return 1, "", str(e)
    
    def _display_commands(self, commands: List[str], title: str = "AI Generated Commands"):
        """Display commands in a nice panel"""
        command_text = "\n".join([f"[bold green]${command}[/bold green]" for command in commands])
        
        panel = Panel(
            command_text,
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="blue",
            box=box.ROUNDED
        )
        self.console.print(panel)
    
    async def _execute_commands_with_confirmation(self, commands: List[str], auto_confirm: bool = False) -> bool:
        """Execute commands after user confirmation (or auto-confirm for thinking mode)"""
        if not commands:
            self.console.print("[yellow]No commands to execute.[/yellow]")
            return False
        
        self._display_commands(commands)
        
        if not auto_confirm and not Confirm.ask("\n[bold]Execute these commands?[/bold]", default=True):
            self.console.print("[yellow]Commands cancelled.[/yellow]")
            return False
        elif auto_confirm:
            self.console.print("\n[dim thinking]Auto-executing exploration commands...[/dim thinking]")
        
        success_count = 0
        for i, command in enumerate(commands, 1):
            if not auto_confirm:
                self.console.print(f"\n[dim]Executing {i}/{len(commands)}:[/dim] [bold]{command}[/bold]")
            
            # Check if it's an interactive command - don't show spinner for those
            if self._is_interactive_command(command):
                returncode, stdout, stderr = await self._execute_command(command)
            else:
                if auto_confirm:
                    # For thinking mode, show minimal output
                    returncode, stdout, stderr = await self._execute_command(command)
                else:
                    with self.console.status(f"[blue]Running command {i}...[/blue]", spinner="dots"):
                        returncode, stdout, stderr = await self._execute_command(command)
            
            if returncode == 0:
                success_count += 1
                if stdout.strip() and not self._is_interactive_command(command) and not auto_confirm:
                    # Display output in a subtle panel (only for non-interactive commands)
                    output_panel = Panel(
                        stdout.strip(),
                        title="[dim]Output[/dim]",
                        border_style="dim green",
                        box=box.MINIMAL
                    )
                    self.console.print(output_panel)
                elif not self._is_interactive_command(command) and not auto_confirm:
                    self.console.print("[dim green]✓ Command completed[/dim green]")
            else:
                if not auto_confirm:
                    self.console.print(f"[bold red]✗ Command failed (exit code {returncode})[/bold red]")
                    if stderr.strip():
                        error_panel = Panel(
                            stderr.strip(),
                            title="[bold red]Error[/bold red]",
                            border_style="red",
                            box=box.MINIMAL
                        )
                        self.console.print(error_panel)
                    
                    # Ask AI for error analysis and fix
                    await self._handle_command_error(command, returncode, stdout, stderr)
                    break
        
        if success_count == len(commands) and not auto_confirm:
            self.console.print(f"[bold green]✓ All {len(commands)} commands executed successfully![/bold green]")
        
        return success_count > 0
    
    async def _handle_command_error(self, failed_command: str, returncode: int, stdout: str, stderr: str):
        """Handle command errors with AI assistance"""
        self.console.print("\n[yellow]🤖 AI is analyzing the error...[/yellow]")
        
        with self.console.status("[blue]Thinking...[/blue]", spinner="dots"):
            ai_response = await self.ai_core.analyze_error(
                failed_command, returncode, stdout, stderr, self.history
            )
        
        if ai_response.needs_clarification:
            # AI needs more info
            clarification_panel = Panel(
                ai_response.message,
                title="[bold yellow]AI Needs Clarification[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED
            )
            self.console.print(clarification_panel)
            
            user_clarification = Prompt.ask("\n[bold]Your response[/bold]")
            
            # Get updated response with clarification
            with self.console.status("[blue]Processing clarification...[/blue]", spinner="dots"):
                ai_response = await self.ai_core.analyze_error_with_clarification(
                    failed_command, returncode, stdout, stderr, self.history, user_clarification
                )
        
        if ai_response.suggested_commands:
            self.console.print("\n[bold green]🤖 AI suggests a fix:[/bold green]")
            self.console.print(f"[dim]{ai_response.message}[/dim]")
            
            await self._execute_commands_with_confirmation(ai_response.suggested_commands)
        else:
            error_panel = Panel(
                ai_response.message,
                title="[bold red]AI Analysis[/bold red]",
                border_style="red",
                box=box.ROUNDED
            )
            self.console.print(error_panel)
    

    async def _handle_save_memory(self, user_input: str):
        """Handle save_mem command"""
        try:
            # Remove the command part and get the sentence
            sentence = user_input[len("save_mem"):].strip()

            if sentence:
                self.ai_core.save_persistent_memory(sentence)
                self.console.print(f"[green]✓ Saved sentence to memory[/green]")
            else:
                self.console.print("[red]Usage: save_mem <your sentence>[/red]")
        except Exception as e:
            self.console.print(f"[red]Error saving memory: {e}[/red]")
    
    async def _handle_view_memory(self):
        """View all saved persistent memory sentences"""
        summary = self.ai_core.get_memory_summary()
        persistent_memory = summary.get('persistent_memory', [])

        if not persistent_memory:
            self.console.print("[yellow]No memory stored yet.[/yellow]")
            return

        self.console.print("[bold cyan]Stored Memory:[/bold cyan]")
        for i, sentence in enumerate(persistent_memory, 1):
            self.console.print(f"[green]{i}.[/green] {sentence}")



    
    async def run(self):
        """Main shell loop"""
        self._create_banner()
        
        while True:
            try:
                # Update current directory
                self.current_dir = os.getcwd()
                
                # Get user input with dynamic prompt
                prompt_text = Text(self._get_shell_prompt(), style="prompt")
                user_input = Prompt.ask(prompt_text, console=self.console)
                
                if not user_input.strip():
                    continue
                
                # Handle special commands
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    self.console.print("[bold cyan]Goodbye! 👋[/bold cyan]")
                    break
                
                if user_input == 'show_thinking':
                    self._show_thinking_process()
                    continue
                
                if user_input.startswith('save_mem'):
                    await self._handle_save_memory(user_input)
                    continue

                if user_input.lower() in ['show mem','mem','show memory']:
                    await self._handle_view_memory()
                    continue

                
                # Track command
                self.command_count += 1
                
                # Handle different input types
                if self._is_direct_command(user_input):
                    # Direct shell command
                    command = self._clean_direct_command(user_input)
                    self.console.print(f"[dim]Executing:[/dim] [bold]{command}[/bold]")
                    
                    returncode, stdout, stderr = await self._execute_command(command)
                    
                    if returncode == 0:
                        if stdout.strip() and not self._is_interactive_command(command):
                            self.console.print(stdout)
                        elif not self._is_interactive_command(command):
                            self.console.print("[dim green]✓ Command completed[/dim green]")
                    else:
                        self.console.print(f"[bold red]Command failed (exit code {returncode})[/bold red]")
                        if stderr.strip():
                            self.console.print(f"[red]{stderr}[/red]")
                
                elif self._is_question(user_input):
                    # Check if it's an agent query first
                    if await self._handle_agent_query(user_input):
                        continue
                    
                    # Check if it's a file analysis request
                    if await self._handle_file_analysis(user_input):
                        continue
                    
                    # Regular AI question
                    question = self._clean_question(user_input)
                    self.console.print("[yellow]🤖 AI is thinking...[/yellow]")
                    
                    with self.console.status("[blue]Processing question...[/blue]", spinner="dots"):
                        response = await self.ai_core.answer_question(question, self.history)
                    
                    answer_panel = Panel(
                        Markdown(response),
                        title="[bold magenta]AI Response[/bold magenta]",
                        border_style="magenta",
                        box=box.ROUNDED
                    )
                    self.console.print(answer_panel)
                                
                else:
                    # Natural language command (with potential thinking mode)
                    if await self._handle_file_analysis(user_input):
                        continue
                    self.console.print("[yellow]🤖 AI is interpreting your command...[/yellow]")
                    
                    with self.console.status("[blue]Analyzing request...[/blue]", spinner="dots"):
                        ai_response = await self.ai_core.process_natural_language(user_input, self.current_dir, self.history)
                    
                    # Check if AI is in thinking mode
                    if ai_response.thinking_mode and ai_response.exploration_commands:
                        self._display_thinking_progress(ai_response.message, ai_response.exploration_commands)
                        
                        # Auto-execute exploration commands
                        with self.console.status("[thinking]🧠 Exploring and analyzing...[/thinking]", spinner="dots"):
                            await self._execute_commands_with_confirmation(ai_response.exploration_commands, auto_confirm=True)
                        
                        # The AI should have provided a final response after exploration
                        if ai_response.suggested_commands:
                            self.console.print(f"\n[bold green]🤖 Based on my analysis:[/bold green] {ai_response.message}")
                            success = await self._execute_commands_with_confirmation(ai_response.suggested_commands)
                        else:
                            # AI provided analysis/summary
                            analysis_panel = Panel(
                                Markdown(ai_response.message),
                                title="[bold ai]🧠 AI Analysis[/bold ai]",
                                border_style="magenta",
                                box=box.ROUNDED
                            )
                            self.console.print(analysis_panel)
                            success = True
                    
                    elif ai_response.needs_clarification:
                        clarification_panel = Panel(
                            ai_response.message,
                            title="[bold yellow]AI Needs Clarification[/bold yellow]",
                            border_style="yellow",
                            box=box.ROUNDED
                        )
                        self.console.print(clarification_panel)
                        
                        clarification = Prompt.ask("\n[bold]Please clarify[/bold]")
                        
                        with self.console.status("[blue]Processing clarification...[/blue]", spinner="dots"):
                            ai_response = await self.ai_core.process_with_clarification(
                                user_input, clarification, self.current_dir, self.history
                            )
                        
                        if ai_response.suggested_commands:
                            success = await self._execute_commands_with_confirmation(ai_response.suggested_commands)
                        else:
                            info_panel = Panel(
                                ai_response.message,
                                title="[bold blue]AI Response[/bold blue]",
                                border_style="blue",
                                box=box.ROUNDED
                            )
                            self.console.print(info_panel)
                            success = True
                    
                    elif ai_response.suggested_commands:
                        success = await self._execute_commands_with_confirmation(ai_response.suggested_commands)
                    else:
                        info_panel = Panel(
                            ai_response.message,
                            title="[bold blue]AI Response[/bold blue]",
                            border_style="blue",
                            box=box.ROUNDED
                        )
                        self.console.print(info_panel)
                        success = True
                    
                    # Update history (for non-direct commands)
                    if not self._is_direct_command(user_input) and not self._is_question(user_input):
                        # Ensure success is defined
                        success = locals().get('success', False)
                        
                        self.history.append({
                            'input': user_input,
                            'commands': ai_response.suggested_commands or [],
                            'success': success,
                            'timestamp': datetime.now().isoformat(),
                            'directory': self.current_dir,
                            'thinking_mode': getattr(ai_response, 'thinking_mode', False)
                        })
                
                # Keep history manageable
                if len(self.history) > 20:
                    self.history = self.history[-20:]
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use 'exit' to quit.[/yellow]")
                continue
            except EOFError:
                self.console.print("\n[bold cyan]Goodbye! 👋[/bold cyan]")
                break
            except Exception as e:
                self.console.print(f"[bold red]Unexpected error: {e}[/bold red]")
                continue

def main():
    """Entry point"""
    try:
        shell = NLShell()
        asyncio.run(shell.run())
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
