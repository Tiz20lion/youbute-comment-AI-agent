#!/usr/bin/env python3
"""
🤖 YouTube Comment AI Agent - Enhanced Cross-Platform Startup Script 🤖
Developed by Tiz Lion
GitHub: https://github.com/Tiz20lion/youtube-comment-AI-agent

This script handles:
- Cross-platform Python virtual environment setup (Windows, macOS, Linux)
- Robust dependency installation with retry mechanisms
- Enhanced color support with fallbacks
- Branded loading animations
- OAuth2 authentication setup
- Main application launch (FastAPI with integrated Telegram service)
- Process management to prevent multiple instances

Supports: Windows 7+, macOS 10.12+, Linux (any modern distro)
Python: 3.8+

Note: Rich library imports are handled dynamically with fallbacks for environments
where the library may not be available during linting/type checking.
"""

# pyright: reportMissingImports=false
# pylint: disable=import-error

import os
import sys
import subprocess
import time
import platform
import importlib.util
import signal
from pathlib import Path
from typing import Optional, Any, Dict, Union

# Import psutil with fallback
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None

# Import configuration to sync with .env values
try:
    from app.config import settings, reload_settings
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    settings = None
    reload_settings = None

# Cross-platform compatibility detection
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

def check_package_installed(package_name):
    """Check if a package is installed and importable."""
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is not None:
            __import__(package_name)
            return True
    except (ImportError, ModuleNotFoundError):
        pass
    return False

def run_fix_colors_if_needed():
    """Run fix_colors.py if it exists and libraries need fixing."""
    fix_colors_path = Path(__file__).parent / "fix_colors.py"
    
    if fix_colors_path.exists():
        # Check if we need to run the color fix
        colorama_ok = check_package_installed('colorama')
        rich_ok = check_package_installed('rich')
        
        if not colorama_ok or not rich_ok:
            print("🔧 Detected fix_colors.py - running automatic color fix...")
            try:
                result = subprocess.run([sys.executable, str(fix_colors_path)], 
                                      capture_output=True, text=True, timeout=120)
                
                if result.returncode == 0:
                    print("✅ Color fix completed successfully!")
                    return True
                else:
                    print("⚠️ Color fix had some issues, but continuing...")
                    
            except Exception as e:
                print(f"⚠️ Could not run fix_colors.py: {e}")
    
    return False

def ensure_pip_available():
    """Ensure pip is available with comprehensive error handling."""
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
    except Exception:
        pass
    
    print("⚠️ pip not found. Installing pip...")
    try:
        import ensurepip
        ensurepip.bootstrap(upgrade=True, default_pip=True)
        print("✅ pip installed successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to install pip: {e}")
        print("🔧 Please install pip manually and try again")
        return False

def install_package_robust(package_name, max_retries=3):
    """Install a package with retry mechanism and cross-platform support."""
    simple_name = package_name.split('>=')[0].split('==')[0]
    
    # Check if already installed
    if check_package_installed(simple_name):
        print(f"✅ {simple_name} already available")
        return True
    
    for attempt in range(max_retries):
        try:
            print(f"📦 Installing {package_name}... (attempt {attempt + 1}/{max_retries})")
            
            cmd = [sys.executable, '-m', 'pip', 'install', package_name]
            
            # Platform-specific flags
            if IS_WINDOWS:
                cmd.extend(['--no-warn-script-location'])
            
            # Progressive installation strategies
            if attempt == 0:
                cmd.extend(['--quiet'])
            elif attempt == 1:
                cmd.extend(['--upgrade', '--no-cache-dir'])
            else:
                cmd.extend(['--force-reinstall'])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            if result.returncode == 0:
                # Verify installation
                time.sleep(1)
                if check_package_installed(simple_name):
                    print(f"✅ {simple_name} installed successfully!")
                    return True
            else:
                print(f"⚠️ Attempt {attempt + 1} failed")
                
        except Exception as e:
            print(f"⚠️ Installation error: {str(e)[:50]}...")
        
        if attempt < max_retries - 1:
            time.sleep(2)
    
    print(f"❌ Failed to install {package_name}")
    return False

def kill_existing_python_processes():
    """Kill existing Python processes to prevent multiple bot instances."""
    if not HAS_PSUTIL:
        print("⚠️ psutil not available - skipping process cleanup")
        return
        
    try:
        current_pid = os.getpid()
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    # Don't kill the current process
                    if proc.info['pid'] != current_pid:
                        # Check if it's running our app
                        cmdline = proc.info['cmdline'] or []
                        if any('main.py' in arg or 'uvicorn' in arg or 'telegram_bot.py' in arg for arg in cmdline):
                            proc.terminate()
                            killed_count += 1
                            print(f"🔄 Terminated existing bot process (PID: {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if killed_count > 0:
            print(f"✅ Cleaned up {killed_count} existing bot processes")
            time.sleep(2)  # Give processes time to terminate
        else:
            print("✅ No existing bot processes found")
            
    except Exception as e:
        print(f"⚠️ Could not check for existing processes: {e}")

def install_essential_deps():
    """Install essential dependencies with robust error handling."""
    print("🚀 Preparing Tiz Lion AI Agent...")
    print(f"🖥️ Platform: {platform.system()} {platform.release()}")
    print(f"🐍 Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Ensure pip is available
    if not ensure_pip_available():
        return False
    
    # Essential libraries (including psutil for process management)
    essential_libs = ['colorama>=0.4.4', 'rich>=13.0.0', 'psutil>=5.8.0']
    
    success_count = 0
    for lib in essential_libs:
        if install_package_robust(lib):
            success_count += 1
    
    print(f"📚 Installation complete: {success_count}/{len(essential_libs)} packages")
    return success_count > 0

# Add this BEFORE the current install_essential_deps() call:
print("🦁 Tiz Lion AI Agent - Enhanced Startup")
print("=" * 50)

# Clean up any existing bot processes to prevent conflicts
print("🔍 Checking for existing bot processes...")
kill_existing_python_processes()

# First, try to run fix_colors.py if needed and available
fix_colors_run = run_fix_colors_if_needed()

# Then run the existing installation logic...
# Install essential dependencies first
if not install_essential_deps():
    print("❌ Critical dependency installation failed!")
    print("🔧 Please install manually: pip install colorama rich psutil")
    input("Press Enter to continue anyway...")

# Import libraries with comprehensive fallback handling
try:
    from colorama import init, Fore, Back, Style
    
    # Platform-specific colorama initialization
    if IS_WINDOWS:
        # Windows needs ANSI conversion
        init(autoreset=True, convert=True, strip=False)
        
        # Enhanced Windows terminal support
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass  # Fallback to colorama conversion
    else:
        # Linux/macOS - disable conversion to prevent colorama conflicts
        init(autoreset=True, convert=False, strip=False)
    
    print(f"{Fore.GREEN}✅ Colorama initialized with full color support{Style.RESET_ALL}")
    HAS_COLORAMA = True
    
except ImportError as e:
    print(f"⚠️ Colorama import failed: {e}")
    
    # Fallback color implementation
    class ColorFallback:
        def __getattr__(self, name):
            return ""
    
    Fore = Back = Style = ColorFallback()
    
    def init(**kwargs):
        pass
    
    HAS_COLORAMA = False
    print("⚠️ Running without color support")

# Try to import Rich components individually with better error handling
HAS_RICH: bool = False
console: Optional[Any] = None
Panel: Optional[Any] = None
Table: Optional[Any] = None
Progress: Optional[Any] = None
SpinnerColumn: Optional[Any] = None
TextColumn: Optional[Any] = None

def try_rich_imports() -> bool:
    """Try to import Rich library components with graceful fallback."""
    global HAS_RICH, console, Panel, Table, Progress, SpinnerColumn, TextColumn
    
    try:
        # Import Rich components
        from rich.console import Console
        from rich.panel import Panel as RichPanel
        from rich.progress import Progress as RichProgress, SpinnerColumn, TextColumn
        from rich.table import Table as RichTable
        
        # Create console with enhanced settings for Linux compatibility
        console = Console(
            force_terminal=True,
            color_system="auto",
            width=None,
            legacy_windows=IS_WINDOWS,
            # Disable features that might conflict with colorama on Linux
            force_interactive=False if IS_LINUX else None
        )
        
        # Set global references
        Panel = RichPanel
        Table = RichTable
        Progress = RichProgress
        
        print(f"{Fore.GREEN}✅ Rich library initialized with enhanced formatting{Style.RESET_ALL}")
        HAS_RICH = True
        return True
        
    except ImportError as e:
        print(f"⚠️ Rich import failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Rich initialization failed: {e}")
        print("🔄 Falling back to basic console...")
        return False

# Try to initialize Rich
if not try_rich_imports():
    
    # Enhanced fallback implementation
    class FallbackConsole:
        def __init__(self):
            try:
                import shutil
                self.width = shutil.get_terminal_size().columns
            except Exception:
                self.width = 80
        
        def print(self, text, style=None, **kwargs):
            import re
            clean_text = re.sub(r'\[/?[^\]]*\]', '', str(text))
            
            # Apply basic color if available
            if HAS_COLORAMA and style:
                if 'red' in style.lower():
                    clean_text = f"{Fore.RED}{clean_text}{Style.RESET_ALL}"
                elif 'green' in style.lower():
                    clean_text = f"{Fore.GREEN}{clean_text}{Style.RESET_ALL}"
                elif 'yellow' in style.lower():
                    clean_text = f"{Fore.YELLOW}{clean_text}{Style.RESET_ALL}"
                elif 'cyan' in style.lower():
                    clean_text = f"{Fore.CYAN}{clean_text}{Style.RESET_ALL}"
                elif 'bold' in style.lower():
                    clean_text = f"{Style.BRIGHT}{clean_text}{Style.RESET_ALL}"
            
            print(clean_text)
        
        def input(self, prompt):
            import re
            clean_prompt = re.sub(r'\[/?[^\]]*\]', '', str(prompt))
            if HAS_COLORAMA:
                clean_prompt = f"{Fore.CYAN}{clean_prompt}{Style.RESET_ALL}"
            return input(clean_prompt)
    
    class FallbackPanel:
        @staticmethod
        def fit(text, title="", border_style="", **kwargs):
            import re
            clean_text = re.sub(r'\[/?[^\]]*\]', '', str(text))
            clean_title = re.sub(r'\[/?[^\]]*\]', '', str(title))
            
            width = 76
            border = "═" * width
            
            lines = [f"╔{border}╗"]
            if clean_title:
                lines.append(f"║ {clean_title:<{width-2}} ║")
                lines.append(f"╠{border}╣")
            
            for line in clean_text.split('\n'):
                if line.strip():
                    lines.append(f"║ {line:<{width-2}} ║")
            
            lines.append(f"╚{border}╝")
            
            result = '\n'.join(lines)
            if HAS_COLORAMA and 'cyan' in border_style.lower():
                result = f"{Fore.CYAN}{result}{Style.RESET_ALL}"
            
            return result
    
    class FallbackTable:
        def __init__(self, title="", **kwargs):
            self.title = title
            self.columns = []
            self.rows = []
        
        def add_column(self, name, style="", width=None, **kwargs):
            self.columns.append(name)
        
        def add_row(self, *args, **kwargs):
            self.rows.append([str(arg) for arg in args])
        
        def __str__(self):
            if not self.columns:
                return ""
            
            # Calculate column widths
            widths = [len(col) for col in self.columns]
            for row in self.rows:
                for i, cell in enumerate(row):
                    if i < len(widths):
                        widths[i] = max(widths[i], len(str(cell)))
            
            # Build table
            result = []
            if self.title:
                result.append(f"\n{self.title}")
                result.append("=" * sum(widths) + "=" * (len(widths) * 3 - 1))
            
            # Header
            header = " | ".join(col.ljust(widths[i]) for i, col in enumerate(self.columns))
            result.append(header)
            result.append("-" * len(header))
            
            # Rows
            for row in self.rows:
                row_str = " | ".join(str(cell).ljust(widths[i]) if i < len(widths) else str(cell) 
                                   for i, cell in enumerate(row))
                result.append(row_str)
            
            return "\n".join(result)
    
    console = FallbackConsole()
    Panel = FallbackPanel
    Table = FallbackTable
    
    # Add fallback Progress components to prevent errors
    class FallbackProgress:
        def __init__(self, *args, **kwargs):
            pass
            
        def __enter__(self):
            return self
            
        def __exit__(self, *args):
            pass
            
        def add_task(self, description, total=None):
            print(f"⏳ {description}")
            return "task_id"
    
    class FallbackSpinnerColumn:
        pass
        
    class FallbackTextColumn:
        pass
    
    Progress = FallbackProgress
    SpinnerColumn = FallbackSpinnerColumn
    TextColumn = FallbackTextColumn
    HAS_RICH = False
    print("⚠️ Running with enhanced fallback UI (includes Progress fallback)")

print(f"{Fore.CYAN}🎨 Display system initialized!{Style.RESET_ALL}")
print(f"   Color Support: {'✅ Yes' if HAS_COLORAMA else '❌ No'}")
print(f"   Rich UI: {'✅ Yes' if HAS_RICH else '🔄 Fallback'}")
print(f"   Platform: {platform.system()} {platform.release()}")
print("=" * 50)


class TizLionAIAgent:
    """Main startup class for YouTube Comment AI Agent by Tiz Lion."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.venv_path = self.project_root / "venv"
        self.requirements_file = self.project_root / "requirements.txt"
        self.oauth_script = self.project_root / "oauth2_setup.py"
        self.env_file = self.project_root / ".env"
        self.example_env_file = self.project_root / "example.env"
        
        # Brand info
        self.brand_name = "Tiz Lion"
        self.github_url = "https://github.com/Tiz20lion/youtube-comment-AI-agent"
        self.project_name = "YouTube Comment AI Agent"
        
        # Available LLM models for selection
        # Organized by categories: Free Tier Models (1-4) and Premium Models (5-9)
        self.available_models = {
            # 🆓 FREE TIER MODELS - Best General-Purpose (No Reasoning Bias)
            "1": {
                "name": "google/gemini-2.0-flash-exp:free", 
                "description": "🚀 Google Gemini 2.0 Flash Experimental (FREE)", 
                "cost": "Free", 
                "context": "1M+", 
                "details": "Fastest with unmatched context size - chat, instruction, summarization"
            },
            "2": {
                "name": "qwen/qwen3-30b-a3b:free", 
                "description": "🧠 Qwen3 30B A3B (FREE MoE)", 
                "cost": "Free", 
                "context": "40K-131K", 
                "details": "Mixture of Experts - multilingual, creative writing, coding"
            },
            "3": {
                "name": "meta-llama/llama-3.3-70b-instruct:free", 
                "description": "🦙 Meta Llama 3.3 70B Instruct (FREE)", 
                "cost": "Free", 
                "context": "131K", 
                "details": "Flagship general-purpose model - natural conversation, instruction-following"
            },
            "4": {
                "name": "moonshotai/kimi-vl-a3b-thinking:free", 
                "description": "🌙 Moonshot Kimi VL A3B (FREE Multimodal)", 
                "cost": "Free", 
                "context": "131K", 
                "details": "Visual + language input support - assistant-style agents"
            },
            
            # 💎 PREMIUM MODELS - Top General-Purpose (Excluding Reasoning Models)
            "5": {
                "name": "google/gemini-2.5-flash-preview-05-20", 
                "description": "👑 Google Gemini 2.5 Flash Preview (PREMIUM)", 
                "cost": "$0.15/$0.60 per 1M", 
                "context": "1M+", 
                "details": "Best context window - fast TTFT, multimodal, cost-efficient"
            },
            "6": {
                "name": "mistralai/mistral-nemo", 
                "description": "💰 Mistral Nemo (CHEAPEST PREMIUM)", 
                "cost": "$0.01/$0.019 per 1M", 
                "context": "131K", 
                "details": "Cheapest premium model - multilingual, function calling"
            },
            "7": {
                "name": "deepseek/deepseek-chat-v3-0324", 
                "description": "🔬 DeepSeek V3 0324 (PREMIUM)", 
                "cost": "$0.30/$0.88 per 1M", 
                "context": "163K", 
                "details": "Latest flagship - chat, legal, finance, science"
            },
            "8": {
                "name": "google/gemini-2.0-flash-001", 
                "description": "⚡ Google Gemini 2.0 Flash (PREMIUM)", 
                "cost": "$0.10/$0.40 per 1M", 
                "context": "1M+", 
                "details": "Ultra-long context - fast response, roleplay, translation, coding"
            },
            "9": {
                "name": "microsoft/wizardlm-2-8x22b", 
                "description": "🧙 WizardLM-2 8x22B (PREMIUM MoE)", 
                "cost": "$0.48/$0.48 per 1M", 
                "context": "65K", 
                "details": "Mixtral MoE - instruction, creative dialogue, multilingual"
            },
            
            # 🚀 EXTENDED PREMIUM MODELS - Additional High-Performance Options
            "10": {
                "name": "gpt-4.1-mini", 
                "description": "🔧 GPT-4.1 Mini (PREMIUM)", 
                "cost": "$0.40/$1.60 per 1M", 
                "context": "1M+", 
                "details": "High context + great coding support - medium-load agentic applications"
            },
            "11": {
                "name": "gpt-4.1-nano", 
                "description": "⚡ GPT-4.1 Nano (PREMIUM FASTEST)", 
                "cost": "$0.10/$0.40 per 1M", 
                "context": "1M+", 
                "details": "Fastest + cheapest OpenAI model - low-latency agents, 80.1% MMLU"
            },
            "12": {
                "name": "anthropic/claude-3.7-sonnet", 
                "description": "🎭 Claude 3.7 Sonnet (PREMIUM)", 
                "cost": "$3.00/$15.00 per 1M", 
                "context": "200K", 
                "details": "Code-based agents, workflows, strong roleplay & chat capabilities"
            },
            "13": {
                "name": "anthropic/claude-sonnet-4", 
                "description": "👑 Claude Sonnet 4 (PREMIUM FLAGSHIP)", 
                "cost": "$3.00/$15.00 per 1M", 
                "context": "200K", 
                "details": "Latest Claude flagship - multimodal support, advanced reasoning"
            }
        }
    
    def ensure_fresh_config(self):
        """Ensure we have the latest config values by reloading if needed."""
        if CONFIG_AVAILABLE and reload_settings:
            global settings
            settings = reload_settings()
        
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_tiz_lion_logo(self):
        """Generate Tiz Lion branded logo with full project information."""
        logo = f"""
{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ████████╗██╗███████╗    ██╗     ██╗ ██████╗ ███╗   ██╗                   ║
║   ╚══██╔══╝██║╚══███╔╝    ██║     ██║██╔═══██╗████╗  ██║                   ║
║      ██║   ██║  ███╔╝     ██║     ██║██║   ██║██╔██╗ ██║                   ║
║      ██║   ██║ ███╔╝      ██║     ██║██║   ██║██║╚██╗██║                   ║
║      ██║   ██║███████╗    ███████╗██║╚██████╔╝██║ ╚████║                   ║
║      ╚═╝   ╚═╝╚══════╝    ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝                   ║
║                                                                              ║
║                    🤖 YouTube Comment AI Agent 🤖                           ║
║                         🚀 AI-Powered Automation 🚀                        ║
║                                                                              ║
║                        👨‍💻 Developed by: Tiz Lion                            ║
║          🔗 GitHub: https://github.com/Tiz20lion/youtube-comment-AI-agent   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        return logo
    
    def show_loading_animation(self, duration=3, message="Loading AI Agent..."):
        """Show animated loading screen with Tiz Lion branding."""
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        colors = [Fore.CYAN, Fore.MAGENTA, Fore.YELLOW, Fore.GREEN, Fore.RED, Fore.BLUE]
        
        start_time = time.time()
        frame_index = 0
        color_index = 0
        
        while time.time() - start_time < duration:
            self.clear_screen()
            
            # Display logo with changing colors
            print(colors[color_index % len(colors)] + Style.BRIGHT + self.show_tiz_lion_logo())
            
            # Animated loading message
            spinner = frames[frame_index % len(frames)]
            loading_text = f"\n{colors[(color_index + 2) % len(colors)]}{Style.BRIGHT}{spinner} {message} {spinner}"
            print(loading_text)
            
            # GitHub link with blinking effect
            if frame_index % 2 == 0:
                github_text = f"\n{Fore.WHITE}{Style.BRIGHT}🔗 Follow development: {self.github_url}"
            else:
                github_text = f"\n{Fore.LIGHTBLACK_EX}🔗 Follow development: {self.github_url}"
            print(github_text)
            
            # Animated progress bar
            progress = min(100, int(((time.time() - start_time) / duration) * 100))
            bar_length = 60
            filled_length = int(bar_length * progress / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            print(f"\n{colors[(color_index + 4) % len(colors)]}{Style.BRIGHT}[{bar}] {progress}%")
            
            # Extended AI-like status messages for 30 seconds
            status_messages = [
                "🧠 Initializing AI models...",
                "🔍 Scanning YouTube APIs...", 
                "📊 Loading analysis engines...",
                "💬 Preparing comment generators...",
                "🤖 Configuring LangGraph workflow...",
                "⚡ Optimizing neural networks...",
                "🎯 Calibrating content analyzers...",
                "🔧 Setting up automation pipelines...",
                "🌐 Connecting to OpenRouter services...",
                "📡 Establishing Telegram connections...",
                "🚀 Finalizing AI deployment..."
            ]
            
            # Calculate status based on progress for longer duration
            status_index = min(len(status_messages) - 1, int(progress / (100 / len(status_messages))))
            status_color = colors[(color_index + 1) % len(colors)]
            print(f"\n{status_color}{Style.DIM}{status_messages[status_index]}")
            
            time.sleep(0.3)
            frame_index += 1
            if frame_index % 20 == 0:  # Change color every 20 frames (slower)
                color_index += 1
    
    def check_python_version(self):
        """Check if Python version is compatible."""
        console.print("\n🐍 Checking Python version...", style="cyan")
        
        if sys.version_info < (3, 8):
            console.print("❌ Python 3.8+ is required for this AI agent!", style="red")
            return False
        
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        console.print(f"✅ Python {version} - Perfect for AI operations!", style="green")
        return True
    
    def check_virtual_environment(self):
        """Check if virtual environment exists, create if not."""
        console.print("\n🏠 Checking virtual environment...", style="cyan")
        
        if self.venv_path.exists():
            console.print("✅ Virtual environment found!", style="green")
            return True
        
        console.print("📦 Creating isolated Python environment...", style="yellow")
        try:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                task = progress.add_task("Creating virtual environment...", total=None)
                subprocess.check_call([sys.executable, '-m', 'venv', str(self.venv_path)], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            console.print("✅ Virtual environment created successfully!", style="green")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to create virtual environment: {e}", style="red")
            return False
    
    def get_venv_python(self):
        """Get the Python executable path for the virtual environment."""
        if platform.system() == "Windows":
            return str(self.venv_path / "Scripts" / "python.exe")
        else:
            return str(self.venv_path / "bin" / "python")
    
    def install_requirements(self):
        """Install required packages from requirements.txt."""
        console.print("\n📚 Checking AI dependencies...", style="cyan")
        
        if not self.requirements_file.exists():
            console.print("❌ requirements.txt not found!", style="red")
            return False
        
        venv_python = self.get_venv_python()
        
        try:
            console.print("🤖 Installing AI libraries and dependencies...", style="yellow")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Installing packages...", total=None)
                
                result = subprocess.run(
                    [venv_python, '-m', 'pip', 'install', '-r', str(self.requirements_file), '--quiet'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    console.print("✅ All AI dependencies installed successfully!", style="green")
                    return True
                else:
                    console.print(f"❌ Failed to install dependencies:\n{result.stderr}", style="red")
                    return False
                    
        except Exception as e:
            console.print(f"❌ Error installing dependencies: {e}", style="red")
            return False
    
    def show_system_info(self):
        """Display system information with Tiz Lion branding."""
        table = Table(title="🤖 Tiz Lion AI Agent - System Information")
        table.add_column("Component", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("💻 Operating System", platform.system())
        table.add_row("🐍 Python Version", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        table.add_row("📁 Project Path", str(self.project_root))
        table.add_row("🏠 Virtual Environment", str(self.venv_path))
        table.add_row("👨‍💻 Developer", self.brand_name)
        table.add_row("🔗 GitHub Repository", self.github_url)
        table.add_row("🤖 AI Agent", "YouTube Comment Automation")
        
        console.print(table)
        
        # Show animated TIZ LION logo after system info
        console.print("\n🎨 Tiz Lion AI Agent - Ready for Action!", style="bold cyan")
        self.show_animated_tiz_lion_logo_inline()
    
    def show_animated_tiz_lion_logo_inline(self, duration=3):
        """Show animated TIZ LION logo inline without clearing the screen."""
        colors = [Fore.CYAN, Fore.MAGENTA, Fore.YELLOW, Fore.GREEN, Fore.RED, Fore.BLUE]
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        
        # Smart loading messages that change during the animation
        loading_messages = [
            "🔍 Analyzing system configuration...",
            "🧠 Loading AI neural networks...",
            "🤖 Initializing automation agents...",
            "📊 Calibrating analysis engines...",
            "💬 Preparing comment generators...",
            "🔗 Establishing API connections...",
            "⚡ Optimizing performance settings...",
            "🚀 System Ready - Tiz Lion AI Agent Initialized!"
        ]
        
        start_time = time.time()
        frame_index = 0
        color_index = 0
        
        # Display the logo once at the beginning
        logo_color = colors[0]
        animated_logo = f"""
{logo_color}{Style.BRIGHT}╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ████████╗██╗███████╗    ██╗     ██╗ ██████╗ ███╗   ██╗                   ║
║   ╚══██╔══╝██║╚══███╔╝    ██║     ██║██╔═══██╗████╗  ██║                   ║
║      ██║   ██║  ███╔╝     ██║     ██║██║   ██║██╔██╗ ██║                   ║
║      ██║   ██║ ███╔╝      ██║     ██║██║   ██║██║╚██╗██║                   ║
║      ██║   ██║███████╗    ███████╗██║╚██████╔╝██║ ╚████║                   ║
║      ╚═╝   ╚═╝╚══════╝    ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝                   ║
║                                                                              ║
║                    🤖 YouTube Comment AI Agent 🤖                           ║
║                         🚀 AI-Powered Automation 🚀                        ║
║                                                                              ║
║                        👨‍💻 Developed by: Tiz Lion                            ║
║          🔗 GitHub: https://github.com/Tiz20lion/youtube-comment-AI-agent   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}"""
        
        print(animated_logo)
        
        # Now show animated loading messages below the logo
        while time.time() - start_time < duration:
            # Calculate current loading message based on progress
            progress = (time.time() - start_time) / duration
            message_index = min(len(loading_messages) - 1, int(progress * len(loading_messages)))
            current_message = loading_messages[message_index]
            
            # Display animated loading message
            spinner = frames[frame_index % len(frames)]
            message_color = colors[color_index % len(colors)]
            
            # Clear only the message line and redraw
            print(f"\r{message_color}{Style.BRIGHT}{spinner} {current_message} {spinner}{Style.RESET_ALL}", end="", flush=True)
            
            time.sleep(0.5)  # Slower, more stable display
            frame_index += 1
            if frame_index % 30 == 0:  # Change color every 30 frames (much slower)
                color_index += 1
        
        # Show final completion message without clearing screen
        console.print("\n✅ Tiz Lion AI Agent - Fully Operational! ✅", style="bold green")
        time.sleep(1)  # Brief pause before continuing
    
    def show_animated_tiz_lion_logo(self, duration=3):
        """Show animated TIZ LION logo with smart loading messages and slow color changes."""
        colors = [Fore.CYAN, Fore.MAGENTA, Fore.YELLOW, Fore.GREEN, Fore.RED, Fore.BLUE]
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        
        # Smart loading messages that change during the animation
        loading_messages = [
            "🔍 Analyzing system configuration...",
            "🧠 Loading AI neural networks...",
            "🤖 Initializing automation agents...",
            "📊 Calibrating analysis engines...",
            "💬 Preparing comment generators...",
            "🔗 Establishing API connections...",
            "⚡ Optimizing performance settings...",
            "🚀 System Ready - Tiz Lion AI Agent Initialized!"
        ]
        
        start_time = time.time()
        frame_index = 0
        color_index = 0
        message_index = 0
        
        while time.time() - start_time < duration:
            # Display stable logo with slowly changing colors
            logo_color = colors[color_index % len(colors)]
            spinner = frames[frame_index % len(frames)]
            
            # Calculate current loading message based on progress
            progress = (time.time() - start_time) / duration
            message_index = min(len(loading_messages) - 1, int(progress * len(loading_messages)))
            current_message = loading_messages[message_index]
            
            # Clear screen and display logo
            self.clear_screen()
            
            animated_logo = f"""
{logo_color}{Style.BRIGHT}╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ████████╗██╗███████╗    ██╗     ██╗ ██████╗ ███╗   ██╗                   ║
║   ╚══██╔══╝██║╚══███╔╝    ██║     ██║██╔═══██╗████╗  ██║                   ║
║      ██║   ██║  ███╔╝     ██║     ██║██║   ██║██╔██╗ ██║                   ║
║      ██║   ██║ ███╔╝      ██║     ██║██║   ██║██║╚██╗██║                   ║
║      ██║   ██║███████╗    ███████╗██║╚██████╔╝██║ ╚████║                   ║
║      ╚═╝   ╚═╝╚══════╝    ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝                   ║
║                                                                              ║
║                    🤖 YouTube Comment AI Agent 🤖                           ║
║                         🚀 AI-Powered Automation 🚀                        ║
║                                                                              ║
║                        👨‍💻 Developed by: Tiz Lion                            ║
║          🔗 GitHub: https://github.com/Tiz20lion/youtube-comment-AI-agent   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}

{colors[(color_index + 2) % len(colors)]}{Style.BRIGHT}{spinner} {current_message} {spinner}{Style.RESET_ALL}
"""
            
            print(animated_logo)
            
            time.sleep(0.5)  # Slower, more stable display
            frame_index += 1
            if frame_index % 30 == 0:  # Change color every 30 frames (much slower)
                color_index += 1
        
        # Show final completion message without clearing screen
        console.print("\n✅ Tiz Lion AI Agent - Fully Operational! ✅", style="bold green")
        time.sleep(1)  # Brief pause before continuing
    
    def load_current_env_settings(self):
        """Load current .env file settings, synchronized with config.py."""
        env_settings = {}
        
        # If config is available, use it as the source of truth
        if CONFIG_AVAILABLE and settings:
            # Map config settings to env format
            env_settings.update({
                "YOUTUBE_API_KEY": settings.YOUTUBE_API_KEY or settings.GOOGLE_API_KEY or "",
                "GOOGLE_API_KEY": settings.GOOGLE_API_KEY or settings.YOUTUBE_API_KEY or "",
                "OPENROUTER_API_KEY": settings.OPENROUTER_API_KEY or "",
                "OPENROUTER_MODEL": settings.OPENROUTER_MODEL,
                "OPENROUTER_TEMPERATURE": str(settings.OPENROUTER_TEMPERATURE),
                "TELEGRAM_BOT_TOKEN": settings.TELEGRAM_BOT_TOKEN or "",
                "TELEGRAM_ALLOWED_USERS": settings.TELEGRAM_ALLOWED_USERS or "",
                "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID or "",
                "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET or "",
                "CHANNEL_PARSER_MAX_VIDEOS": str(settings.CHANNEL_PARSER_MAX_VIDEOS),
                "MAX_COMMENTS_PER_VIDEO": str(settings.MAX_COMMENTS_PER_VIDEO),
                "COMMENT_MAX_LENGTH": str(settings.COMMENT_MAX_LENGTH),
                "COMMENT_MIN_LENGTH": str(settings.COMMENT_MIN_LENGTH),
                "COMMENT_STYLE": settings.COMMENT_STYLE,
                "LANGGRAPH_TIMEOUT": str(settings.LANGGRAPH_TIMEOUT),
                "ANALYSIS_TIMEOUT": str(settings.ANALYSIS_TIMEOUT),
                "SCRAPER_TIMEOUT": str(settings.SCRAPER_TIMEOUT),
                "COMMENT_POST_DELAY": str(settings.COMMENT_POST_DELAY),
                "ENABLE_COMMENT_POSTING": str(settings.ENABLE_COMMENT_POSTING).lower(),
                "CONTENT_ANALYZER_MODEL": settings.CONTENT_ANALYZER_MODEL or settings.OPENROUTER_MODEL,
                "COMMENT_GENERATOR_MODEL": settings.COMMENT_GENERATOR_MODEL or settings.OPENROUTER_MODEL,
                "CONTENT_ANALYZER_TEMPERATURE": str(settings.CONTENT_ANALYZER_TEMPERATURE),
                "COMMENT_GENERATOR_TEMPERATURE": str(settings.COMMENT_GENERATOR_TEMPERATURE),
                "LANGGRAPH_MAX_RETRIES": str(settings.LANGGRAPH_MAX_RETRIES),
                "COMMENT_POST_RETRIES": str(settings.COMMENT_POST_RETRIES),
                "LOG_BACKUP_COUNT": str(settings.LOG_BACKUP_COUNT)
            })
        
        # Also read from .env file for any additional settings
        if self.env_file.exists():
            try:
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Remove quotes if present
                            value = value.strip('"\'')
                            # Only override if not already set from config
                            if key not in env_settings or not env_settings[key]:
                                env_settings[key] = value
            except Exception as e:
                console.print(f"⚠️ Error reading .env file: {e}", style="yellow")
        
        return env_settings
    
    def save_env_settings(self, settings_dict):
        """Save settings to .env file."""
        try:
            # Read the example.env as template
            template_lines = []
            if self.example_env_file.exists():
                with open(self.example_env_file, 'r', encoding='utf-8') as f:
                    template_lines = f.readlines()
            
            # Update template with new values
            updated_lines = []
            for line in template_lines:
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith('#') and '=' in line_stripped:
                    key = line_stripped.split('=', 1)[0]
                    if key in settings_dict:
                        updated_lines.append(f'{key}="{settings_dict[key]}"\n')
                    else:
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)
            
            # Write updated .env file
            with open(self.env_file, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
            
            # Reload config to pick up new values
            if CONFIG_AVAILABLE and reload_settings:
                global settings
                settings = reload_settings()
                console.print("🔄 Configuration reloaded with new values!", style="cyan")
            
            console.print("✅ Settings saved successfully to .env file!", style="green")
            return True
            
        except Exception as e:
            console.print(f"❌ Error saving settings: {e}", style="red")
            return False
    
    def show_settings_menu(self):
        """Show the main settings configuration menu."""
        while True:
            self.clear_screen()
            
            # Always reload config to ensure fresh values
            if CONFIG_AVAILABLE and reload_settings:
                global settings
                settings = reload_settings()
            
            # Check current .env status
            env_exists = self.env_file.exists()
            current_settings = self.load_current_env_settings() if env_exists else {}
            
            # Branded header
            console.print(Panel.fit(
                f"[bold cyan]⚙️ {self.project_name} - Settings Manager ⚙️[/bold cyan]\n\n"
                f"[bold white]Developed by: {self.brand_name}[/bold white]\n"
                f"[blue]GitHub: {self.github_url}[/blue]\n\n"
                f"[yellow]🔧 Configure your AI automation settings[/yellow]",
                title="🦁 Tiz Lion Settings",
                border_style="cyan"
            ))
            
            # Settings status
            status_table = Table(title="📊 Current Configuration Status")
            status_table.add_column("Setting", style="cyan")
            status_table.add_column("Status", style="white")
            status_table.add_column("Value", style="yellow")
            
            # Check key settings
            youtube_api = current_settings.get("YOUTUBE_API_KEY") or current_settings.get("GOOGLE_API_KEY")
            openrouter_api = current_settings.get("OPENROUTER_API_KEY")
            telegram_token = current_settings.get("TELEGRAM_BOT_TOKEN")
            model = current_settings.get("OPENROUTER_MODEL", "Not Set")
            max_videos = current_settings.get("CHANNEL_PARSER_MAX_VIDEOS", "10")
            
            status_table.add_row(
                "🎬 YouTube API", 
                "✅ Configured" if youtube_api else "❌ Missing",
                youtube_api[:20] + "..." if youtube_api else "Not Set"
            )
            status_table.add_row(
                "🤖 OpenRouter API", 
                "✅ Configured" if openrouter_api else "❌ Missing",
                openrouter_api[:20] + "..." if openrouter_api else "Not Set"
            )
            status_table.add_row(
                "📱 Telegram Bot", 
                "✅ Configured" if telegram_token else "❌ Missing",
                telegram_token[:20] + "..." if telegram_token else "Not Set"
            )
            status_table.add_row("🧠 AI Model", "✅ Set", model[:40] + "..." if len(model) > 40 else model)
            status_table.add_row("📹 Max Videos", "✅ Set", max_videos)
            
            console.print(status_table)
            
            # Settings menu options
            console.print("\n🚀 Tiz Lion AI Settings Options:", style="bold cyan")
            choices = Table()
            choices.add_column("Option", style="cyan bold")
            choices.add_column("Description", style="white")
            choices.add_column("Best For", style="yellow")
            
            choices.add_row("1", "🎯 Quick Settings", "Change AI model, video count, basic options")
            choices.add_row("2", "🔧 Full Setup", "Complete .env configuration with all API keys")
            choices.add_row("3", "📋 View Current Settings", "Display all current configuration values")
            choices.add_row("4", "🔄 Reset to Defaults", "Restore default example.env settings")
            choices.add_row("5", "💾 Backup Settings", "Create backup of current .env file")
            choices.add_row("6", "🚀 Continue to Launch", "Use current settings and start AI agent")
            choices.add_row("7", "👋 Exit", "Exit settings manager")
            
            console.print(choices)
            
            try:
                choice = console.input("\n[bold cyan]🎯 Select option (1-7): [/bold cyan]").strip()
                
                if choice == "1":
                    self.quick_settings_menu(current_settings)
                elif choice == "2":
                    self.full_setup_menu(current_settings)
                elif choice == "3":
                    self.view_current_settings(current_settings)
                elif choice == "4":
                    self.reset_to_defaults()
                elif choice == "5":
                    self.backup_settings()
                elif choice == "6":
                    return "continue"
                elif choice == "7":
                    return "exit"
                else:
                    console.print("❌ Invalid option. Please choose 1-7.", style="red")
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                console.print(f"\n[yellow]👋 Settings cancelled[/yellow]")
                return "exit"
    
    def quick_settings_menu(self, current_settings):
        """Quick settings menu for common options."""
        while True:
            self.clear_screen()
            
            console.print(Panel.fit(
                f"[bold cyan]🎯 Quick Settings - Tiz Lion AI Agent[/bold cyan]\n\n"
                f"[yellow]Change frequently used settings quickly[/yellow]",
                title="🦁 Quick Configuration",
                border_style="cyan"
            ))
            
            # Show current values, using LIVE properties for fresh data
            if CONFIG_AVAILABLE:
                current_model = settings.live_openrouter_model
                current_videos = str(settings.live_channel_parser_max_videos)
                current_comments = str(settings.live_max_comments_per_video)
                current_temperature = str(settings.live_openrouter_temperature)
            else:
                current_model = current_settings.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
                current_videos = current_settings.get("CHANNEL_PARSER_MAX_VIDEOS", "10")
                current_comments = current_settings.get("MAX_COMMENTS_PER_VIDEO", "100")
                current_temperature = current_settings.get("OPENROUTER_TEMPERATURE", "0.7")
            
            # Quick settings table
            quick_table = Table(title="🚀 Current Quick Settings")
            quick_table.add_column("Setting", style="cyan")
            quick_table.add_column("Current Value", style="yellow")
            quick_table.add_column("Description", style="white")
            
            quick_table.add_row("🧠 AI Model", current_model, "AI model for content analysis & generation")
            quick_table.add_row("📹 Max Videos", current_videos, "Maximum videos to process per channel")
            quick_table.add_row("💬 Max Comments", current_comments, "Maximum comments to analyze per video")
            quick_table.add_row("🌡️ Temperature", current_temperature, "AI creativity level (0.0-1.0)")
            
            console.print(quick_table)
            
            # Quick settings options
            console.print("\n🎯 Quick Settings Options:", style="bold cyan")
            options = Table()
            options.add_column("Option", style="cyan bold")
            options.add_column("Setting", style="white")
            options.add_column("Action", style="yellow")
            
            options.add_row("1", "🧠 Change AI Model", "Select from popular AI models")
            options.add_row("2", "📹 Set Max Videos", "Change videos per channel (1-20)")
            options.add_row("3", "💬 Set Max Comments", "Change comments per video (10-500)")
            options.add_row("4", "🌡️ Set Temperature", "Adjust AI creativity (0.0-1.0)")
            options.add_row("5", "💾 Save & Return", "Save changes and go back")
            options.add_row("6", "🔙 Cancel", "Return without saving")
            
            console.print(options)
            
            try:
                choice = console.input("\n[bold cyan]🎯 Select option (1-6): [/bold cyan]").strip()
                
                if choice == "1":
                    new_model = self.select_ai_model(current_model)
                    if new_model:
                        current_settings["OPENROUTER_MODEL"] = new_model
                        current_settings["CONTENT_ANALYZER_MODEL"] = new_model
                        current_settings["COMMENT_GENERATOR_MODEL"] = new_model
                        console.print(f"✅ AI Model updated to: {new_model}", style="green")
                        time.sleep(2)
                        
                elif choice == "2":
                    new_videos = self.get_numeric_input("📹 Max Videos per Channel (1-20)", current_videos, 1, 20)
                    if new_videos:
                        current_settings["CHANNEL_PARSER_MAX_VIDEOS"] = str(new_videos)
                        console.print(f"✅ Max videos updated to: {new_videos}", style="green")
                        time.sleep(2)
                        
                elif choice == "3":
                    new_comments = self.get_numeric_input("💬 Max Comments per Video (10-500)", current_comments, 10, 500)
                    if new_comments:
                        current_settings["MAX_COMMENTS_PER_VIDEO"] = str(new_comments)
                        console.print(f"✅ Max comments updated to: {new_comments}", style="green")
                        time.sleep(2)
                        
                elif choice == "4":
                    new_temp = self.get_float_input("🌡️ AI Temperature (0.0-1.0)", current_temperature, 0.0, 1.0)
                    if new_temp is not None:
                        current_settings["OPENROUTER_TEMPERATURE"] = str(new_temp)
                        console.print(f"✅ Temperature updated to: {new_temp}", style="green")
                        time.sleep(2)
                        
                elif choice == "5":
                    if self.save_env_settings(current_settings):
                        console.print("🎉 Quick settings saved successfully!", style="green")
                        # Refresh current_settings with reloaded config
                        current_settings = self.load_current_env_settings()
                        time.sleep(2)
                        return
                    else:
                        console.print("❌ Failed to save settings", style="red")
                        time.sleep(2)
                        
                elif choice == "6":
                    return
                else:
                    console.print("❌ Invalid option. Please choose 1-6.", style="red")
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                console.print(f"\n[yellow]👋 Quick settings cancelled[/yellow]")
                return
    
    def select_ai_model(self, current_model):
        """Show AI model selection menu with enhanced model information."""
        self.clear_screen()
        
        console.print(Panel.fit(
            f"[bold cyan]🧠 AI Model Selection - Tiz Lion AI Agent[/bold cyan]\n\n"
            f"[yellow]Choose the AI model for content analysis and comment generation[/yellow]\n"
            f"[green]🆓 Options 1-4: FREE TIER | 💎 Options 5-13: PREMIUM MODELS[/green]",
            title="🤖 AI Model Selector",
            border_style="cyan"
        ))
        
        # Model selection table with enhanced information
        model_table = Table(title="🚀 Available AI Models (Free & Premium)")
        model_table.add_column("Option", style="cyan bold", width=8)
        model_table.add_column("Model ID", style="white", width=35)
        model_table.add_column("Description", style="yellow", width=40)
        model_table.add_column("Cost", style="green", width=18)
        model_table.add_column("Context", style="magenta", width=12)
        
        for key, model_info in self.available_models.items():
            marker = "👑" if model_info["name"] == current_model else "  "
            model_table.add_row(
                f"{key} {marker}",
                model_info["name"],
                model_info["description"],
                model_info["cost"],
                model_info["context"]
            )
        
        console.print(model_table)
        
        # Show detailed information for selected models
        console.print("\n📋 Model Details:", style="bold cyan")
        details_table = Table()
        details_table.add_column("Category", style="cyan bold")
        details_table.add_column("Details", style="white")
        
        details_table.add_row("🆓 Free Tier (1-4)", "No API costs - rate limited but excellent for testing")
        details_table.add_row("💎 Premium (5-13)", "Pay-per-use - higher limits and advanced capabilities")
        details_table.add_row("🚀 Recommended", "Option 1 (Free) or Option 5 (Premium) for best performance")
        details_table.add_row("💰 Most Economical", "Option 6 (Mistral Nemo) or Option 11 (GPT-4.1 Nano)")
        details_table.add_row("🔧 Best for Coding", "Option 10 (GPT-4.1 Mini) or Option 12 (Claude 3.7)")
        details_table.add_row("👑 Flagship Models", "Option 13 (Claude Sonnet 4) - latest advanced reasoning")
        
        console.print(details_table)
        
        # Show current model from config if available
        display_current = current_model
        if CONFIG_AVAILABLE and not current_model:
            display_current = settings.OPENROUTER_MODEL
        console.print(f"\n[yellow]Current model: {display_current}[/yellow]")
        
        try:
            choice = console.input("\n[bold cyan]🎯 Select model (1-13) or Enter to cancel: [/bold cyan]").strip()
            
            if choice in self.available_models:
                selected_model = self.available_models[choice]["name"]
                selected_info = self.available_models[choice]
                
                # Show confirmation with model details
                console.print(f"\n✅ Selected: {selected_info['description']}", style="green")
                console.print(f"📋 Details: {selected_info['details']}", style="cyan")
                console.print(f"💰 Cost: {selected_info['cost']}", style="yellow")
                console.print(f"🔤 Context: {selected_info['context']} tokens", style="magenta")
                
                time.sleep(3)  # Show details for 3 seconds
                return selected_model
            elif choice == "":
                return None
            else:
                console.print("❌ Invalid selection. Please choose 1-13.", style="red")
                time.sleep(2)
                return None
                
        except KeyboardInterrupt:
            return None
    
    def get_numeric_input(self, prompt, current_value, min_val, max_val):
        """Get numeric input with validation."""
        try:
            # Use config default if current_value is empty or None
            if not current_value and CONFIG_AVAILABLE:
                if "Max Videos" in prompt:
                    current_value = str(settings.CHANNEL_PARSER_MAX_VIDEOS)
                elif "Max Comments" in prompt:
                    current_value = str(settings.MAX_COMMENTS_PER_VIDEO)
            
            user_input = console.input(f"\n[cyan]{prompt} (current: {current_value}): [/cyan]").strip()
            
            if not user_input:
                return None
                
            value = int(user_input)
            if min_val <= value <= max_val:
                return value
            else:
                console.print(f"❌ Value must be between {min_val} and {max_val}", style="red")
                time.sleep(2)
                return None
                
        except ValueError:
            console.print("❌ Please enter a valid number", style="red")
            time.sleep(2)
            return None
        except KeyboardInterrupt:
            return None
    
    def get_float_input(self, prompt, current_value, min_val, max_val):
        """Get float input with validation."""
        try:
            # Use config default if current_value is empty or None
            if not current_value and CONFIG_AVAILABLE:
                if "Temperature" in prompt:
                    current_value = str(settings.OPENROUTER_TEMPERATURE)
            
            user_input = console.input(f"\n[cyan]{prompt} (current: {current_value}): [/cyan]").strip()
            
            if not user_input:
                return None
                
            value = float(user_input)
            if min_val <= value <= max_val:
                return value
            else:
                console.print(f"❌ Value must be between {min_val} and {max_val}", style="red")
                time.sleep(2)
                return None
                
        except ValueError:
            console.print("❌ Please enter a valid number", style="red")
            time.sleep(2)
            return None
        except KeyboardInterrupt:
            return None
    
    def full_setup_menu(self, current_settings):
        """Full setup menu for all .env configuration."""
        while True:
            self.clear_screen()
            
            console.print(Panel.fit(
                f"[bold cyan]🔧 Full Setup - Tiz Lion AI Agent[/bold cyan]\n\n"
                f"[yellow]Complete .env file configuration with all API keys[/yellow]\n"
                f"[red]⚠️ Sensitive information - handle with care![/red]",
                title="🔐 Complete Configuration",
                border_style="cyan"
            ))
            
            # Essential settings checklist
            essential_table = Table(title="🚨 Essential Settings Status")
            essential_table.add_column("Setting", style="cyan")
            essential_table.add_column("Status", style="white")
            essential_table.add_column("Required For", style="yellow")
            
            youtube_api = current_settings.get("YOUTUBE_API_KEY") or current_settings.get("GOOGLE_API_KEY")
            openrouter_api = current_settings.get("OPENROUTER_API_KEY")
            telegram_token = current_settings.get("TELEGRAM_BOT_TOKEN")
            telegram_users = current_settings.get("TELEGRAM_ALLOWED_USERS")
            google_client_id = current_settings.get("GOOGLE_CLIENT_ID")
            google_client_secret = current_settings.get("GOOGLE_CLIENT_SECRET")
            
            essential_table.add_row(
                "🎬 YouTube API Key",
                "✅ Set" if youtube_api else "❌ Missing",
                "Video data access"
            )
            essential_table.add_row(
                "🤖 OpenRouter API Key",
                "✅ Set" if openrouter_api else "❌ Missing",
                "AI content generation"
            )
            essential_table.add_row(
                "📱 Telegram Bot Token",
                "✅ Set" if telegram_token else "❌ Missing",
                "Bot communication"
            )
            essential_table.add_row(
                "👥 Telegram Allowed Users",
                "✅ Set" if telegram_users else "❌ Missing",
                "Access control"
            )
            essential_table.add_row(
                "🔐 Google OAuth Client ID",
                "✅ Set" if google_client_id else "❌ Missing",
                "Comment posting"
            )
            essential_table.add_row(
                "🔑 Google OAuth Secret",
                "✅ Set" if google_client_secret else "❌ Missing",
                "Comment posting"
            )
            
            console.print(essential_table)
            
            # Setup options
            console.print("\n🔧 Full Setup Options:", style="bold cyan")
            setup_options = Table()
            setup_options.add_column("Option", style="cyan bold")
            setup_options.add_column("Category", style="white")
            setup_options.add_column("Description", style="yellow")
            
            setup_options.add_row("1", "🎬 YouTube API", "Configure YouTube Data API v3 key")
            setup_options.add_row("2", "🤖 OpenRouter API", "Configure AI model API key")
            setup_options.add_row("3", "📱 Telegram Bot", "Configure bot token and users")
            setup_options.add_row("4", "🔐 Google OAuth2", "Configure comment posting credentials")
            setup_options.add_row("5", "⚙️ Advanced Settings", "Timeouts, limits, and other options")
            setup_options.add_row("6", "📋 Import from File", "Load settings from backup file")
            setup_options.add_row("7", "💾 Save & Return", "Save all changes and return")
            setup_options.add_row("8", "🔙 Cancel", "Return without saving")
            
            console.print(setup_options)
            
            try:
                choice = console.input("\n[bold cyan]🎯 Select setup category (1-8): [/bold cyan]").strip()
                
                if choice == "1":
                    self.setup_youtube_api(current_settings)
                elif choice == "2":
                    self.setup_openrouter_api(current_settings)
                elif choice == "3":
                    self.setup_telegram_bot(current_settings)
                elif choice == "4":
                    self.setup_google_oauth(current_settings)
                elif choice == "5":
                    self.setup_advanced_settings(current_settings)
                elif choice == "6":
                    self.import_settings_from_file(current_settings)
                elif choice == "7":
                    if self.save_env_settings(current_settings):
                        console.print("🎉 Full setup saved successfully!", style="green")
                        # Refresh current_settings with reloaded config
                        current_settings = self.load_current_env_settings()
                        time.sleep(2)
                        return
                    else:
                        console.print("❌ Failed to save settings", style="red")
                        time.sleep(2)
                elif choice == "8":
                    return
                else:
                    console.print("❌ Invalid option. Please choose 1-8.", style="red")
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                console.print(f"\n[yellow]👋 Full setup cancelled[/yellow]")
                return
    
    def setup_youtube_api(self, current_settings):
        """Setup YouTube API configuration."""
        self.clear_screen()
        
        console.print(Panel.fit(
            f"[bold cyan]🎬 YouTube API Setup - Tiz Lion AI Agent[/bold cyan]\n\n"
            f"[yellow]Configure YouTube Data API v3 for video access[/yellow]\n"
            f"[blue]Get your API key from: https://console.cloud.google.com/[/blue]",
            title="🎬 YouTube Configuration",
            border_style="cyan"
        ))
        
        current_key = current_settings.get("YOUTUBE_API_KEY") or current_settings.get("GOOGLE_API_KEY", "")
        
        console.print(f"[yellow]Current YouTube API Key: {current_key[:20] + '...' if current_key else 'Not Set'}[/yellow]")
        
        try:
            new_key = console.input("\n[cyan]🔑 Enter YouTube API Key (or press Enter to keep current): [/cyan]").strip()
            
            if new_key:
                current_settings["YOUTUBE_API_KEY"] = new_key
                current_settings["GOOGLE_API_KEY"] = new_key  # Set both for compatibility
                console.print("✅ YouTube API Key updated!", style="green")
            else:
                console.print("ℹ️ YouTube API Key unchanged", style="blue")
                
            time.sleep(2)
            
        except KeyboardInterrupt:
            console.print(f"\n[yellow]👋 YouTube API setup cancelled[/yellow]")
    
    def setup_openrouter_api(self, current_settings):
        """Setup OpenRouter API configuration."""
        self.clear_screen()
        
        console.print(Panel.fit(
            f"[bold cyan]🤖 OpenRouter API Setup - Tiz Lion AI Agent[/bold cyan]\n\n"
            f"[yellow]Configure OpenRouter API for AI content generation[/yellow]\n"
            f"[blue]Get your API key from: https://openrouter.ai/keys[/blue]",
            title="🤖 OpenRouter Configuration",
            border_style="cyan"
        ))
        
        current_key = current_settings.get("OPENROUTER_API_KEY", "")
        
        console.print(f"[yellow]Current OpenRouter API Key: {current_key[:20] + '...' if current_key else 'Not Set'}[/yellow]")
        
        try:
            new_key = console.input("\n[cyan]🔑 Enter OpenRouter API Key (or press Enter to keep current): [/cyan]").strip()
            
            if new_key:
                current_settings["OPENROUTER_API_KEY"] = new_key
                console.print("✅ OpenRouter API Key updated!", style="green")
                
                # Also ask for model selection
                console.print("\n🧠 Would you like to select an AI model now?", style="cyan")
                model_choice = console.input("[cyan]Select model? (y/N): [/cyan]").strip().lower()
                
                if model_choice in ['y', 'yes']:
                    current_model = current_settings.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
                    new_model = self.select_ai_model(current_model)
                    if new_model:
                        current_settings["OPENROUTER_MODEL"] = new_model
                        current_settings["CONTENT_ANALYZER_MODEL"] = new_model
                        current_settings["COMMENT_GENERATOR_MODEL"] = new_model
            else:
                console.print("ℹ️ OpenRouter API Key unchanged", style="blue")
                
            time.sleep(2)
            
        except KeyboardInterrupt:
            console.print(f"\n[yellow]👋 OpenRouter API setup cancelled[/yellow]")
    
    def setup_telegram_bot(self, current_settings):
        """Setup Telegram Bot configuration."""
        self.clear_screen()
        
        console.print(Panel.fit(
            f"[bold cyan]📱 Telegram Bot Setup - Tiz Lion AI Agent[/bold cyan]\n\n"
            f"[yellow]Configure Telegram bot for user interaction[/yellow]\n"
            f"[blue]1. Message @BotFather on Telegram to create a bot[/blue]\n"
            f"[blue]2. Message @userinfobot to get your user ID[/blue]",
            title="📱 Telegram Configuration",
            border_style="cyan"
        ))
        
        current_token = current_settings.get("TELEGRAM_BOT_TOKEN", "")
        current_users = current_settings.get("TELEGRAM_ALLOWED_USERS", "")
        
        console.print(f"[yellow]Current Bot Token: {current_token[:20] + '...' if current_token else 'Not Set'}[/yellow]")
        console.print(f"[yellow]Current Allowed Users: {current_users if current_users else 'Not Set'}[/yellow]")
        
        try:
            # Bot Token
            new_token = console.input("\n[cyan]🤖 Enter Telegram Bot Token (or press Enter to keep current): [/cyan]").strip()
            if new_token:
                current_settings["TELEGRAM_BOT_TOKEN"] = new_token
                console.print("✅ Telegram Bot Token updated!", style="green")
            
            # Allowed Users
            new_users = console.input("\n[cyan]👥 Enter Allowed User IDs (comma-separated, or press Enter to keep current): [/cyan]").strip()
            if new_users:
                current_settings["TELEGRAM_ALLOWED_USERS"] = new_users
                console.print("✅ Telegram Allowed Users updated!", style="green")
                
            if not new_token and not new_users:
                console.print("ℹ️ Telegram settings unchanged", style="blue")
                
            time.sleep(2)
            
        except KeyboardInterrupt:
            console.print(f"\n[yellow]👋 Telegram setup cancelled[/yellow]")
    
    def setup_google_oauth(self, current_settings):
        """Setup Google OAuth2 configuration."""
        self.clear_screen()
        
        console.print(Panel.fit(
            f"[bold cyan]🔐 Google OAuth2 Setup - Tiz Lion AI Agent[/bold cyan]\n\n"
            f"[yellow]Configure OAuth2 credentials for YouTube comment posting[/yellow]\n"
            f"[blue]Get OAuth2 credentials from: https://console.cloud.google.com/[/blue]\n"
            f"[red]⚠️ Required for posting comments to YouTube[/red]",
            title="🔐 OAuth2 Configuration",
            border_style="cyan"
        ))
        
        current_client_id = current_settings.get("GOOGLE_CLIENT_ID", "")
        current_client_secret = current_settings.get("GOOGLE_CLIENT_SECRET", "")
        
        console.print(f"[yellow]Current Client ID: {current_client_id[:20] + '...' if current_client_id else 'Not Set'}[/yellow]")
        console.print(f"[yellow]Current Client Secret: {current_client_secret[:20] + '...' if current_client_secret else 'Not Set'}[/yellow]")
        
        try:
            # Client ID
            new_client_id = console.input("\n[cyan]🆔 Enter Google Client ID (or press Enter to keep current): [/cyan]").strip()
            if new_client_id:
                current_settings["GOOGLE_CLIENT_ID"] = new_client_id
                console.print("✅ Google Client ID updated!", style="green")
            
            # Client Secret
            new_client_secret = console.input("\n[cyan]🔑 Enter Google Client Secret (or press Enter to keep current): [/cyan]").strip()
            if new_client_secret:
                current_settings["GOOGLE_CLIENT_SECRET"] = new_client_secret
                console.print("✅ Google Client Secret updated!", style="green")
                
            # Enable comment posting if both are set
            if (new_client_id or current_client_id) and (new_client_secret or current_client_secret):
                enable_posting = console.input("\n[cyan]📝 Enable comment posting? (y/N): [/cyan]").strip().lower()
                if enable_posting in ['y', 'yes']:
                    current_settings["ENABLE_COMMENT_POSTING"] = "true"
                    console.print("✅ Comment posting enabled!", style="green")
                else:
                    current_settings["ENABLE_COMMENT_POSTING"] = "false"
                    console.print("ℹ️ Comment posting disabled", style="blue")
                
            if not new_client_id and not new_client_secret:
                console.print("ℹ️ OAuth2 settings unchanged", style="blue")
                
            time.sleep(2)
            
        except KeyboardInterrupt:
            console.print(f"\n[yellow]👋 OAuth2 setup cancelled[/yellow]")
    
    def setup_advanced_settings(self, current_settings):
        """Setup advanced configuration options."""
        while True:
            self.clear_screen()
            
            console.print(Panel.fit(
                f"[bold cyan]⚙️ Advanced Settings - Tiz Lion AI Agent[/bold cyan]\n\n"
                f"[yellow]Configure timeouts, limits, and advanced options[/yellow]",
                title="⚙️ Advanced Configuration",
                border_style="cyan"
            ))
            
            # Advanced settings table
            advanced_table = Table(title="🔧 Current Advanced Settings")
            advanced_table.add_column("Setting", style="cyan")
            advanced_table.add_column("Current Value", style="yellow")
            advanced_table.add_column("Description", style="white")
            
            advanced_table.add_row("⏱️ LangGraph Timeout", current_settings.get("LANGGRAPH_TIMEOUT", "300"), "Workflow timeout (seconds)")
            advanced_table.add_row("🔄 Max Retries", current_settings.get("LANGGRAPH_MAX_RETRIES", "3"), "Maximum retry attempts")
            advanced_table.add_row("📊 Analysis Timeout", current_settings.get("ANALYSIS_TIMEOUT", "300"), "Content analysis timeout")
            advanced_table.add_row("🕐 Comment Post Delay", current_settings.get("COMMENT_POST_DELAY", "10"), "Delay between posts (seconds)")
            advanced_table.add_row("📝 Comment Max Length", current_settings.get("COMMENT_MAX_LENGTH", "400"), "Maximum comment length")
            advanced_table.add_row("📝 Comment Min Length", current_settings.get("COMMENT_MIN_LENGTH", "150"), "Minimum comment length")
            
            console.print(advanced_table)
            
            # Advanced options
            console.print("\n⚙️ Advanced Options:", style="bold cyan")
            options = Table()
            options.add_column("Option", style="cyan bold")
            options.add_column("Setting", style="white")
            options.add_column("Action", style="yellow")
            
            options.add_row("1", "⏱️ Timeouts", "Configure workflow and agent timeouts")
            options.add_row("2", "📊 Processing Limits", "Set video and comment processing limits")
            options.add_row("3", "💬 Comment Settings", "Configure comment generation parameters")
            options.add_row("4", "🔄 Retry & Rate Limits", "Configure retry attempts and rate limiting")
            options.add_row("5", "🎛️ Feature Flags", "Enable/disable advanced features")
            options.add_row("6", "🔙 Return", "Return to full setup menu")
            
            console.print(options)
            
            try:
                choice = console.input("\n[bold cyan]🎯 Select advanced option (1-6): [/bold cyan]").strip()
                
                if choice == "1":
                    self.configure_timeouts(current_settings)
                elif choice == "2":
                    self.configure_processing_limits(current_settings)
                elif choice == "3":
                    self.configure_comment_settings(current_settings)
                elif choice == "4":
                    self.configure_retry_limits(current_settings)
                elif choice == "5":
                    self.configure_feature_flags(current_settings)
                elif choice == "6":
                    return
                else:
                    console.print("❌ Invalid option. Please choose 1-6.", style="red")
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                console.print(f"\n[yellow]👋 Advanced settings cancelled[/yellow]")
                return
    
    def configure_timeouts(self, current_settings):
        """Configure timeout settings."""
        console.print("\n⏱️ Timeout Configuration:", style="bold cyan")
        
        # Use config defaults if available
        if CONFIG_AVAILABLE:
            timeouts = [
                ("LANGGRAPH_TIMEOUT", "Workflow Timeout", str(settings.LANGGRAPH_TIMEOUT), "seconds"),
                ("ANALYSIS_TIMEOUT", "Content Analysis Timeout", str(settings.ANALYSIS_TIMEOUT), "seconds"),
                ("SCRAPER_TIMEOUT", "Content Scraper Timeout", str(settings.SCRAPER_TIMEOUT), "seconds"),
                ("COMMENT_POST_TIMEOUT", "Comment Posting Timeout", str(settings.COMMENT_POST_TIMEOUT), "seconds")
            ]
        else:
            timeouts = [
                ("LANGGRAPH_TIMEOUT", "Workflow Timeout", "300", "seconds"),
                ("ANALYSIS_TIMEOUT", "Content Analysis Timeout", "300", "seconds"),
                ("SCRAPER_TIMEOUT", "Content Scraper Timeout", "180", "seconds"),
                ("COMMENT_POST_TIMEOUT", "Comment Posting Timeout", "60", "seconds")
            ]
        
        for key, name, default, unit in timeouts:
            current_value = current_settings.get(key, default)
            new_value = self.get_numeric_input(f"⏱️ {name} ({unit})", current_value, 30, 600)
            if new_value:
                current_settings[key] = str(new_value)
                console.print(f"✅ {name} updated to: {new_value} {unit}", style="green")
        
        time.sleep(2)
    
    def configure_processing_limits(self, current_settings):
        """Configure processing limits."""
        console.print("\n📊 Processing Limits Configuration:", style="bold cyan")
        
        # Use config defaults if available
        if CONFIG_AVAILABLE:
            limits = [
                ("CHANNEL_PARSER_MAX_VIDEOS", "Max Videos per Channel", str(settings.CHANNEL_PARSER_MAX_VIDEOS), 1, 50),
                ("MAX_COMMENTS_PER_VIDEO", "Max Comments per Video", str(settings.MAX_COMMENTS_PER_VIDEO), 10, 1000),
                ("YOUTUBE_MAX_RESULTS", "YouTube API Max Results", str(settings.YOUTUBE_MAX_RESULTS), 10, 100)
            ]
        else:
            limits = [
            ("CHANNEL_PARSER_MAX_VIDEOS", "Max Videos per Channel", "10", 1, 50),
            ("MAX_COMMENTS_PER_VIDEO", "Max Comments per Video", "100", 10, 1000),
            ("YOUTUBE_MAX_RESULTS", "YouTube API Max Results", "50", 10, 100)
        ]
        
        for key, name, default, min_val, max_val in limits:
            current_value = current_settings.get(key, default)
            new_value = self.get_numeric_input(f"📊 {name}", current_value, min_val, max_val)
            if new_value:
                current_settings[key] = str(new_value)
                console.print(f"✅ {name} updated to: {new_value}", style="green")
        
        time.sleep(2)
    
    def configure_comment_settings(self, current_settings):
        """Configure comment generation settings."""
        console.print("\n💬 Comment Settings Configuration:", style="bold cyan")
        
        # Comment length settings - use config defaults
        if CONFIG_AVAILABLE:
            min_default = str(settings.COMMENT_MIN_LENGTH)
            max_default = str(settings.COMMENT_MAX_LENGTH)
            style_default = settings.COMMENT_STYLE
            delay_default = str(settings.COMMENT_POST_DELAY)
        else:
            min_default = "150"
            max_default = "400"
            style_default = "engaging"
            delay_default = "10"
        
        min_length = self.get_numeric_input("📝 Minimum Comment Length", current_settings.get("COMMENT_MIN_LENGTH", min_default), 50, 300)
        if min_length:
            current_settings["COMMENT_MIN_LENGTH"] = str(min_length)
        
        max_length = self.get_numeric_input("📝 Maximum Comment Length", current_settings.get("COMMENT_MAX_LENGTH", max_default), 200, 1000)
        if max_length:
            current_settings["COMMENT_MAX_LENGTH"] = str(max_length)
        
        # Comment style
        styles = {"1": "engaging", "2": "professional", "3": "casual", "4": "analytical"}
        current_style = current_settings.get("COMMENT_STYLE", style_default)
        
        console.print(f"\n💬 Comment Style Options:")
        for key, style in styles.items():
            marker = "👑" if style == current_style else "  "
            console.print(f"{key}{marker} {style.title()}")
        
        style_choice = console.input(f"\n[cyan]Select comment style (1-4) or Enter to keep current ({current_style}): [/cyan]").strip()
        if style_choice in styles:
            current_settings["COMMENT_STYLE"] = styles[style_choice]
            console.print(f"✅ Comment style updated to: {styles[style_choice]}", style="green")
        
        # Post delay
        post_delay = self.get_numeric_input("🕐 Delay between comment posts (seconds)", current_settings.get("COMMENT_POST_DELAY", delay_default), 5, 60)
        if post_delay:
            current_settings["COMMENT_POST_DELAY"] = str(post_delay)
        
        time.sleep(2)
    
    def configure_retry_limits(self, current_settings):
        """Configure retry and rate limit settings."""
        console.print("\n🔄 Retry & Rate Limit Configuration:", style="bold cyan")
        
        # Use config defaults if available
        if CONFIG_AVAILABLE:
            retry_settings = [
                ("LANGGRAPH_MAX_RETRIES", "Workflow Max Retries", str(settings.LANGGRAPH_MAX_RETRIES), 1, 10),
                ("COMMENT_POST_RETRIES", "Comment Post Retries", str(settings.COMMENT_POST_RETRIES), 1, 5),
                ("DESCRIPTION_RETRY_ATTEMPTS", "Description Extraction Retries", str(settings.DESCRIPTION_RETRY_ATTEMPTS), 1, 5)
            ]
        else:
            retry_settings = [
            ("LANGGRAPH_MAX_RETRIES", "Workflow Max Retries", "3", 1, 10),
            ("COMMENT_POST_RETRIES", "Comment Post Retries", "3", 1, 5),
            ("DESCRIPTION_RETRY_ATTEMPTS", "Description Extraction Retries", "2", 1, 5)
        ]
        
        for key, name, default, min_val, max_val in retry_settings:
            current_value = current_settings.get(key, default)
            new_value = self.get_numeric_input(f"🔄 {name}", current_value, min_val, max_val)
            if new_value:
                current_settings[key] = str(new_value)
                console.print(f"✅ {name} updated to: {new_value}", style="green")
        
        time.sleep(2)
    
    def configure_feature_flags(self, current_settings):
        """Configure feature flags."""
        console.print("\n🎛️ Feature Flags Configuration:", style="bold cyan")
        
        flags = [
            ("ENABLE_COMMENT_POSTING", "Comment Posting", "Enable actual comment posting to YouTube"),
            ("DEV_SKIP_RATE_LIMITS", "Skip Rate Limits", "Skip rate limiting (development only)"),
            ("ENABLE_ANALYTICS", "Analytics", "Enable usage analytics collection"),
            ("ENABLE_METRICS", "Metrics", "Enable performance metrics")
        ]
        
        for key, name, description in flags:
            # Use config default if available
            if CONFIG_AVAILABLE:
                if key == "ENABLE_COMMENT_POSTING":
                    default_val = str(settings.ENABLE_COMMENT_POSTING).lower()
                elif key == "DEV_SKIP_RATE_LIMITS":
                    default_val = str(settings.DEV_SKIP_RATE_LIMITS).lower()
                elif key == "ENABLE_ANALYTICS":
                    default_val = str(settings.ENABLE_ANALYTICS).lower()
                elif key == "ENABLE_METRICS":
                    default_val = str(settings.ENABLE_METRICS).lower()
                else:
                    default_val = "false"
            else:
                default_val = "false"
                
            current_value = current_settings.get(key, default_val).lower() == "true"
            console.print(f"\n🎛️ {name}: {'✅ Enabled' if current_value else '❌ Disabled'}")
            console.print(f"   {description}")
            
            toggle = console.input(f"[cyan]Toggle {name}? (y/N): [/cyan]").strip().lower()
            if toggle in ['y', 'yes']:
                new_value = "false" if current_value else "true"
                current_settings[key] = new_value
                status = "enabled" if new_value == "true" else "disabled"
                console.print(f"✅ {name} {status}!", style="green")
        
        time.sleep(2)
    
    def import_settings_from_file(self, current_settings):
        """Import settings from a backup file."""
        console.print("\n📋 Import Settings from File:", style="bold cyan")
        
        try:
            file_path = console.input("[cyan]📁 Enter backup file path: [/cyan]").strip()
            
            if not file_path:
                return
                
            backup_file = Path(file_path)
            if not backup_file.exists():
                console.print("❌ File not found!", style="red")
                time.sleep(2)
                return
            
            # Load settings from backup
            with open(backup_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        value = value.strip('"\'')
                        current_settings[key] = value
            
            console.print("✅ Settings imported successfully!", style="green")
            time.sleep(2)
            
        except Exception as e:
            console.print(f"❌ Error importing settings: {e}", style="red")
            time.sleep(2)
    
    def view_current_settings(self, current_settings):
        """View all current settings."""
        while True:
            self.clear_screen()
            
            console.print(Panel.fit(
                f"[bold cyan]📋 Current Settings - Tiz Lion AI Agent[/bold cyan]\n\n"
                f"[yellow]View all configuration values[/yellow]",
                title="📊 Settings Overview",
                border_style="cyan"
            ))
            
            # Group settings by category
            categories = {
                "🎬 YouTube API": ["YOUTUBE_API_KEY", "GOOGLE_API_KEY", "YOUTUBE_MAX_RESULTS"],
                "🤖 OpenRouter AI": ["OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_TEMPERATURE"],
                "📱 Telegram Bot": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS"],
                "🔐 Google OAuth": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "ENABLE_COMMENT_POSTING"],
                "⚙️ Processing": ["CHANNEL_PARSER_MAX_VIDEOS", "MAX_COMMENTS_PER_VIDEO", "COMMENT_STYLE"],
                "⏱️ Timeouts": ["LANGGRAPH_TIMEOUT", "ANALYSIS_TIMEOUT", "SCRAPER_TIMEOUT"]
            }
            
            for category, keys in categories.items():
                console.print(f"\n{category}:", style="bold cyan")
                
                settings_table = Table()
                settings_table.add_column("Setting", style="yellow")
                settings_table.add_column("Value", style="white")
                
                for key in keys:
                    value = current_settings.get(key, "Not Set")
                    # Mask sensitive values
                    if "API_KEY" in key or "TOKEN" in key or "SECRET" in key:
                        display_value = value[:10] + "..." if value != "Not Set" else "Not Set"
                    else:
                        display_value = value
                    
                    settings_table.add_row(key, display_value)
                
                console.print(settings_table)
            
            try:
                choice = console.input("\n[bold cyan]Press Enter to return or 'e' to export settings: [/bold cyan]").strip().lower()
                
                if choice == 'e':
                    self.export_current_settings(current_settings)
                else:
                    return
                    
            except KeyboardInterrupt:
                return
    
    def export_current_settings(self, current_settings):
        """Export current settings to a file."""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_file = self.project_root / f"settings_export_{timestamp}.env"
            
            with open(export_file, 'w', encoding='utf-8') as f:
                f.write("# Tiz Lion AI Agent - Settings Export\n")
                f.write(f"# Exported on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for key, value in sorted(current_settings.items()):
                    f.write(f'{key}="{value}"\n')
            
            console.print(f"✅ Settings exported to: {export_file}", style="green")
            time.sleep(2)
            
        except Exception as e:
            console.print(f"❌ Error exporting settings: {e}", style="red")
            time.sleep(2)
    
    def reset_to_defaults(self):
        """Reset settings to default values from example.env."""
        console.print("\n🔄 Reset to Default Settings:", style="bold cyan")
        console.print("[red]⚠️ This will overwrite your current .env file![/red]")
        
        try:
            confirm = console.input("\n[cyan]Are you sure you want to reset? (yes/NO): [/cyan]").strip()
            
            if confirm.lower() == "yes":
                if self.example_env_file.exists():
                    # Copy example.env to .env
                    with open(self.example_env_file, 'r', encoding='utf-8') as src:
                        content = src.read()
                    
                    with open(self.env_file, 'w', encoding='utf-8') as dst:
                        dst.write(content)
                    
                    # Reload config to pick up reset values
                    if CONFIG_AVAILABLE and reload_settings:
                        global settings
                        settings = reload_settings()
                        console.print("🔄 Configuration reloaded with default values!", style="cyan")
                    
                    console.print("✅ Settings reset to defaults successfully!", style="green")
                else:
                    console.print("❌ example.env file not found!", style="red")
            else:
                console.print("ℹ️ Reset cancelled", style="blue")
                
            time.sleep(2)
            
        except Exception as e:
            console.print(f"❌ Error resetting settings: {e}", style="red")
            time.sleep(2)
    
    def backup_settings(self):
        """Create a backup of current settings."""
        try:
            if not self.env_file.exists():
                console.print("❌ No .env file to backup!", style="red")
                time.sleep(2)
                return
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = self.project_root / f"env_backup_{timestamp}.env"
            
            # Copy current .env to backup
            with open(self.env_file, 'r', encoding='utf-8') as src:
                content = src.read()
            
            with open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(f"# Tiz Lion AI Agent - Settings Backup\n")
                dst.write(f"# Created on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                dst.write(content)
            
            console.print(f"✅ Settings backed up to: {backup_file}", style="green")
            time.sleep(2)
            
        except Exception as e:
            console.print(f"❌ Error creating backup: {e}", style="red")
            time.sleep(2)
    
    def run_oauth2_setup(self):
        """Run the OAuth2 setup script."""
        console.print("\n🔐 Starting OAuth2 Setup for YouTube Access...", style="cyan")
        
        if not self.oauth_script.exists():
            console.print("❌ OAuth2 setup script not found!", style="red")
            return False
        
        venv_python = self.get_venv_python()
        
        try:
            # Show OAuth2 loading animation
            self.show_loading_animation(3, "Preparing OAuth2 Authentication...")
            
            # Run OAuth2 setup
            result = subprocess.run([venv_python, str(self.oauth_script)])
            
            if result.returncode == 0:
                console.print("✅ OAuth2 setup completed successfully!", style="green")
                return True
            else:
                console.print("⚠️ OAuth2 setup completed with warnings", style="yellow")
                return True
                
        except subprocess.CalledProcessError as e:
            console.print(f"❌ OAuth2 setup failed: {e}", style="red")
            return False
        except KeyboardInterrupt:
            console.print("\n⏹️ OAuth2 setup cancelled by user", style="yellow")
            return False
    
    def start_main_application(self):
        """Start the main application."""
        console.print("\n🚀 Launching YouTube Comment AI Agent...", style="cyan")
        
        # Show final Tiz Lion loading screen
        self.show_loading_animation(3, "🤖 Tiz Lion AI Agent Ready to Deploy! 🤖")
        
        # Clear screen and show final menu
        self.clear_screen()
        
        # Final branded panel
        console.print(Panel.fit(
            f"[bold cyan]🤖 {self.project_name} 🤖[/bold cyan]\n\n"
            f"[bold white]Developed by: {self.brand_name}[/bold white]\n"
            f"[blue]GitHub: {self.github_url}[/blue]\n\n"
            f"[green]🚀 Ready for AI-Powered YouTube Automation! 🚀[/green]\n"
            f"[yellow]💬 Intelligent Comment Generation & Posting[/yellow]",
            title="🦁 Tiz Lion AI Agent",
            border_style="cyan"
        ))
        
        # Application options - with settings access
        choices = Table(title="🚀 Tiz Lion AI Agent - Launch Options")
        choices.add_column("Option", style="cyan bold")
        choices.add_column("Description", style="white")
        choices.add_column("Features", style="yellow")
        
        choices.add_row("1", "🤖 Start Complete AI Automation", "FastAPI with Integrated Telegram Bot")
        choices.add_row("2", "⚙️ Configure Settings", "Modify AI models, API keys, and options")
        choices.add_row("3", "👋 Exit", "Maybe Later...")
        
        console.print(choices)
        
        while True:
            try:
                choice = console.input("\n[bold cyan]🎯 Select launch option (1-3): [/bold cyan]").strip()
                
                if choice == "1":
                    self.start_full_agent()
                    break
                elif choice == "2":
                    settings_result = self.show_settings_menu()
                    if settings_result == "continue":
                        # User chose to continue to launch after settings
                        self.start_full_agent()
                        break
                    elif settings_result == "exit":
                        console.print(f"[yellow]👋 Thanks for using Tiz Lion AI Agent![/yellow]")
                        console.print(f"[blue]🔗 Follow updates: {self.github_url}[/blue]")
                        break
                    # If settings_result is None, continue the loop to show menu again
                elif choice == "3":
                    console.print(f"[yellow]👋 Thanks for using Tiz Lion AI Agent![/yellow]")
                    console.print(f"[blue]🔗 Follow updates: {self.github_url}[/blue]")
                    break
                else:
                    console.print("❌ Invalid option. Please choose 1-3.", style="red")
                    
            except KeyboardInterrupt:
                console.print(f"\n[yellow]👋 Goodbye from Tiz Lion![/yellow]")
                break
    
    def start_full_agent(self):
        """Start the complete Tiz Lion AI Agent (FastAPI with integrated Telegram bot)."""
        console.print("\n🚀 Launching Complete Tiz Lion AI Agent...", style="green bold")
        # Dynamic port display for VPS deployment
        port = "7844"
        if CONFIG_AVAILABLE and hasattr(settings, 'PORT'):
            port = str(settings.PORT)
        console.print(f"📡 FastAPI Server: http://localhost:{port}", style="blue")
        console.print("🤖 Telegram Bot: Integrated with FastAPI", style="blue")
        console.print("⚡ Unified AI automation system", style="cyan")
        console.print("💡 Tip: Use Ctrl+C to stop the agent", style="yellow")
        
        # Clean up any existing bot processes before starting
        console.print("\n🔍 Ensuring no conflicting processes...", style="cyan")
        kill_existing_python_processes()
        
        venv_python = self.get_venv_python()
        
        try:
            console.print("\n🌐 Starting Tiz Lion AI Agent...", style="cyan")
            console.print("🔄 FastAPI will automatically start the Telegram service", style="blue")
            
            # Start the main FastAPI app which includes integrated Telegram service
            # This is all we need - no separate telegram_bot.py required!
            # Check if custom port is configured for VPS deployment
            port = "7844"
            if CONFIG_AVAILABLE and hasattr(settings, 'PORT'):
                port = str(settings.PORT)
            
            subprocess.run([
                venv_python, "-m", "uvicorn", "app.main:app", 
                "--reload", "--host", "0.0.0.0", "--port", port
            ])
            
        except KeyboardInterrupt:
            console.print("\n⏹️ Stopping Tiz Lion AI Agent...", style="yellow")
        except Exception as e:
            console.print(f"\n❌ Error starting AI Agent: {e}", style="red")
            console.print("🔧 Check your .env file configuration", style="blue")
        finally:
            console.print("✅ Tiz Lion AI Agent stopped safely", style="green")
            console.print(f"🔗 Report issues: {self.github_url}/issues", style="blue")
    
    def run(self):
        """Main startup sequence."""
        try:
            # Initial Tiz Lion branding animation - 3 seconds
            self.show_loading_animation(3, "🦁 Tiz Lion AI Agent Starting Up... 🦁")
            
            # Clear and show welcome with branding
            self.clear_screen()
            console.print(Panel.fit(
                f"[bold cyan]🦁 Welcome to Tiz Lion's AI Laboratory! 🦁[/bold cyan]\n\n"
                f"[bold white]🤖 {self.project_name}[/bold white]\n"
                f"[blue]👨‍💻 Created by: {self.brand_name}[/blue]\n"
                f"[blue]🔗 GitHub: {self.github_url}[/blue]\n\n"
                f"[yellow]🚀 AI-Powered YouTube Comment Automation[/yellow]\n"
                f"[green]📊 Intelligent Content Analysis & Generation[/green]",
                title="🚀 Tiz Lion AI Agent",
                border_style="cyan"
            ))
            
            # System checks with progress
            console.print("\n🔍 Running system diagnostics...", style="cyan")
            
            if not self.check_python_version():
                return False
            
            if not self.check_virtual_environment():
                return False
            
            if not self.install_requirements():
                return False
            
            # Show system info
            self.show_system_info()
            
            # Settings Configuration Menu
            console.print("\n" + "="*70, style="cyan")
            console.print("⚙️ Tiz Lion AI Agent - Configuration Manager", style="bold yellow")
            
            # Check if .env file exists and show appropriate options
            env_file = self.project_root / ".env"
            if not env_file.exists():
                console.print("\n⚠️ [bold red]No .env configuration file found![/bold red]", style="red")
                console.print("🔧 You need to configure API keys and settings to use the AI agent", style="yellow")
                
                config_choice = console.input("\n[cyan]🎯 Would you like to configure settings now? (Y/n): [/cyan]").strip().lower()
                if config_choice not in ['n', 'no']:
                    settings_result = self.show_settings_menu()
                    if settings_result == "exit":
                        console.print("👋 Configuration cancelled. Please set up .env file manually.", style="yellow")
                        return False
                else:
                    console.print("👋 Please configure .env file manually and try again", style="yellow")
                    return False
            else:
                # .env exists, offer optional configuration
                console.print("✅ Configuration file found", style="green")
                
                config_choice = console.input("\n[cyan]⚙️ Configure settings before launch? (y/N): [/cyan]").strip().lower()
                if config_choice in ['y', 'yes']:
                    settings_result = self.show_settings_menu()
                    if settings_result == "exit":
                        console.print("👋 Settings configuration cancelled by user", style="yellow")
                        console.print("✅ Continuing with current settings...", style="green")
                        # Don't return False - user just cancelled settings, not the entire startup
            
            # OAuth2 setup option
            console.print("\n" + "="*70, style="cyan")
            console.print("🔐 OAuth2 Setup for YouTube Comment Posting", style="bold yellow")
            oauth_choice = console.input("[cyan]🤖 Enable comment posting with OAuth2? (y/N): [/cyan]").strip().lower()
            
            if oauth_choice in ['y', 'yes']:
                if self.run_oauth2_setup():
                    # Success animation
                    self.show_loading_animation(3, "🎉 OAuth2 Setup Complete! 🎉")
                else:
                    console.print("⚠️ OAuth2 setup incomplete. You can run 'python oauth2_setup.py' later.", style="yellow")
                    time.sleep(2)
            else:
                console.print("ℹ️ OAuth2 setup skipped. AI agent will run in read-only mode.", style="blue")
            
            # Final launch sequence
            self.start_main_application()
            
            return True
            
        except KeyboardInterrupt:
            console.print(f"\n👋 Startup cancelled. Thanks for trying Tiz Lion AI Agent!", style="yellow")
            return False
        except Exception as e:
            console.print(f"\n❌ Startup error: {e}", style="red")
            console.print(f"🔗 Report issues: {self.github_url}/issues", style="blue")
            return False


def main():
    """Main entry point for Tiz Lion's YouTube Comment AI Agent."""
    
    # Show initial banner
    print(Fore.CYAN + Style.BRIGHT + """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║               🦁 TIZ LION AI AGENT 🦁                       ║
    ║                                                              ║
    ║            🤖 YouTube Comment Automation 🤖                 ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    time.sleep(1)
    
    # Initialize and run the AI agent
    agent = TizLionAIAgent()
    success = agent.run()
    
    if not success:
        print(f"\n{Fore.RED}❌ Startup failed. Check the errors above.")
        print(f"{Fore.BLUE}🔗 Get help: {agent.github_url}/issues")
        sys.exit(1)


if __name__ == "__main__":
    main() 