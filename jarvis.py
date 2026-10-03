"""
=============================================================================
J.A.R.V.I.S - Personal AI Desktop Voice Assistant (V1)
=============================================================================
A single-file, reliable personal AI assistant for Windows.

Setup Instructions:
1. Install dependencies:
   pip install google-genai SpeechRecognition pyttsx3 psutil Pillow

   * Optional (for microphone input on Python versions with wheel support):
     pip install PyAudio
   * If PyAudio is not available, JARVIS automatically provides smooth
     interactive console text input while maintaining full voice output (TTS).

2. Set your Gemini API Key in Windows environment variables:
   In PowerShell:
     $env:GEMINI_API_KEY="your_api_key_here"
   In Command Prompt (CMD):
     set GEMINI_API_KEY=your_api_key_here
   Or permanently in Windows System Properties -> Environment Variables.

3. Run JARVIS:
   python jarvis.py
=============================================================================
"""

import os
import sys
import time
import datetime
import platform
import shutil
import subprocess
import webbrowser
import re
import ast
import operator
import threading
from typing import Optional, Tuple

# =============================================================================
# ENVIRONMENT & CONFIGURATION LOADER
# =============================================================================
def load_env_file(env_filename: str = ".env") -> None:
    """
    Automatically loads environment variables from a .env file.
    Supports python-dotenv if installed, with a built-in zero-dependency fallback.
    """
    # 1. Try python-dotenv if present
    try:
        import dotenv
        dotenv.load_dotenv(env_filename)
        return
    except ImportError:
        pass

    # 2. Built-in zero-dependency .env parser fallback
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.getcwd(), env_filename),
        os.path.join(script_dir, env_filename),
    ]

    for env_path in candidates:
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and (key not in os.environ or not os.environ[key]):
                            os.environ[key] = val
                break
            except Exception:
                pass


# Automatically load .env on launch
load_env_file()

# Core Libraries
try:
    import psutil
except ImportError:
    psutil = None

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    sd = None
    np = None

# Gemini SDK
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# =============================================================================
# GLOBAL CONFIGURATION & INITIALIZATION
# =============================================================================
WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "okay jarvis"]
AI_SYSTEM_INSTRUCTION = (
    "You are JARVIS, a helpful personal desktop AI assistant. "
    "Be concise, intelligent, polite, and professional. Address the user respectfully. "
    "You can assist with questions and computer tasks. "
    "Never claim to have performed an action unless the program actually performed it. "
    "Keep answers conversational and suitable for speech synthesis."
)

# Optional Windows COM interface for robust SAPI TTS
try:
    import win32com.client
except ImportError:
    win32com = None

import collections

# Initialize Windows SAPI Voice Engine safely
sapi_voice = None
if win32com is not None:
    try:
        sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
        sapi_voice.Rate = 1  # Natural conversational tempo
        sapi_voice.Volume = 100
    except Exception:
        sapi_voice = None

# Fallback pyttsx3 engine
tts_engine = None
tts_lock = threading.Lock()

if sapi_voice is None and pyttsx3 is not None:
    try:
        tts_engine = pyttsx3.init()
        tts_engine.setProperty("rate", 180)
        tts_engine.setProperty("volume", 0.95)
    except Exception:
        tts_engine = None


def speak(text: str) -> None:
    """Prints and speaks the provided text reliably using Windows SAPI / TTS."""
    if not text:
        return

    print(f"\nJARVIS: {text}\n")

    # 1. Primary: Native Windows SAPI (synchronous, never locks up)
    if sapi_voice is not None:
        try:
            sapi_voice.Speak(text)
            return
        except Exception:
            pass

    # 2. Secondary: pyttsx3 fallback
    if tts_engine is not None:
        try:
            with tts_lock:
                tts_engine.say(text)
                tts_engine.runAndWait()
        except Exception:
            pass


# =============================================================================
# GEMINI AI BRAIN (ONE-TO-ONE CONVERSATION MEMORY)
# =============================================================================
class ChatBrain:
    """Maintains continuous 1-on-1 conversational memory with Google Gemini."""

    def __init__(self):
        self.chat_session = None
        self.client = None
        self._initialize_chat()

    def _initialize_chat(self):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or genai is None:
            return

        try:
            self.client = genai.Client(api_key=api_key)
            # Create a persistent chat session
            self.chat_session = self.client.chats.create(
                model="gemini-3.5-flash-lite",
                config=types.GenerateContentConfig(
                    system_instruction=AI_SYSTEM_INSTRUCTION,
                    temperature=0.7,
                    max_output_tokens=350,
                ),
            )
        except Exception:
            self.chat_session = None

    def ask(self, prompt: str) -> str:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return (
                "I could not reach Gemini AI because GEMINI_API_KEY is not set in your .env file. "
                "Please configure your key to enable my AI brain."
            )

        if genai is None:
            return "The google-genai library is not installed. Please run pip install google-genai."

        if self.chat_session is None:
            self._initialize_chat()

        # 1. Try continuous chat session with conversation memory
        if self.chat_session is not None:
            try:
                response = self.chat_session.send_message(prompt)
                if response and response.text:
                    cleaned_text = response.text.replace("**", "").replace("*", "").strip()
                    return cleaned_text
            except Exception:
                # If session timed out or had an error, reset and try fallback
                self.chat_session = None

        # 2. Fallback to direct generate_content with multiple models
        try:
            client = genai.Client(api_key=api_key)
            models_to_try = [
                "gemini-3.5-flash-lite",
                "gemini-3.5-flash",
                "gemini-3-flash-preview",
                "gemini-3.7-flash",
            ]
            response = None
            last_err = None

            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=AI_SYSTEM_INSTRUCTION,
                            temperature=0.7,
                            max_output_tokens=300,
                        ),
                    )
                    if response and response.text:
                        break
                except Exception as model_err:
                    last_err = model_err
                    continue

            if response and response.text:
                cleaned_text = response.text.replace("**", "").replace("*", "").strip()
                return cleaned_text
            elif last_err:
                raise last_err
            return "I apologize, but I received an empty response from Gemini."
        except Exception as e:
            error_msg = str(e)
            if "API_KEY_INVALID" in error_msg or "invalid" in error_msg.lower():
                return "The configured GEMINI_API_KEY appears to be invalid. Please check your .env file."
            return f"I encountered an error connecting to Gemini AI: {error_msg}"


# Global AI brain instance
ai_brain = ChatBrain()


def ask_ai(prompt: str) -> str:
    """Queries the conversational AI brain."""
    return ai_brain.ask(prompt)


# =============================================================================
# SAFE CALCULATOR (NO UNRESTRICTED EVAL)
# =============================================================================
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_ast(node):
    """Recursively evaluates an AST node safely for math operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval_ast(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Invalid constant type.")
    elif isinstance(node, ast.BinOp):
        left = _safe_eval_ast(node.left)
        right = _safe_eval_ast(node.right)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](left, right)
        raise ValueError("Unsupported operator.")
    elif isinstance(node, ast.UnaryOp):
        operand = _safe_eval_ast(node.operand)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](operand)
        raise ValueError("Unsupported unary operator.")
    else:
        raise ValueError("Unsupported AST syntax.")


def safe_calculate(expression_str: str) -> Optional[float]:
    """Safely calculates mathematical expressions without using eval()."""
    try:
        # Preprocess percentage phrases: "25 percent of 800" -> "(25 / 100) * 800"
        cleaned = re.sub(
            r"(\d+(?:\.\d+)?)\s*(?:percent|%)\s*(?:of)\s*(\d+(?:\.\d+)?)",
            r"((\1 / 100) * \2)",
            expression_str,
            flags=re.IGNORECASE,
        )
        # Clean common symbols
        cleaned = cleaned.replace("x", "*").replace("X", "*").replace("^", "**")
        # Remove any non-math characters
        sanitized = re.sub(r"[^0-9\+\-\*\/\%\(\)\.\s]", "", cleaned).strip()
        if not sanitized:
            return None

        parsed = ast.parse(sanitized, mode="eval")
        result = _safe_eval_ast(parsed)
        return result
    except Exception:
        return None


# =============================================================================
# LOCAL COMMAND HANDLERS
# =============================================================================
def get_greeting() -> str:
    """Returns an appropriate greeting based on current local time."""
    current_hour = datetime.datetime.now().hour
    if current_hour < 12:
        time_greeting = "Good morning"
    elif 12 <= current_hour < 17:
        time_greeting = "Good afternoon"
    else:
        time_greeting = "Good evening"
    return f"{time_greeting}. JARVIS is online. How may I assist you?"


def handle_time() -> str:
    """Returns current formatted time."""
    now = datetime.datetime.now()
    formatted_time = now.strftime("%I:%M %p")
    if formatted_time.startswith("0"):
        formatted_time = formatted_time[1:]
    return f"The current time is {formatted_time}."


def handle_date() -> str:
    """Returns current formatted date."""
    now = datetime.datetime.now()
    formatted_date = now.strftime("%A, %B %d, %Y")
    return f"Today is {formatted_date}."


def handle_system_info(info_type: str) -> str:
    """Returns basic hardware/OS metrics."""
    try:
        if info_type == "cpu":
            if psutil:
                usage = psutil.cpu_percent(interval=0.5)
                return f"Current CPU utilization is at {usage} percent."
            return "psutil library is required for CPU monitoring."

        elif info_type == "ram":
            if psutil:
                mem = psutil.virtual_memory()
                used_gb = round((mem.total - mem.available) / (1024**3), 1)
                total_gb = round(mem.total / (1024**3), 1)
                return f"RAM usage is {mem.percent} percent, with {used_gb} Gigabytes used out of {total_gb} Gigabytes."
            return "psutil library is required for RAM monitoring."

        elif info_type == "os":
            os_name = platform.system()
            release = platform.release()
            version = platform.version()
            return f"You are running {os_name} {release} (Version {version})."

    except Exception as e:
        return f"Unable to retrieve system info: {e}"
    return "System info not available."


def handle_open_website(query: str) -> Tuple[bool, str]:
    """Opens popular websites or custom URLs safely in the default browser."""
    sites = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://www.github.com",
        "gmail": "https://mail.google.com",
        "chatgpt": "https://chatgpt.com",
        "reddit": "https://www.reddit.com",
        "stack overflow": "https://stackoverflow.com",
        "wikipedia": "https://www.wikipedia.org",
    }

    for name, url in sites.items():
        if name in query:
            try:
                webbrowser.open(url)
                return True, f"Opening {name.title()}."
            except Exception as e:
                return True, f"Could not open {name}: {e}"

    # Generic website matching like 'open example.com'
    match = re.search(r"open\s+([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})", query)
    if match:
        domain = match.group(1)
        url = f"https://{domain}" if not domain.startswith("http") else domain
        try:
            webbrowser.open(url)
            return True, f"Opening {domain}."
        except Exception as e:
            return True, f"Could not open {domain}: {e}"

    return False, ""


def handle_open_app(query: str) -> Tuple[bool, str]:
    """Safely launches common Windows applications."""
    apps = {
        "notepad": {"cmd": "notepad.exe", "name": "Notepad"},
        "calculator": {"cmd": "calc.exe", "name": "Calculator"},
        "calc": {"cmd": "calc.exe", "name": "Calculator"},
        "file explorer": {"cmd": "explorer.exe", "name": "File Explorer"},
        "explorer": {"cmd": "explorer.exe", "name": "File Explorer"},
        "vs code": {"cmd": "code", "name": "Visual Studio Code"},
        "vscode": {"cmd": "code", "name": "Visual Studio Code"},
        "chrome": {"cmd": "chrome", "name": "Google Chrome"},
        "google chrome": {"cmd": "chrome", "name": "Google Chrome"},
        "edge": {"cmd": "msedge", "name": "Microsoft Edge"},
        "microsoft edge": {"cmd": "msedge", "name": "Microsoft Edge"},
    }

    # Known absolute fallback paths for Windows browsers
    known_paths = {
        "chrome": [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ],
        "msedge": [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ],
    }

    for key, app_data in apps.items():
        # Match 'open [app]' or just the app name if explicitly asked
        pattern = rf"\b(open|launch|start)?\s*{re.escape(key)}\b"
        if re.search(pattern, query):
            cmd = app_data["cmd"]
            name = app_data["name"]

            # Try locating in PATH
            if shutil.which(cmd):
                try:
                    subprocess.Popen([cmd], shell=True)
                    return True, f"Opening {name}."
                except Exception as e:
                    return True, f"Failed to launch {name}: {e}"

            # Try direct Windows paths if browser
            if cmd in known_paths:
                for path in known_paths[cmd]:
                    if os.path.exists(path):
                        try:
                            os.startfile(path)
                            return True, f"Opening {name}."
                        except Exception as e:
                            return True, f"Failed to start {name}: {e}"

            # Try os.startfile directly
            try:
                os.startfile(cmd)
                return True, f"Opening {name}."
            except Exception:
                pass

            return True, f"I could not find {name} installed on your system."

    return False, ""


def handle_search_web(query: str) -> Tuple[bool, str]:
    """Extracts search query and opens Google search in default browser."""
    patterns = [
        r"search\s+the\s+web\s+for\s+(.+)",
        r"search\s+google\s+for\s+(.+)",
        r"search\s+for\s+(.+)",
        r"google\s+(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            search_term = match.group(1).strip()
            # Clean trailing punctuation
            search_term = re.sub(r"[\s,\.\!\?]+$", "", search_term)
            if search_term:
                url = f"https://www.google.com/search?q={search_term.replace(' ', '+')}"
                try:
                    webbrowser.open(url)
                    return True, f"Searching the web for {search_term}."
                except Exception as e:
                    return True, f"Failed to open browser search: {e}"

    return False, ""


def handle_screenshot() -> str:
    """Takes a screenshot and saves it to the user's Pictures/Screenshots directory."""
    if ImageGrab is None:
        return "Pillow library is required to capture screenshots. Please run pip install Pillow."

    try:
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        screenshots_dir = os.path.join(pictures_dir, "Screenshots")

        # Create directory if it doesn't exist
        os.makedirs(screenshots_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)

        # Capture and save
        screenshot = ImageGrab.grab()
        screenshot.save(filepath)

        return f"Screenshot taken successfully and saved to {filepath}."
    except Exception as e:
        return f"Failed to capture screenshot: {e}"


# =============================================================================
# COMMAND ROUTER
# =============================================================================
def strip_wake_word(text: str) -> str:
    """Cleans and removes wake words ('Jarvis', 'Hey Jarvis') from start, end, or inside sentences."""
    if not text:
        return ""
    
    cleaned = text.strip()
    # Normalize wake words with regex regardless of position (start or end)
    cleaned = re.sub(r"\b(hey\s+|ok\s+|okay\s+)?jarvis\b", "", cleaned, flags=re.IGNORECASE)
    # Strip residual punctuation and spaces
    cleaned = re.sub(r"^[\s,\.\!\?]+", "", cleaned)
    cleaned = re.sub(r"[\s,\.\!\?]+$", "", cleaned).strip()
    return cleaned


def route_command(raw_input: str) -> Tuple[str, bool]:
    """
    Main routing pipeline:
    1. Normalizes text
    2. Checks for wake word
    3. Checks local commands (time, date, apps, web, math, sys info, exit)
    4. Routes to Gemini AI for general knowledge & conversation
    Returns (response_text, should_exit)
    """
    if not raw_input or not raw_input.strip():
        return "", False

    prompt = strip_wake_word(raw_input)
    prompt_lower = prompt.lower().strip()

    # If the user only said "Jarvis" or "Hey Jarvis"
    if not prompt_lower:
        return "Yes, I am listening. How can I help you?", False

    # 1. Exit Commands
    exit_triggers = ["goodbye", "exit", "quit", "shutdown", "bye", "go offline", "terminate"]
    if any(prompt_lower == trig or prompt_lower.startswith(trig) for trig in exit_triggers):
        return "Goodbye. JARVIS going offline.", True

    # 2. Conversational Quick Matches
    if prompt_lower in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]:
        return "Hello. How can I help you?", False

    if "who created you" in prompt_lower or "who made you" in prompt_lower:
        return "I am your personal AI assistant, created by you.", False

    if "what can you do" in prompt_lower or prompt_lower == "help":
        return (
            "I can tell you the time and date, open applications like Chrome, VS Code, "
            "and Calculator, open websites like YouTube and GitHub, search the web, "
            "perform safe calculations, monitor your CPU and RAM usage, take screenshots, "
            "and answer general questions using Gemini AI.",
            False,
        )

    # 3. Time and Date
    if "time" in prompt_lower and ("what" in prompt_lower or "tell" in prompt_lower or "current" in prompt_lower):
        return handle_time(), False

    if ("date" in prompt_lower or "today" in prompt_lower) and ("what" in prompt_lower or "tell" in prompt_lower or "current" in prompt_lower):
        return handle_date(), False

    # 4. System Info (CPU, RAM, OS)
    if "cpu" in prompt_lower:
        return handle_system_info("cpu"), False

    if "ram" in prompt_lower or "memory" in prompt_lower:
        return handle_system_info("ram"), False

    if "operating system" in prompt_lower or "what os" in prompt_lower or "system info" in prompt_lower:
        return handle_system_info("os"), False

    # 5. Screenshot
    if "screenshot" in prompt_lower or "screen capture" in prompt_lower:
        return handle_screenshot(), False

    # 6. Web Searches
    handled_search, search_resp = handle_search_web(prompt_lower)
    if handled_search:
        return search_resp, False

    # 7. Open Websites
    if "open" in prompt_lower or "launch" in prompt_lower:
        handled_web, web_resp = handle_open_website(prompt_lower)
        if handled_web:
            return web_resp, False

        # 8. Open Applications
        handled_app, app_resp = handle_open_app(prompt_lower)
        if handled_app:
            return app_resp, False

    # 9. Calculator
    if "calculate" in prompt_lower or "percent of" in prompt_lower or re.search(r"what is \d+", prompt_lower):
        # Extract math expression
        math_candidate = re.sub(r"^(calculate|what is|how much is)\s*", "", prompt_lower, flags=re.IGNORECASE)
        math_candidate = math_candidate.rstrip("?.").strip()
        result = safe_calculate(math_candidate)
        if result is not None:
            # Format integer nicely if whole number
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            return f"The result is {result}.", False

    # 10. Fallback to Gemini AI Brain
    ai_response = ask_ai(prompt)
    return ai_response, False


# =============================================================================
# VOICE & INPUT HANDLING
# =============================================================================
def record_with_sounddevice(
    fs: int = 16000,
    max_seconds: float = 12.0,
    silence_limit: float = 1.3,
    listen_timeout: float = 6.0,
) -> Optional[object]:
    """
    Captures voice from Windows default microphone using sounddevice.
    Maintains a rolling pre-speech ring buffer so initial words are never clipped.
    Uses dynamic RMS energy threshold for speech start/stop detection.
    """
    if sd is None or np is None or sr is None:
        return None

    block_size = 1024
    pre_buffer_size = 6  # ~380ms of pre-speech audio
    pre_buffer = collections.deque(maxlen=pre_buffer_size)
    frames = []

    try:
        with sd.InputStream(samplerate=fs, channels=1, dtype="int16") as stream:
            # 1. Calibrate ambient background noise for 0.3s
            ambient_energies = []
            for _ in range(max(1, int(fs / block_size * 0.3))):
                data, _ = stream.read(block_size)
                rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
                ambient_energies.append(rms)

            avg_ambient = float(np.mean(ambient_energies)) if ambient_energies else 30.0
            speech_threshold = max(avg_ambient * 1.4, 180.0)

            print("\nLISTENING... (Speak now or press Ctrl+C to exit)")

            # 2. Wait for speech start
            speech_started = False
            start_time = time.time()
            silence_start = None

            while True:
                data, _ = stream.read(block_size)
                rms = float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))
                elapsed = time.time() - start_time

                if not speech_started:
                    pre_buffer.append(data.copy())
                    if rms > speech_threshold:
                        speech_started = True
                        # Include pre-speech buffer so first syllables are preserved
                        frames.extend(list(pre_buffer))
                        silence_start = None
                    elif elapsed > listen_timeout:
                        # Timeout waiting for speech
                        return None
                else:
                    frames.append(data.copy())
                    if rms < speech_threshold:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= silence_limit:
                            # User stopped speaking
                            break
                    else:
                        silence_start = None

                    # Guard against exceeding max duration
                    if len(frames) * block_size / fs >= max_seconds:
                        break

            if frames:
                all_pcm = np.concatenate(frames, axis=0)
                audio_bytes = all_pcm.tobytes()
                return sr.AudioData(audio_bytes, fs, 2)
            return None

    except Exception:
        return None


def listen(recognizer: Optional[object] = None, mic_backend: Optional[str] = None) -> str:
    """
    Captures voice input from the microphone.
    Supports sounddevice (no C++ build tools required) and PyAudio backends.
    Gracefully falls back to console text input if no microphone is available.
    """
    if recognizer is None or sr is None or mic_backend is None:
        try:
            user_text = input("You (type command): ").strip()
            return user_text
        except (EOFError, KeyboardInterrupt):
            return "exit"

    # 1. Primary backend: sounddevice (Realtek / Windows Audio)
    if mic_backend == "sounddevice":
        try:
            audio = record_with_sounddevice()
            if audio is None:
                return ""
            print("Recognizing speech...")
            text = recognizer.recognize_google(audio)
            print(f"You: {text}")
            return text
        except sr.UnknownValueError:
            print("JARVIS: [Speech unrecognized]")
            return ""
        except sr.RequestError as e:
            print(f"JARVIS: [Speech recognition service unavailable: {e}]")
            return ""
        except Exception as e:
            print(f"\n[Microphone error: {e}. Falling back to keyboard input]")
            try:
                return input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                return "exit"

    # 2. Secondary backend: PyAudio / sr.Microphone
    elif mic_backend == "pyaudio":
        try:
            with sr.Microphone() as source:
                print("\nLISTENING... (Speak now or press Ctrl+C to exit)")
                recognizer.adjust_for_ambient_noise(source, duration=0.6)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)

            print("Recognizing speech...")
            text = recognizer.recognize_google(audio)
            print(f"You: {text}")
            return text
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            print("JARVIS: [Speech unrecognized]")
            return ""
        except sr.RequestError as e:
            print(f"JARVIS: [Speech service unavailable: {e}]")
            return ""
        except Exception:
            try:
                return input("You (type command): ").strip()
            except (EOFError, KeyboardInterrupt):
                return "exit"

    try:
        return input("You (type command): ").strip()
    except (EOFError, KeyboardInterrupt):
        return "exit"


# =============================================================================
# MAIN APPLICATION
# =============================================================================
def print_banner():
    """Displays the startup banner in the terminal."""
    banner = """
========================================
             J.A.R.V.I.S
    Personal AI Voice Assistant
========================================
STATUS: ONLINE
ENVIRONMENT: Windows
AI BRAIN: Google Gemini
========================================
"""
    print(banner)


def detect_microphone_backend() -> Tuple[Optional[str], Optional[str]]:
    """Detects available microphone hardware and driver backend."""
    # Check sounddevice
    if sd is not None and np is not None:
        try:
            input_device = sd.default.device[0]
            if input_device is not None and input_device >= 0:
                device_info = sd.query_devices(input_device, "input")
                device_name = device_info.get("name", "Windows Audio Device")
                return "sounddevice", device_name
        except Exception:
            pass

    # Check PyAudio / sr.Microphone
    if sr is not None:
        try:
            with sr.Microphone():
                return "pyaudio", "PyAudio Device"
        except Exception:
            pass

    return None, None


def main():
    """Main execution loop for JARVIS."""
    print_banner()

    # Check microphone availability
    recognizer = sr.Recognizer() if sr is not None else None
    mic_backend, mic_device_name = detect_microphone_backend()

    if mic_backend:
        print(f"[Microphone: Ready ({mic_device_name})]")
    else:
        print("[Microphone: Not detected. Interactive keyboard input mode enabled]")

    # Check Gemini API Key
    if os.environ.get("GEMINI_API_KEY"):
        print("[Gemini AI: Connected]")
    else:
        print("[Gemini AI: No GEMINI_API_KEY found. Check .env file]")

    # 1. Startup Greeting
    startup_greeting = get_greeting()
    speak(startup_greeting)

    # Main interaction loop
    while True:
        try:
            # Capture voice / input
            raw_input = listen(recognizer, mic_backend)

            if not raw_input or not raw_input.strip():
                continue

            # Route and execute command
            response, should_exit = route_command(raw_input)

            if response:
                speak(response)

            if should_exit:
                break

        except KeyboardInterrupt:
            speak("Goodbye. JARVIS going offline.")
            break
        except Exception as e:
            print(f"\n[Error encountered: {e}]")
            speak("I encountered an unexpected issue, but I am still online and ready.")


if __name__ == "__main__":
    main()
