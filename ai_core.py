
#!/usr/bin/env python3
"""
Enhanced AI Core (ai_core.py)
Handles all AI operations, memory management, error analysis, and thinking capability.
"""

import os
import json
import platform
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

try:
    import google.generativeai as genai
    import openai
    from dotenv import load_dotenv
except ImportError:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "pip", "install", "google-generativeai", "openai", "python-dotenv"], check=True)
    import google.generativeai as genai
    import openai
    from dotenv import load_dotenv

@dataclass
class AIResponse:
    """Response from AI with commands and metadata"""
    message: str
    suggested_commands: List[str] = None
    needs_clarification: bool = False
    confidence: float = 1.0
    thinking_mode: bool = False
    exploration_commands: List[str] = None
    
    def __post_init__(self):
        """Initialize None fields to empty lists"""
        if self.suggested_commands is None:
            self.suggested_commands = []
        if self.exploration_commands is None:
            self.exploration_commands = []

@dataclass
class ThinkingStep:
    """A step in the thinking process"""
    command: str
    output: str
    reasoning: str
    next_action: str

class AICore:
    def __init__(self):
        load_dotenv()
        
        # Initialize API clients
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # Default to Gemini, fallback to OpenAI
        self.use_gemini = bool(self.gemini_api_key)
        
        # Prepare OpenAI client if key is present (even if Gemini is primary) for fallback
        self.client = None
        self._openai_v1 = False
        if self.openai_api_key:
            # Try OpenAI v1 client, fall back to legacy SDK
            try:
                from openai import OpenAI as _OpenAI
                self.client = _OpenAI(api_key=self.openai_api_key)
                self._openai_v1 = True
            except Exception:
                # Legacy SDK path
                openai.api_key = self.openai_api_key
                self.client = openai
                self._openai_v1 = False

        if self.use_gemini:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        elif self.client is not None:
            # OpenAI only
            pass
        else:
            raise ValueError("No API key found. Please set GEMINI_API_KEY or OPENAI_API_KEY in .env file")
        
        # Memory management
        self.temp_memory = []  # Last 20 interactions
        self.persistent_memory = self._load_persistent_memory()
        
        # System context
        self.system_info = self._gather_system_info()
        
        # Thinking state
        self.thinking_steps = []
        
    def _gather_system_info(self) -> Dict[str, Any]:
        """Gather system information for better command generation"""
        info = {
            'os': platform.system(),
            'os_version': platform.version(),
            'machine': platform.machine(),
            'python_version': platform.python_version(),
            'cwd': os.getcwd(),
            'home': str(Path.home()),
            'shell': os.environ.get('SHELL', 'unknown'),
            'user': os.environ.get('USER', os.environ.get('USERNAME', 'unknown')),
            'path_separator': os.sep,
        }
        
        # Check for common tools
        tools = {}
        for tool in ['git', 'node', 'npm', 'docker', 'gcc', 'make', 'pip', 'conda','jupyter']:
            tools[tool] = self._check_command_exists(tool)
        info['available_tools'] = tools
        
        return info
    
    def _check_command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            import subprocess
            result = subprocess.run(['which', command], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _load_persistent_memory(self) -> Dict[str, Any]:
        """Load persistent memory (list of sentences) from file"""
        memory_file = Path.home() / '.nlshell_memory.json'
        try:
            if memory_file.exists():
                with open(memory_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        return []  
    
    def save_persistent_memory(self, sentence: str):
        """Append a sentence to persistent memory"""

        self.persistent_memory.append(sentence)
        memory_file = Path.home() / '.nlshell_memory.json'
        try:
            with open(memory_file, 'w') as f:
                json.dump(self.persistent_memory, f, indent=2)
        except Exception as e:
            print(f"Error saving memory: {e}")

  
    def _build_context_prompt(self, current_dir: str, history: List[Dict]) -> str:
        """Build context prompt with system info, memory, and history"""
        context = f"""You are an AI assistant helping with a natural language shell interface.

SYSTEM INFO:
- OS: {self.system_info['os']} {self.system_info['os_version']}
- Current Directory: {current_dir}
- User: {self.system_info['user']}
- Shell: {self.system_info['shell']}
- Available Tools: {', '.join([tool for tool, available in self.system_info['available_tools'].items() if available])}

PERSISTENT MEMORY:
{json.dumps(self.persistent_memory, indent=2) if self.persistent_memory else "No persistent memory stored"}

RECENT HISTORY (last {len(history)} commands):
"""
        for i, item in enumerate(history[-10:], 1):  # Show last 10 for context
            context += f"{i}. Input: '{item.get('input', 'N/A')}'\n"
            context += f"   Commands: {item.get('commands', [])}\n"
            context += f"   Success: {item.get('success', False)}\n\n"
        
        return context

    def _requires_thinking(self, user_input: str) -> bool:
        """Determine if the request requires thinking/exploration"""
        thinking_indicators = [
            # File operations with ambiguous references
            "this file", "that file", "the file", "these files", "those files",
            "the folder", "this folder", "that folder", "this directory",
            
            # Analysis requests
            "what is in", "what's in", "show me", "tell me about", "analyze",
            "summarize", "summary of", "what does", "how big", "how many",
            
            # Ambiguous file references
            "matrix file", "config file", "log file", "data file", "script file",
            "python file", "text file", "json file", "csv file",
            
            # Delete/modify with ambiguous references
            "delete this", "remove this", "delete the", "remove the",
            "edit this", "modify this", "change this",
            
            # Search and exploration
            "find", "search for", "look for", "where is", "which file",
            
            # Comparative operations
            "largest file", "smallest file", "newest file", "oldest file",
            "most recent", "latest", "biggest", "smallest",
            
            # Status and inspection
            "what's taking up space", "disk usage", "memory usage",
            "running processes", "active connections", "system status"
        ]
        
        user_lower = user_input.lower()
        return any(indicator in user_lower for indicator in thinking_indicators)

    async def _execute_thinking_command(self, command: str, current_dir: str) -> Tuple[int, str, str]:
        """Execute a command during thinking phase"""
        try:
            if command.strip().startswith('cd '):
                # Don't change directory during thinking
                return 1, "", "Cannot change directory during thinking phase"
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=current_dir
            )
            
            stdout, stderr = await process.communicate()
            return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')
            
        except Exception as e:
            return 1, "", str(e)

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API"""
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text
        except Exception as e:
            if self.openai_api_key:
                # Fallback to OpenAI
                return await self._call_openai(prompt)
            else:
                raise Exception(f"Gemini API error: {e}")
    
    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            if self.client is None:
                if not self.openai_api_key:
                    raise RuntimeError("OpenAI API key not configured")
                # Try to (re)initialize client
                try:
                    from openai import OpenAI as _OpenAI
                    self.client = _OpenAI(api_key=self.openai_api_key)
                    self._openai_v1 = True
                except Exception:
                    openai.api_key = self.openai_api_key
                    self.client = openai
                    self._openai_v1 = False

            if self._openai_v1:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
            else:
                # Legacy SDK (<1.0.0)
                response = await asyncio.to_thread(
                    self.client.ChatCompletion.create,
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                # Legacy shape: choices[0].message["content"]
                return response.choices[0].message["content"]
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")
    
    async def _call_ai(self, prompt: str) -> str:
        """Call the appropriate AI API"""
        if self.use_gemini:
            return await self._call_gemini(prompt)
        else:
            return await self._call_openai(prompt)
    
    def _parse_ai_response(self, response: str) -> AIResponse:
        """Parse AI response and extract commands"""
        try:
            # Look for JSON in response
            if '```json' in response:
                json_start = response.find('```json') + 7
                json_end = response.find('```', json_start)
                json_str = response[json_start:json_end].strip()
                data = json.loads(json_str)
                
                return AIResponse(
                    message=data.get('message', ''),
                    suggested_commands=data.get('commands', []),
                    needs_clarification=data.get('needs_clarification', False),
                    confidence=data.get('confidence', 1.0),
                    thinking_mode=data.get('thinking_mode', False),
                    exploration_commands=data.get('exploration_commands', [])
                )
            else:
                # Try to parse as direct JSON
                try:
                    data = json.loads(response)
                    return AIResponse(
                        message=data.get('message', ''),
                        suggested_commands=data.get('commands', []),
                        needs_clarification=data.get('needs_clarification', False),
                        confidence=data.get('confidence', 1.0),
                        thinking_mode=data.get('thinking_mode', False),
                        exploration_commands=data.get('exploration_commands', [])
                    )
                except:
                    # Fallback: treat as plain message
                    return AIResponse(
                        message=response,
                        suggested_commands=[],
                        needs_clarification=False,
                        confidence=1.0,
                        thinking_mode=False,
                        exploration_commands=[]
                    )
        except Exception:
            return AIResponse(
                message="Sorry, I couldn't parse that response properly.",
                suggested_commands=[],
                needs_clarification=False,
                confidence=1.0,
                thinking_mode=False,
                exploration_commands=[]
            )

    async def _think_and_explore(self, user_input: str, current_dir: str, history: List[Dict]) -> AIResponse:
        """Enter thinking mode to explore and gather information"""
        self.thinking_steps = []
        
        # Initial thinking prompt
        context = self._build_context_prompt(current_dir, history)
        
        think_prompt = f"""{context}

THINKING MODE ACTIVATED: The user's request requires exploration to understand the context fully.

USER REQUEST: "{user_input}"

You need to think step by step and explore the current directory/system to understand what the user is referring to.

First, generate exploration commands to gather information. Return your response in JSON format:

```json
{{
    "message": "I need to explore to understand what you're referring to. Let me check...",
    "exploration_commands": ["ls -la", "pwd", "find . -name '*.txt' | head -10"],
    "thinking_mode": true,
    "confidence": 0.8
}}
```

Common exploration patterns:
- For "this file" → ls -la, find commands to see what files exist
- For "matrix file" → find . -name "*matrix*" -type f
- For "delete this" → ls -la to see current files
- For "what's in this file" → ls -la first, then cat/head the likely file
- For "largest file" → ls -lah, du -sh *, find commands
- For analysis → gather info first, then analyze

Generate exploration commands now:"""

        try:
            response = await self._call_ai(think_prompt)
            ai_response = self._parse_ai_response(response)
            
            if ai_response.exploration_commands:
                # Execute exploration commands
                exploration_results = []
                
                for cmd in ai_response.exploration_commands:
                    returncode, stdout, stderr = await self._execute_thinking_command(cmd, current_dir)
                    
                    exploration_results.append({
                        'command': cmd,
                        'returncode': returncode,
                        'stdout': stdout,
                        'stderr': stderr
                    })
                    
                    # Add to thinking steps
                    self.thinking_steps.append(ThinkingStep(
                        command=cmd,
                        output=stdout if returncode == 0 else stderr,
                        reasoning=f"Exploring to understand user request: {user_input}",
                        next_action="Continue exploration or provide final answer"
                    ))
                
                # Now analyze the results and provide final answer
                return await self._analyze_exploration_results(user_input, current_dir, history, exploration_results)
            
            return ai_response
            
        except Exception as e:
            return AIResponse(
                message=f"AI thinking error: {str(e)}",
                suggested_commands=[],
                needs_clarification=False
            )

    async def _analyze_exploration_results(self, user_input: str, current_dir: str, history: List[Dict], exploration_results: List[Dict]) -> AIResponse:
        """Analyze exploration results and provide final answer"""
        context = self._build_context_prompt(current_dir, history)
        
        # Build exploration summary
        exploration_summary = "EXPLORATION RESULTS:\n"
        for result in exploration_results:
            exploration_summary += f"Command: {result['command']}\n"
            if result['returncode'] == 0:
                exploration_summary += f"Output:\n{result['stdout']}\n"
            else:
                exploration_summary += f"Error: {result['stderr']}\n"
            exploration_summary += "-" * 40 + "\n"
        
        analysis_prompt = f"""{context}

{exploration_summary}

ORIGINAL USER REQUEST: "{user_input}"

Based on the exploration results above, now provide the final response. You should:

1. If the user wanted information (e.g., "what is in this file"), provide a summary/analysis
2. If the user wanted to perform an action (e.g., "delete matrix file"), provide the specific commands
3. Be specific about which files/directories you're referring to based on the exploration

Return response in JSON format:

```json
{{
    "message": "Based on my exploration, here's what I found... [provide summary or explanation]",
    "commands": ["specific_command1", "specific_command2"],
    "thinking_mode": false,
    "confidence": 0.9
}}
```

Examples:
- If exploring found "matrix.py" and user said "delete matrix file" → commands: ["rm matrix.py"]
- If user said "what's in this file" and found "data.txt" → analyze data.txt content and provide summary
- If multiple files match, ask for clarification

Provide your final analysis now:"""

        try:
            response = await self._call_ai(analysis_prompt)
            return self._parse_ai_response(response)
        except Exception as e:
            return AIResponse(
                message=f"Error analyzing exploration results: {str(e)}",
                suggested_commands=[],
                needs_clarification=False
            )

    async def process_natural_language(self, user_input: str, current_dir: str, history: List[Dict]) -> AIResponse:
        """Process natural language input and generate shell commands"""
        
        # Check if this requires thinking mode
        if self._requires_thinking(user_input):
            return await self._think_and_explore(user_input, current_dir, history)
        
        # Regular processing for direct commands
        context = self._build_context_prompt(current_dir, history)
        
        prompt = f"""{context}

        TASK: Convert the following natural language request into shell commands.

        USER REQUEST: "{user_input}"

        INSTRUCTIONS:
        1. Generate appropriate shell commands for the user's request
        2. Consider the current directory and system info
        3. Use available tools when appropriate
        4. If the request is ambiguous, ask for clarification
        5. Return response in JSON format:

        ```json
        {{
            "message": "Brief explanation of what you're doing",
            "commands": ["command1", "command2", ...],
            "needs_clarification": false,
            "confidence": 0.95
        }}
        ```

        If you need clarification, set needs_clarification to true and explain what you need to know in the message field.

        Examples:
        - "go to desktop" → ["cd ~/Desktop"]
        - "list files" → ["ls -la"]
        - "compile myfile.c" → ["gcc myfile.c -o myfile"]
        - "install python package requests" → ["pip install requests"]
        - "create new folder called test" → ["mkdir test"]

        Generate commands now:"""

        try:
            response = await self._call_ai(prompt)
            return self._parse_ai_response(response)
        except Exception as e:
            return AIResponse(
                message=f"AI error: {str(e)}",
                suggested_commands=[],
                needs_clarification=False
            )
    
    async def process_with_clarification(self, original_input: str, clarification: str, current_dir: str, history: List[Dict]) -> AIResponse:
        """Process natural language with additional clarification"""
        context = self._build_context_prompt(current_dir, history)
        
        prompt = f"""{context}

TASK: Convert natural language request into shell commands with clarification.

ORIGINAL REQUEST: "{original_input}"
USER CLARIFICATION: "{clarification}"

Now generate the appropriate commands in JSON format:

```json
{{
    "message": "Brief explanation",
    "commands": ["command1", "command2", ...],
    "needs_clarification": false,
    "confidence": 0.95
}}
```

Generate commands now:"""

        try:
            response = await self._call_ai(prompt)
            return self._parse_ai_response(response)
        except Exception as e:
            return AIResponse(
                message=f"AI error: {str(e)}",
                suggested_commands=[],
                needs_clarification=False
            )
    
    async def analyze_error(self, failed_command: str, returncode: int, stdout: str, stderr: str, history: List[Dict]) -> AIResponse:
        """Analyze command error and suggest fixes"""
        context = self._build_context_prompt(os.getcwd(), history)
        
        prompt = f"""{context}

TASK: Analyze a failed command and suggest a fix.

FAILED COMMAND: "{failed_command}"
EXIT CODE: {returncode}
STDOUT: "{stdout}"
STDERR: "{stderr}"

INSTRUCTIONS:
1. Analyze why the command failed
2. Suggest a fix or alternative approach
3. If you need more information to provide a good fix, ask for clarification
4. Return response in JSON format:

```json
{{
    "message": "Analysis and explanation of the error",
    "commands": ["fixed_command1", "fixed_command2", ...],
    "needs_clarification": false,
    "confidence": 0.85
}}
```

Common error patterns:
- File not found → check path, suggest alternatives
- Permission denied → suggest using sudo or changing permissions
- Command not found → suggest installing the tool
- Compilation errors → suggest fixing syntax or dependencies

Analyze the error and provide a fix:"""

        try:
            response = await self._call_ai(prompt)
            return self._parse_ai_response(response)
        except Exception as e:
            return AIResponse(
                message=f"AI error during error analysis: {str(e)}",
                suggested_commands=[],
                needs_clarification=False
            )
    
    async def analyze_error_with_clarification(self, failed_command: str, returncode: int, stdout: str, stderr: str, history: List[Dict], clarification: str) -> AIResponse:
        """Analyze error with user clarification"""
        context = self._build_context_prompt(os.getcwd(), history)
        
        prompt = f"""{context}

TASK: Analyze failed command with additional clarification.

FAILED COMMAND: "{failed_command}"
EXIT CODE: {returncode}
STDOUT: "{stdout}"
STDERR: "{stderr}"
USER CLARIFICATION: "{clarification}"

Now provide a fix in JSON format:

```json
{{
    "message": "Analysis with fix explanation",
    "commands": ["fixed_command1", "fixed_command2", ...],
    "needs_clarification": false,
    "confidence": 0.90
}}
```

Generate fix now:"""

        try:
            response = await self._call_ai(prompt)
            return self._parse_ai_response(response)
        except Exception as e:
            return AIResponse(
                message=f"AI error: {str(e)}",
                suggested_commands=[],
                needs_clarification=False
            )
    
    async def answer_question(self, question: str, history: List[Dict]) -> str:
        """Answer general questions (not command generation)"""
        context = self._build_context_prompt(os.getcwd(), history)
        
        prompt = f"""{context}

TASK: Answer the user's general question (not a command generation request).

USER QUESTION: "{question}"

INSTRUCTIONS:
1. Provide a helpful, informative answer
2. Use your knowledge and the context provided
3. If it's related to system administration or development, provide practical advice
4. Keep the answer concise but thorough
5. Use markdown formatting for better readability

Answer the question now:"""

        try:
            response = await self._call_ai(prompt)
            return response
        except Exception as e:
            return f"AI error: {str(e)}"
    
    def add_to_temp_memory(self, interaction: Dict[str, Any]):
        """Add interaction to temporary memory"""
        self.temp_memory.append(interaction)
        # Keep only last 20 interactions
        if len(self.temp_memory) > 20:
            self.temp_memory = self.temp_memory[-20:]
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary of current memory state"""
        return {
            'persistent_memory': self.persistent_memory,
            'temp_memory_count': len(self.temp_memory),
            'system_info': self.system_info,
            'using_gemini': self.use_gemini,
            'thinking_steps_count': len(self.thinking_steps)
        }
    
    def get_thinking_steps(self) -> List[ThinkingStep]:
        """Get the current thinking steps"""
        return self.thinking_steps

    