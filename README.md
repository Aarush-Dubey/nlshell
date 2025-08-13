# 🤖 Natural Language Shell (NLShell)

An intelligent command-line interface that understands natural language and converts it into shell commands using AI. Features automatic command execution, file analysis, thinking capability, and persistent memory.

## ✨ Features

### 🧠 AI-Powered Command Generation
- Convert natural language requests into shell commands
- Support for both Gemini and OpenAI APIs
- Intelligent thinking mode for complex queries
- Context-aware command suggestions

### 🤖 AI Agent Mode
- Automatic execution of safe commands with `-a` suffix
- Built-in safety rules for secure automation
- Real-time command interpretation and analysis
- File analysis and content inspection

### 🔍 Smart File Analysis
- Automatic file type detection and analysis
- Support for multiple formats: PDF, DOCX, CSV, JSON, images, etc.
- Content preview and metadata extraction
- Intelligent file content interpretation

### 💾 Persistent Memory
- Save important information across sessions
- Context-aware command generation based on history
- Session memory for recent interactions

### 🛡️ Safety Features
- Whitelist of safe auto-executable commands
- Protection against dangerous operations
- User confirmation for potentially risky commands
- Interactive command support with real-time I/O

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- API key for either Google Gemini or OpenAI

### Dependencies
```bash
pip install google-generativeai openai python-dotenv rich PyPDF2 python-docx pillow pandas openpyxl
```

### Setup
1. Clone or download the project files:
   - `nlshell.py` - Main shell interface
   - `ai_core.py` - AI processing engine
   - `ai_agent.py` - Autonomous agent functionality

2. Create a `.env` file in the project directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

3. Run the shell:
```bash
python nlshell.py
```

## 📖 Usage

### Command Types

#### 1. Natural Language Commands
Simply type what you want to do in plain English:
```
create a new folder called projects
list all python files in this directory
find the largest files in my home directory
show me the contents of config.json
delete all .tmp files
```

#### 2. Direct Shell Commands
Use `!` prefix or suffix for direct shell execution:
```
!ls -la
pwd!
! git status
```

#### 3. AI Questions
Use `-q` suffix to ask general questions:
```
how do I compile a C program -q
what is the difference between grep and awk -q
explain git branching -q
```

#### 4. AI Agent Mode
Use `-a` suffix for automatic command execution:
```
show me disk usage -a
find all large files -a
list running processes -a
```

#### 5. File Analysis
Natural language file inspection:
```
what's in this file data.csv
analyze file report.pdf
read file config.json
what is matrix.txt
```

### Special Commands

#### Memory Management
```bash
save_mem "Remember that the project database is in /opt/myapp/db"
show memory
mem
```

#### Thinking Process
```bash
show_thinking  # Display AI's reasoning steps
```

#### Exit
```bash
exit
quit
bye
```

## 🧠 AI Thinking Mode

The shell automatically enters "thinking mode" for complex or ambiguous requests:

### Triggers for Thinking Mode
- Ambiguous file references: "this file", "the config file"
- Analysis requests: "what's in", "show me", "analyze"
- Comparative operations: "largest file", "newest file"
- System inspection: "what's taking up space", "disk usage"

### How It Works
1. **Exploration Phase**: AI generates safe commands to gather information
2. **Analysis Phase**: AI interprets the collected data
3. **Response Phase**: AI provides specific answers or commands

Example:
```
User: "delete the matrix file"
AI: 🧠 I need to explore to understand what you're referring to. Let me check...

Exploring:
• ls -la
• find . -name "*matrix*" -type f

Analysis: Found matrix.py and matrix_data.txt. Which file would you like to delete?
```

## 🛡️ Safety Features

### Automatic Execution Whitelist
These commands are safe to run automatically:
- File listing: `ls`, `find`
- File inspection: `cat`, `head`, `tail`, `file`
- System info: `pwd`, `whoami`, `uname`, `ps`, `df`, `du`
- Text searching: `grep` (with safe flags)

### Restricted Operations
These require user confirmation:
- File deletion: `rm`
- System modifications: `sudo`, `chmod`, `chown`
- Network operations: `curl | bash`, `wget | bash`
- System control: `shutdown`, `reboot`

### Interactive Program Support
Automatic detection and proper handling of:
- Custom executables (`./myprogram`)
- Interactive interpreters (`python -i`, `node`)
- Compiled programs
- Real-time input/output with proper terminal control

## 🗂️ File Type Support

### Text Files
- Plain text, logs, configuration files
- Line count, character count, content preview

### Structured Data
- **JSON**: Structure analysis, key extraction, formatted preview
- **CSV**: Row/column count, column names, data type detection
- **Excel**: Sheet analysis with pandas integration

### Documents
- **PDF**: Page count, text extraction (requires PyPDF2)
- **DOCX**: Paragraph count, text extraction (requires python-docx)

### Media Files
- **Images**: Dimensions, format, file size (requires Pillow)
- **Video/Audio**: Basic metadata, file size

## 🔧 Configuration

### API Preferences
The shell prioritizes Gemini API but falls back to OpenAI if:
- Gemini API key is not provided
- Gemini API encounters errors

### Memory Storage
- Persistent memory is stored in `~/.nlshell_memory.json`
- Temporary session memory keeps the last 20 interactions
- History includes commands, success status, and timestamps

### Customization
You can modify safety rules in `ai_agent.py`:
```python
SafetyRule(r'^your_pattern', True, "Description", True)
```

## 🎨 Interface Features

### Rich Terminal UI
- Color-coded output with syntax highlighting
- Progress spinners for AI processing
- Organized panels for different content types
- Markdown rendering for AI responses

### Dynamic Prompt
- Shows current environment (conda, venv)
- Displays current directory with smart truncation
- Visual indicators for different modes

### Error Handling
- AI-powered error analysis and fix suggestions
- Graceful handling of interrupted commands
- Comprehensive error messages with context

## 🔍 Examples

### System Administration
```bash
# Find large files
show me the 10 largest files in this directory -a

# Check disk usage
what's taking up space on my system -a

# Process monitoring
show me running python processes -a

# Clean up
delete all .log files older than 7 days
```

### Development Tasks
```bash
# Project setup
create a new python project structure

# Code analysis
find all TODO comments in python files

# Git operations
commit all changes with message "bug fixes"

# Build tasks
compile all C files in src directory
```

### File Management
```bash
# Organization
move all images to Pictures folder

# Analysis
what's in this CSV file
analyze file data.json

# Backup
create a backup of important files
```

## 🤝 Contributing

To extend functionality:

1. **Add new file handlers** in `ai_agent.py`:
   ```python
   async def _handle_new_format(self, filepath: str) -> Dict[str, Any]:
       # Your implementation
   ```

2. **Extend safety rules** for new command patterns
3. **Improve AI prompts** for better command generation
4. **Add new thinking triggers** for complex scenarios

## 📋 Requirements

### System Requirements
- Linux, macOS, or Windows with WSL
- Python 3.8+
- Terminal with color support

### API Requirements
- Google Gemini API key (recommended) OR
- OpenAI API key (fallback)

### Optional Dependencies
For full functionality:
- PyPDF2 for PDF analysis
- python-docx for Word documents
- Pillow for image analysis
- pandas for advanced CSV/Excel handling

## 🐛 Troubleshooting

### Common Issues

**API Key Errors**
```bash
# Check your .env file
cat .env

# Verify API key format
echo $GEMINI_API_KEY
```

**Permission Errors**
```bash
# The shell will ask for confirmation on risky operations
# Use direct commands (!) to bypass AI interpretation
!sudo your_command
```

**Interactive Programs Not Working**
```bash
# Ensure your terminal supports PTY
# Try using direct command execution
!./your_interactive_program
```

**Memory Issues**
```bash
# Clear persistent memory if needed
rm ~/.nlshell_memory.json
```

## 📜 License

This project is open source. Please ensure you comply with the terms of service for the AI APIs you use (Google Gemini, OpenAI).

## 🙏 Acknowledgments

- Built with Google Gemini and OpenAI APIs
- Rich library for beautiful terminal output
- Python ecosystem for file processing capabilities

---

**Happy shell commanding! 🚀**
