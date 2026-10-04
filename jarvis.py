"""
=============================================================================
J.A.R.V.I.S - Personal AI Desktop Voice Assistant (V2)
=============================================================================
An intelligent, lightweight, and reliable personal desktop AI assistant
for Windows powered by Google Gemini AI with persistent memory, safe application
& folder launching, volume controls, file search, text file reading, screen vision,
system monitoring, and natural voice interaction.

Setup:
1. pip install -r requirements.txt
2. Configure GEMINI_API_KEY in .env file
3. python jarvis.py
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
import json
import ctypes
import glob
from typing import Optional, Tuple, List, Dict, Any

# =============================================================================
# ENVIRONMENT & CONFIGURATION LOADER
# =============================================================================
def load_env_file(env_filename: str = ".env") -> None:
    """
    Automatically loads environment variables from a .env file.
    Supports python-dotenv if installed, with a built-in zero-dependency fallback.
    """
    try:
        import dotenv
        dotenv.load_dotenv(env_filename)
        return
    except ImportError:
        pass

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

# Core Hardware & Media Libraries
try:
    import psutil
except ImportError:
    psutil = None

try:
    from PIL import ImageGrab, Image
except ImportError:
    ImageGrab = None
    Image = None

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

# Windows COM Interface for native SAPI TTS
try:
    import pythoncom
    import win32com.client
    WIN32COM_AVAILABLE = True
except ImportError:
    pythoncom = None
    win32com = None
    WIN32COM_AVAILABLE = False

# Optional pycaw for volume control
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

import collections

# =============================================================================
# GLOBAL CONFIGURATION & SYSTEM PROMPTS
# =============================================================================
WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "okay jarvis"]
AI_SYSTEM_INSTRUCTION = (
    "You are J.A.R.V.I.S V2, a personal desktop AI assistant. "
    "You are intelligent, professional, calm, concise, slightly futuristic, and respectful. "
    "Address the user naturally and politely. Provide concise answers suitable for speech output "
    "without markdown asterisks or excessive filler. If user personal facts or memories are provided "
    "in the context, use them seamlessly and accurately. Never claim to have executed computer actions "
    "unless you were informed they were completed."
)


# =============================================================================
# MULTI-LAYER TEXT-TO-SPEECH (TTS) ENGINE
# =============================================================================
tts_lock = threading.Lock()


def speak(text: str) -> None:
    """
    Prints and speaks text reliably using Windows SAPI / pyttsx3 / PowerShell fallback.
    Cleans markdown formatting and symbols so speech sounds natural.
    """
    if not text:
        return

    print(f"\nJARVIS: {text}\n")

    # Clean text for natural speech synthesis
    speech_text = re.sub(r"https?://\S+", "link", text)
    speech_text = re.sub(r"[*_`#~|•\t]", " ", speech_text)
    speech_text = re.sub(r"\s+", " ", speech_text).strip()

    if not speech_text:
        return

    with tts_lock:
        # Layer 1: Windows SAPI via win32com (Native, instant, zero latency)
        if WIN32COM_AVAILABLE and win32com is not None:
            try:
                if pythoncom is not None:
                    pythoncom.CoInitialize()
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Rate = 0  # Standard conversational speed (-10 to +10)
                voice.Volume = 100
                voice.Speak(speech_text)
                return
            except Exception:
                pass

        # Layer 2: pyttsx3 engine
        if pyttsx3 is not None:
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 175)
                engine.setProperty("volume", 1.0)
                engine.say(speech_text)
                engine.runAndWait()
                return
            except Exception:
                pass

        # Layer 3: Native Windows PowerShell System.Speech Synthesizer fallback
        try:
            escaped = speech_text.replace("'", "''").replace('"', '`"')
            ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{escaped}')"
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                timeout=15,
            )
            return
        except Exception:
            pass


# =============================================================================
# FEATURE 1: PERSONAL PERSISTENT MEMORY SYSTEM (JSON)
# =============================================================================
MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.json")


def load_memory() -> Dict[str, Any]:
    """
    Safely loads memory from jarvis_memory.json.
    Automatically recreates the structure if corrupted or missing.
    """
    default_structure = {
        "facts": {},
        "statements": [],
        "updated_at": datetime.datetime.now().isoformat(),
    }

    if not os.path.isfile(MEMORY_FILE):
        return default_structure

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "facts" in data and "statements" in data:
                return data
    except Exception:
        pass

    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(default_structure, f, indent=2)
    except Exception:
        pass

    return default_structure


def save_memory(data: Dict[str, Any]) -> bool:
    """Safely saves memory dictionary to jarvis_memory.json."""
    try:
        data["updated_at"] = datetime.datetime.now().isoformat()
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def handle_remember(text: str) -> str:
    """
    Stores an explicit personal fact into memory.
    Handles various natural voice inputs:
    - 'remember that my name is Zeeshan'
    - 'remember my name is Zeeshan'
    - 'remember my name my name is Zeeshan'
    - 'remember that I am working on a data science project'
    - 'remember that my favorite programming language is Python'
    """
    # Clean leading command triggers
    fact_text = re.sub(
        r"^(?:please\s+|can\s+you\s+)?(?:remember\s+that|remember|save\s+in\s+memory(?:\s+that)?)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    fact_text = fact_text.rstrip(".").strip()

    if not fact_text:
        return "What would you like me to remember?"

    mem = load_memory()
    if "facts" not in mem:
        mem["facts"] = {}
    if "statements" not in mem:
        mem["statements"] = []

    # 1. Name: "my name is X" / "my name my name is X" / "i am X"
    name_match = re.search(r"(?:my name is|my name my name is|i am)\s+([A-Za-z\s]+)", fact_text, re.IGNORECASE)
    if name_match and "working" not in fact_text.lower():
        extracted_name = name_match.group(1).strip().title()
        # Clean trailing filler words
        extracted_name = re.sub(r"\b(please|thanks|thank you)\b", "", extracted_name, flags=re.IGNORECASE).strip()
        if extracted_name:
            mem["facts"]["name"] = extracted_name

    # 2. Project: "i am working on X" / "my project is X"
    proj_match = re.search(r"(?:i am working on|my project is|working on)\s+(?:a|an|the)?\s*([^,\.]+)", fact_text, re.IGNORECASE)
    if proj_match:
        mem["facts"]["project"] = proj_match.group(1).strip()

    # 3. Favorite [thing] is [value] / Favorite language is Python
    fav_match = re.search(r"my favorite\s+([a-zA-Z\s]+?)\s+is\s+([^,\.]+)", fact_text, re.IGNORECASE)
    if fav_match:
        key = f"favorite_{fav_match.group(1).strip().lower()}"
        mem["facts"][key] = fav_match.group(2).strip()

    # Store statement if not duplicate
    clean_statement = fact_text
    if clean_statement not in mem["statements"]:
        mem["statements"].append(clean_statement)

    save_memory(mem)
    return "I'll remember that."


def handle_memory_query(text: str) -> Optional[str]:
    """Retrieves information from personal memory."""
    t = text.lower().strip().rstrip("?.,!")
    mem = load_memory()
    facts = mem.get("facts", {})
    statements = mem.get("statements", [])

    # 1. "What do you remember about me?" / "What is in your memory?"
    if any(q in t for q in [
        "what do you remember about me", "what do you remember", "what is in your memory",
        "show my memory", "show memories", "list my memories", "list memories", "tell me what you remember"
    ]):
        if not statements and not facts:
            return "I don't have any stored memories about you yet. You can tell me by saying 'Remember that...'."
        
        items = []
        if "name" in facts:
            items.append(f"Your name is {facts['name']}.")
        if "project" in facts:
            items.append(f"You are working on {facts['project']}.")
        for k, v in facts.items():
            if k.startswith("favorite_"):
                subj = k.replace("favorite_", "")
                items.append(f"Your favorite {subj} is {v}.")
        for st in statements:
            formatted = f"You mentioned: {st}."
            if not any(facts.get(k, "") in st for k in ["name", "project"]):
                items.append(formatted)

        return "Here is what I remember about you: " + " ".join(items)

    # 2. Name questions
    if any(q in t for q in ["what is my name", "what's my name", "who am i", "do you know my name", "tell me my name"]):
        if "name" in facts:
            return f"Your name is {facts['name']}."
        for st in statements:
            if "name is" in st.lower():
                return f"According to my memory, {st}."

    # 3. Project questions
    if any(q in t for q in ["what project", "which project", "project am i working on", "what am i working on"]):
        if "project" in facts:
            return f"You are working on {facts['project']}."
        for st in statements:
            if "working on" in st.lower() or "project" in st.lower():
                return f"You are {st}."

    # 4. Favorite questions
    if "favorite" in t:
        fav_match = re.search(r"(?:what is|what's|tell me)\s+my favorite\s+([a-zA-Z\s]+)", t)
        if fav_match:
            subj = fav_match.group(1).strip().lower()
            key = f"favorite_{subj}"
            if key in facts:
                return f"Your favorite {subj} is {facts[key]}."
            for k, v in facts.items():
                if subj in k or k.replace("favorite_", "") in subj:
                    return f"Your favorite {k.replace('favorite_', '')} is {v}."

    return None


def handle_forget(text: str) -> str:
    """Removes a specific memory fact."""
    t = re.sub(r"^(?:please\s+)?(?:forget\s+that|forget|delete\s+memory(?:\s+of)?)\s+", "", text, flags=re.IGNORECASE).strip().rstrip(".").lower()
    mem = load_memory()
    removed = False

    for k in list(mem.get("facts", {}).keys()):
        if k in t or mem["facts"][k].lower() in t:
            del mem["facts"][k]
            removed = True

    new_statements = []
    for st in mem.get("statements", []):
        if t in st.lower() or any(w in st.lower() for w in t.split() if len(w) > 3):
            removed = True
        else:
            new_statements.append(st)
    mem["statements"] = new_statements

    if removed:
        save_memory(mem)
        return "I have removed that from my memory."
    return "I couldn't find a matching memory to remove."


# =============================================================================
# FEATURE 12: CONFIRMATION SYSTEM
# =============================================================================
PENDING_CONFIRMATION: Optional[Dict[str, Any]] = None


def check_confirmation(raw_input: str) -> Optional[Tuple[str, bool]]:
    """
    Checks if there is a pending confirmation action.
    Returns (response_text, should_exit) if handled, or None to continue routing.
    """
    global PENDING_CONFIRMATION
    if not PENDING_CONFIRMATION:
        return None

    cleaned = raw_input.lower().strip().rstrip(".,!")
    action = PENDING_CONFIRMATION.get("action")

    if cleaned in ["yes", "y", "confirm", "sure", "proceed", "do it", "yeah", "yep", "ok", "okay"]:
        PENDING_CONFIRMATION = None
        if action == "clear_memory":
            default_mem = {
                "facts": {},
                "statements": [],
                "updated_at": datetime.datetime.now().isoformat(),
            }
            save_memory(default_mem)
            return "All stored memories have been permanently cleared.", False
        return "Action confirmed and executed.", False

    elif cleaned in ["no", "n", "cancel", "stop", "nevermind", "abort", "don't", "nope"]:
        PENDING_CONFIRMATION = None
        return "Operation cancelled. Your data remains unchanged.", False

    return "Please confirm with 'yes' to proceed or 'no' to cancel.", False


# =============================================================================
# FEATURE 2: SAFE APPLICATION CONTROL
# =============================================================================
SAFE_APP_MAP = {
    "whatsapp": {
        "uri": "whatsapp:",
        "cmd": "whatsapp",
        "name": "WhatsApp",
        "web": "https://web.whatsapp.com",
    },
    "spotify": {
        "uri": "spotify:",
        "cmd": "spotify",
        "name": "Spotify",
        "web": "https://open.spotify.com",
    },
    "discord": {
        "uri": "discord:",
        "cmd": "discord",
        "name": "Discord",
        "web": "https://discord.com/app",
    },
    "telegram": {
        "uri": "tg:",
        "cmd": "telegram",
        "name": "Telegram",
        "web": "https://web.telegram.org",
    },
    "chrome": {"cmd": "chrome", "name": "Google Chrome"},
    "google chrome": {"cmd": "chrome", "name": "Google Chrome"},
    "vs code": {"cmd": "code", "name": "Visual Studio Code"},
    "vscode": {"cmd": "code", "name": "Visual Studio Code"},
    "code": {"cmd": "code", "name": "Visual Studio Code"},
    "notepad": {"cmd": "notepad.exe", "name": "Notepad"},
    "calculator": {"cmd": "calc.exe", "name": "Calculator"},
    "calc": {"cmd": "calc.exe", "name": "Calculator"},
    "file explorer": {"cmd": "explorer.exe", "name": "File Explorer"},
    "explorer": {"cmd": "explorer.exe", "name": "File Explorer"},
    "microsoft edge": {"cmd": "msedge", "name": "Microsoft Edge"},
    "edge": {"cmd": "msedge", "name": "Microsoft Edge"},
    "task manager": {"cmd": "taskmgr.exe", "name": "Task Manager"},
    "paint": {"cmd": "mspaint.exe", "name": "Paint"},
    "cmd": {"cmd": "cmd.exe", "name": "Command Prompt"},
    "command prompt": {"cmd": "cmd.exe", "name": "Command Prompt"},
    "terminal": {"cmd": "wt.exe", "name": "Windows Terminal"},
    "powershell": {"cmd": "powershell.exe", "name": "PowerShell"},
    "settings": {"uri": "ms-settings:", "name": "Windows Settings"},
    "windows settings": {"uri": "ms-settings:", "name": "Windows Settings"},
    "word": {"cmd": "winword.exe", "name": "Microsoft Word"},
    "excel": {"cmd": "excel.exe", "name": "Microsoft Excel"},
    "powerpoint": {"cmd": "powerpnt.exe", "name": "Microsoft PowerPoint"},
}

KNOWN_APP_PATHS = {
    "chrome": [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ],
    "msedge": [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ],
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\WindowsApps\Spotify.exe"),
    ],
    "whatsapp": [
        os.path.expandvars(r"%LocalAppData%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%ProgramFiles%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\WindowsApps\WhatsApp.exe"),
    ],
    "discord": [
        os.path.expandvars(r"%LocalAppData%\Discord\Update.exe --processStart Discord.exe"),
    ],
    "code": [
        os.path.expandvars(r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\Code.exe"),
    ],
}


def handle_open_app(query: str) -> Tuple[bool, str]:
    """Safely launches predefined Windows applications or Windows URI schemes."""
    q = query.lower().strip()

    for key, app_data in SAFE_APP_MAP.items():
        pattern = rf"\b(?:open|launch|start)?\s*{re.escape(key)}\b"
        if re.search(pattern, q):
            name = app_data.get("name", key.title())

            # 1. Try URI scheme if defined (e.g. whatsapp:, spotify:, ms-settings:)
            if "uri" in app_data:
                try:
                    os.system(f"start {app_data['uri']}")
                    return True, f"Opening {name}."
                except Exception:
                    pass

            # 2. Try PATH binary
            cmd = app_data.get("cmd")
            if cmd and shutil.which(cmd):
                try:
                    subprocess.Popen([cmd], shell=True)
                    return True, f"Opening {name}."
                except Exception as e:
                    return True, f"Failed to launch {name}: {e}"

            # 3. Try known absolute installation paths
            if key in KNOWN_APP_PATHS:
                for path in KNOWN_APP_PATHS[key]:
                    if os.path.exists(path.split(" --")[0]):
                        try:
                            os.startfile(path)
                            return True, f"Opening {name}."
                        except Exception as e:
                            return True, f"Failed to start {name}: {e}"

            # 4. Try direct command with startfile
            if cmd:
                try:
                    os.startfile(cmd)
                    return True, f"Opening {name}."
                except Exception:
                    pass

            # 5. Fallback to Web version if available (e.g. WhatsApp Web / Spotify Web)
            if "web" in app_data:
                try:
                    webbrowser.open(app_data["web"])
                    return True, f"Opening {name} Web in your browser."
                except Exception:
                    pass

            return True, f"I couldn't find {name} installed on your system."

    # Catch-all for generic 'open [app]' phrase
    open_match = re.search(r"\b(?:open|launch|start)\s+([a-zA-Z0-9_\-]+)\b", q)
    if open_match:
        app_name = open_match.group(1).strip()
        if app_name not in ["the", "my", "a", "an", "folder", "file", "time", "date", "cpu", "ram", "memory"]:
            # Try PATH
            if shutil.which(app_name):
                try:
                    subprocess.Popen([app_name], shell=True)
                    return True, f"Opening {app_name.title()}."
                except Exception:
                    pass
            # Try Windows URI protocol: start app_name:
            try:
                ret = os.system(f"start {app_name}: 2>nul")
                if ret == 0:
                    return True, f"Opening {app_name.title()}."
            except Exception:
                pass

            return True, f"I couldn't find {app_name.title()} installed on your system."

    return False, ""


# =============================================================================
# FEATURE 3: SAFE FOLDER CONTROL
# =============================================================================
def get_user_directories() -> Dict[str, str]:
    """Returns safe standard Windows user directories."""
    user_home = os.path.expanduser("~")
    return {
        "downloads": os.path.join(user_home, "Downloads"),
        "documents": os.path.join(user_home, "Documents"),
        "pictures": os.path.join(user_home, "Pictures"),
        "desktop": os.path.join(user_home, "Desktop"),
        "music": os.path.join(user_home, "Music"),
        "videos": os.path.join(user_home, "Videos"),
    }


def handle_open_folder(query: str) -> Tuple[bool, str]:
    """Opens safe standard user folders in Windows File Explorer."""
    folders = get_user_directories()
    q = query.lower()

    for name, path in folders.items():
        pattern = rf"\b(?:open|show|explore)\s+(?:my\s+)?{name}(?:\s+folder)?\b"
        if re.search(pattern, q):
            if os.path.exists(path):
                try:
                    os.startfile(path)
                    return True, f"Opening {name.title()}."
                except Exception as e:
                    return True, f"Could not open {name.title()}: {e}"
            else:
                return True, f"{name.title()} directory not found."

    return False, ""


# =============================================================================
# FEATURE 4: VOLUME CONTROL
# =============================================================================
def handle_volume_control(query: str) -> Tuple[bool, str]:
    """Controls system volume (Increase, Decrease, Mute, Unmute, Set %)."""
    q = query.lower()

    # 1. Mute / Unmute
    if "mute" in q or "unmute" in q:
        try:
            ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
            return True, "Volume muted or unmuted."
        except Exception as e:
            return True, f"Failed to toggle volume mute: {e}"

    # 2. Increase volume
    if any(p in q for p in ["increase volume", "volume up", "turn up volume", "raise volume", "louder"]):
        try:
            for _ in range(5):
                ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
            return True, "Volume increased."
        except Exception as e:
            return True, f"Failed to increase volume: {e}"

    # 3. Decrease volume
    if any(p in q for p in ["decrease volume", "volume down", "lower volume", "turn down volume", "softer"]):
        try:
            for _ in range(5):
                ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
            return True, "Volume decreased."
        except Exception as e:
            return True, f"Failed to decrease volume: {e}"

    # 4. Set volume to X percent
    set_match = re.search(r"set\s+volume\s+to\s+(\d+)(?:\s*percent|\s*%)?", q)
    if set_match:
        percent = int(set_match.group(1))
        percent = max(0, min(100, percent))

        if PYCAW_AVAILABLE:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
                return True, f"Volume set to {percent} percent."
            except Exception:
                pass

        try:
            for _ in range(50):
                ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
            steps = int(percent / 2)
            for _ in range(steps):
                ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
            return True, f"Volume adjusted to approximately {percent} percent."
        except Exception as e:
            return True, f"Could not set volume: {e}"

    return False, ""


# =============================================================================
# FEATURE 5: SAFE FILE SEARCH
# =============================================================================
def handle_file_search(query: str) -> Tuple[bool, str]:
    """
    Searches for files in safe user directories (Desktop, Documents, Downloads, Pictures).
    Examples:
    - 'Find my Python files'
    - 'Find resume.pdf'
    - 'Find files named project'
    - 'Search my Downloads for CSV files'
    """
    q = query.lower()
    search_triggers = ["find", "search for file", "search for files", "search my", "locate file", "where is my file"]
    if not any(q.startswith(trig) or f" {trig} " in f" {q} " for trig in search_triggers):
        return False, ""

    user_dirs = get_user_directories()
    search_roots = [user_dirs["desktop"], user_dirs["documents"], user_dirs["downloads"], user_dirs["pictures"]]

    if "download" in q:
        search_roots = [user_dirs["downloads"]]
    elif "document" in q:
        search_roots = [user_dirs["documents"]]
    elif "desktop" in q:
        search_roots = [user_dirs["desktop"]]
    elif "picture" in q:
        search_roots = [user_dirs["pictures"]]

    ext_map = {
        "python": "*.py",
        "py": "*.py",
        "csv": "*.csv",
        "pdf": "*.pdf",
        "text": "*.txt",
        "txt": "*.txt",
        "json": "*.json",
        "markdown": "*.md",
        "word": "*.docx",
        "excel": "*.xlsx",
    }

    target_pattern = None
    for name, pattern in ext_map.items():
        if f"{name} file" in q or f"{name} files" in q or q.endswith(f"for {name}"):
            target_pattern = pattern
            break

    if not target_pattern:
        named_match = re.search(
            r"(?:find|search(?:\s+my\s+\w+)?\s+for)\s+(?:files?\s+named\s+|file\s+|files\s+)?([a-zA-Z0-9_\-\.]+)",
            q,
        )
        if named_match:
            candidate = named_match.group(1).strip()
            if candidate and candidate not in ["files", "file", "my", "all"]:
                if candidate in ext_map:
                    target_pattern = ext_map[candidate]
                else:
                    target_pattern = f"*{candidate}*"

    if not target_pattern:
        return False, ""

    matched_files = []
    scanned_count = 0
    max_scan = 500

    for root_dir in search_roots:
        if not os.path.exists(root_dir):
            continue
        try:
            for root, dirs, files in os.walk(root_dir):
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d.lower() not in ["appdata", "node_modules", ".git", "venv", "__pycache__"]
                ]
                rel_path = os.path.relpath(root, root_dir)
                depth = len(rel_path.split(os.sep)) if rel_path != "." else 0
                if depth > 3:
                    dirs[:] = []
                    continue

                for f in files:
                    scanned_count += 1
                    if scanned_count > max_scan or len(matched_files) >= 5:
                        break

                    if target_pattern.startswith("*."):
                        ext_suffix = target_pattern[1:].lower()
                        if f.lower().endswith(ext_suffix):
                            matched_files.append(os.path.join(root, f))
                    else:
                        clean_target = target_pattern.replace("*", "").lower()
                        if clean_target in f.lower():
                            matched_files.append(os.path.join(root, f))

                if len(matched_files) >= 5 or scanned_count > max_scan:
                    break
        except Exception:
            continue

    if not matched_files:
        return True, f"I couldn't find any matching files for {target_pattern} in your user folders."

    count_str = f"I found {len(matched_files)} matching file{'s' if len(matched_files) > 1 else ''}:"
    result_lines = [count_str]
    for path in matched_files:
        result_lines.append(f"• {path}")

    return True, "\n".join(result_lines)


# =============================================================================
# FEATURE 6: READ TEXT FILES
# =============================================================================
SAFE_TEXT_EXTENSIONS = [".txt", ".csv", ".md", ".json", ".py", ".log", ".ini", ".env"]


def handle_read_file(query: str) -> Tuple[bool, str]:
    """
    Safely reads and summarizes text-based files.
    Example: 'Read my notes.txt' or 'Read file requirements.txt'
    """
    q = query.strip()
    match = re.search(r"\bread\s+(?:my\s+|the\s+|file\s+)?([a-zA-Z0-9_\-\.\/\\]+)", q, re.IGNORECASE)
    if not match:
        return False, ""

    filename = match.group(1).strip().rstrip(".,")
    if filename.lower() in ["time", "date", "screen", "news"]:
        return False, ""

    user_dirs = get_user_directories()
    candidate_paths = [
        os.path.abspath(filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(user_dirs["desktop"], filename),
        os.path.join(user_dirs["documents"], filename),
        os.path.join(user_dirs["downloads"], filename),
    ]

    target_path = None
    for p in candidate_paths:
        if os.path.isfile(p):
            target_path = p
            break

    if not target_path:
        for root_dir in [os.getcwd(), user_dirs["desktop"], user_dirs["documents"], user_dirs["downloads"]]:
            found = glob.glob(os.path.join(root_dir, f"*{filename}*"))
            if found and os.path.isfile(found[0]):
                target_path = found[0]
                break

    if not target_path:
        return True, f"I could not find the file '{filename}' in your project or user folders."

    _, ext = os.path.splitext(target_path)
    if ext.lower() not in SAFE_TEXT_EXTENSIONS:
        return True, f"For security reasons, I only read safe text-based files ({', '.join(SAFE_TEXT_EXTENSIONS)})."

    try:
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(3000)

        if not content.strip():
            return True, f"The file '{os.path.basename(target_path)}' is currently empty."

        if len(content) < 200:
            return True, f"Here is the content of {os.path.basename(target_path)}:\n{content.strip()}"

        summary_prompt = (
            f"Summarize the following contents of '{os.path.basename(target_path)}' in 2 concise, "
            f"professional sentences suitable for speech synthesis:\n\n{content}"
        )
        ai_summary = ask_ai(summary_prompt)
        if ai_summary and not ai_summary.startswith("I could not reach Gemini"):
            return True, f"Summary of {os.path.basename(target_path)}: {ai_summary}"

        excerpt = content[:250].strip().replace("\n", " ")
        return True, f"Read {os.path.basename(target_path)}: {excerpt}..."

    except Exception as e:
        return True, f"Failed to read file: {e}"


# =============================================================================
# FEATURE 8: SCREEN VISION (GEMINI VISION)
# =============================================================================
def handle_screen_vision() -> str:
    """Captures a temporary screenshot and analyzes what is visible using Gemini Vision."""
    if ImageGrab is None:
        return "Pillow library is required for screen vision. Please run pip install Pillow."

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "GEMINI_API_KEY is not configured in your .env file. Screen vision requires a valid Gemini API key."

    if genai is None:
        return "The google-genai library is not installed. Please run pip install google-genai."

    try:
        screenshot = ImageGrab.grab()
        screenshot.thumbnail((1280, 720))

        client = genai.Client(api_key=api_key)
        vision_prompt = (
            "Analyze the user's screen in 2 to 3 concise, natural, and polite sentences suitable for speech output. "
            "Identify the active application, editor, document, or webpage visible."
        )

        vision_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.5-flash-lite", "gemini-3.7-flash"]
        response = None
        last_err = None

        for model_name in vision_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[vision_prompt, screenshot],
                    config=types.GenerateContentConfig(
                        system_instruction=AI_SYSTEM_INSTRUCTION,
                        temperature=0.4,
                        max_output_tokens=250,
                    ),
                )
                if response and response.text:
                    break
            except Exception as err:
                last_err = err
                continue

        if response and response.text:
            cleaned = response.text.replace("**", "").replace("*", "").strip()
            return cleaned
        elif last_err:
            return f"Screen vision analysis encountered an issue: {last_err}"

        return "I took a look at your screen, but received an empty response."

    except Exception as e:
        return f"Failed to analyze screen: {e}"


# =============================================================================
# FEATURE 9: GEMINI AI BRAIN WITH ROLLING CONVERSATION MEMORY & USER MEMORY
# =============================================================================
class ChatBrain:
    """Maintains continuous 1-on-1 conversational memory with Google Gemini."""

    def __init__(self):
        self.chat_session = None
        self.client = None
        self.history: List[Dict[str, str]] = []
        self._initialize_chat()

    def _get_contextual_instruction(self) -> str:
        """Injects stored user memories into the system prompt."""
        mem = load_memory()
        facts = mem.get("facts", {})
        statements = mem.get("statements", [])

        memory_context = ""
        if facts or statements:
            items = []
            for k, v in facts.items():
                items.append(f"{k}: {v}")
            for st in statements[:5]:
                items.append(st)
            memory_context = f"\nUser Personal Context & Saved Memories:\n- " + "\n- ".join(items)

        return AI_SYSTEM_INSTRUCTION + memory_context

    def _initialize_chat(self):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or genai is None:
            return

        try:
            self.client = genai.Client(api_key=api_key)
            self.chat_session = self.client.chats.create(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(
                    system_instruction=self._get_contextual_instruction(),
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
                    self.history.append({"user": prompt, "assistant": cleaned_text})
                    if len(self.history) > 6:
                        self.history.pop(0)
                    return cleaned_text
            except Exception:
                self.chat_session = None

        # 2. Multi-model fallback
        try:
            client = genai.Client(api_key=api_key)
            models_to_try = [
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.7-flash",
            ]
            response = None
            last_err = None

            context_prompt = ""
            if self.history:
                recent = self.history[-3:]
                context_prompt = "Recent conversation context:\n" + "\n".join([f"User: {h['user']}\nJARVIS: {h['assistant']}" for h in recent]) + f"\n\nCurrent Query: {prompt}"
            else:
                context_prompt = prompt

            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=context_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=self._get_contextual_instruction(),
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
                self.history.append({"user": prompt, "assistant": cleaned_text})
                if len(self.history) > 6:
                    self.history.pop(0)
                return cleaned_text
            elif last_err:
                raise last_err
            return "I apologize, but I received an empty response from Gemini."
        except Exception as e:
            error_msg = str(e)
            if "API_KEY_INVALID" in error_msg or "invalid" in error_msg.lower():
                return "The configured GEMINI_API_KEY appears to be invalid. Please check your .env file."
            return f"I encountered an error connecting to Gemini AI: {error_msg}"


ai_brain = ChatBrain()


def ask_ai(prompt: str) -> str:
    """Queries the conversational AI brain."""
    return ai_brain.ask(prompt)


# =============================================================================
# SAFE MATHEMATICAL CALCULATOR (NO UNRESTRICTED EVAL)
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
        cleaned = re.sub(
            r"(\d+(?:\.\d+)?)\s*(?:percent|%)\s*(?:of)\s*(\d+(?:\.\d+)?)",
            r"((\1 / 100) * \2)",
            expression_str,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.replace("x", "*").replace("X", "*").replace("^", "**")
        sanitized = re.sub(r"[^0-9\+\-\*\/\%\(\)\.\s]", "", cleaned).strip()
        if not sanitized:
            return None

        parsed = ast.parse(sanitized, mode="eval")
        result = _safe_eval_ast(parsed)
        return result
    except Exception:
        return None


# =============================================================================
# LOCAL SYSTEM & WEB COMMAND HANDLERS
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
    return f"{time_greeting}. JARVIS V2 is online. How may I assist you?"


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


# =============================================================================
# FEATURE 14 & 15: HELP & STATUS COMMANDS
# =============================================================================
def handle_help() -> str:
    """Returns a clean overview of JARVIS capabilities."""
    return (
        "JARVIS can currently:\n"
        "• Answer questions & converse using Gemini AI\n"
        "• Open applications (Chrome, WhatsApp, VS Code, Spotify, etc.)\n"
        "• Open user folders (Downloads, Documents, Desktop, Pictures)\n"
        "• Search the web & open websites\n"
        "• Control system volume (Up, Down, Mute, Set %)\n"
        "• Check CPU and RAM performance\n"
        "• Search files in user folders\n"
        "• Read and summarize text files (.txt, .md, .py, .csv, .json)\n"
        "• Take screenshots & analyze your screen visually\n"
        "• Remember personal details & retrieve stored memories\n"
        "• Perform safe mathematical calculations"
    )


def handle_system_status() -> str:
    """Returns current comprehensive system & assistant status."""
    ai_status = "Connected" if os.environ.get("GEMINI_API_KEY") else "Offline (No API Key)"
    mic_status = "Ready" if sr is not None else "Keyboard Mode"
    speaker_status = "Ready (Windows SAPI)" if WIN32COM_AVAILABLE else ("Ready (pyttsx3)" if pyttsx3 else "Text-only")
    
    mem = load_memory()
    mem_count = len(mem.get("facts", {})) + len(mem.get("statements", []))
    memory_status = f"Ready ({mem_count} items stored)"

    cpu_str = f"{psutil.cpu_percent(interval=0.2)}%" if psutil else "N/A"
    ram_str = f"{psutil.virtual_memory().percent}%" if psutil else "N/A"
    time_str = datetime.datetime.now().strftime("%I:%M %p")

    status_report = (
        "JARVIS STATUS\n"
        f"AI: {ai_status}\n"
        f"Microphone: {mic_status}\n"
        f"Speaker: {speaker_status}\n"
        f"Memory: {memory_status}\n"
        f"CPU: {cpu_str}\n"
        f"RAM: {ram_str}\n"
        f"Current time: {time_str}"
    )
    return status_report


# =============================================================================
# WEB & SCREENSHOT HANDLERS
# =============================================================================
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


def handle_search_web(query: str) -> Tuple[bool, str]:
    """Extracts search query and opens Google search in default browser."""
    patterns = [
        r"search\s+the\s+web\s+for\s+(.+)",
        r"search\s+google\s+for\s+(.+)",
        r"search\s+for\s+(.+)",
        r"google\s+(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            search_term = match.group(1).strip()
            search_term = re.sub(r"[\s,\.\!\?]+$", "", search_term)
            if search_term:
                url = f"https://www.google.com/search?q={search_term.replace(' ', '+')}"
                try:
                    webbrowser.open(url)
                    return True, f"Searching the web for {search_term} in your browser."
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
        os.makedirs(screenshots_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)

        screenshot = ImageGrab.grab()
        screenshot.save(filepath)

        return f"Screenshot taken successfully and saved to {filepath}."
    except Exception as e:
        return f"Failed to capture screenshot: {e}"


# =============================================================================
# FEATURE 11: COMMAND PRIORITY ROUTER
# =============================================================================
def strip_wake_word(text: str) -> str:
    """Cleans and removes wake words ('Jarvis', 'Hey Jarvis') from text."""
    if not text:
        return ""
    
    cleaned = text.strip()
    cleaned = re.sub(r"\b(?:hey\s+|ok\s+|okay\s+)?jarvis\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[\s,\.\!\?]+", "", cleaned)
    cleaned = re.sub(r"[\s,\.\!\?]+$", "", cleaned).strip()
    return cleaned


def is_exit_command(text: str) -> bool:
    """Checks if the user requested to exit or go offline."""
    t = text.lower().strip().rstrip(".,!")
    exit_patterns = [
        r"\b(?:go\s+)?offline\b",
        r"\b(?:go\s+to\s+)?sleep\b",
        r"\bshut\s*down\b",
        r"\bturn\s*off\b",
        r"\bexit\b",
        r"\bquit\b",
        r"\bgoodbye\b",
        r"\bbye\b",
        r"\bterminate\b",
        r"\bclose\s+jarvis\b",
        r"\bstop\s+jarvis\b",
    ]
    return any(re.search(pat, t) for pat in exit_patterns)


def route_command(raw_input: str) -> Tuple[str, bool]:
    """
    Main V2 command priority routing pipeline:
    1. Normalize text & strip wake word
    2. Check pending confirmation state
    3. Check exit / offline commands
    4. Check help & system status commands
    5. Check screen vision
    6. Check volume control
    7. Check local commands (time, date, CPU, RAM, OS, screenshot)
    8. Check memory commands (remember, recall, forget, clear)
    9. Check file search & read text files
    10. Check folder control (Downloads, Documents, etc.)
    11. Check web search & website opening
    12. Check application control (Chrome, WhatsApp, VS Code, Spotify, etc.)
    13. Check safe mathematical calculator
    14. Fallback to Gemini AI Brain with rolling session history and personal memory context
    Returns (response_text, should_exit)
    """
    global PENDING_CONFIRMATION

    if not raw_input or not raw_input.strip():
        return "", False

    # 1. Pending Confirmation State
    conf_result = check_confirmation(raw_input)
    if conf_result is not None:
        return conf_result

    # 2. Check exit on raw input before and after wake word stripping
    if is_exit_command(raw_input):
        return "Goodbye. JARVIS going offline.", True

    prompt = strip_wake_word(raw_input)
    prompt_lower = prompt.lower().strip()

    if not prompt_lower:
        return "Yes, I am listening. How can I assist you?", False

    if is_exit_command(prompt):
        return "Goodbye. JARVIS going offline.", True

    # 3. Conversational Greetings
    if prompt_lower in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]:
        return "Hello. How can I help you?", False

    if "who created you" in prompt_lower or "who made you" in prompt_lower:
        return "I am J.A.R.V.I.S V2, your personal AI desktop assistant, created by you.", False

    # 4. Help & Status Commands
    if prompt_lower in ["help", "what can you do", "show commands", "commands"]:
        return handle_help(), False

    if any(p in prompt_lower for p in ["system status", "status report", "jarvis status", "about system status", "tell me about system status"]):
        return handle_system_status(), False

    # 5. Screen Vision
    if any(p in prompt_lower for p in ["look at my screen", "what is on my screen", "analyze my screen", "describe my screen"]):
        return handle_screen_vision(), False

    # 6. Volume Control
    handled_vol, vol_resp = handle_volume_control(prompt_lower)
    if handled_vol:
        return vol_resp, False

    # 7. Time and Date
    if "time" in prompt_lower and any(w in prompt_lower for w in ["what", "tell", "current"]):
        return handle_time(), False

    if ("date" in prompt_lower or "today" in prompt_lower) and any(w in prompt_lower for w in ["what", "tell", "current"]):
        return handle_date(), False

    # 8. System Diagnostics (CPU, RAM, OS)
    if "cpu" in prompt_lower:
        return handle_system_info("cpu"), False

    if "ram" in prompt_lower and not ("program" in prompt_lower or "frame" in prompt_lower):
        return handle_system_info("ram"), False

    if any(p in prompt_lower for p in ["operating system", "what os", "which os"]):
        return handle_system_info("os"), False

    # 9. Screenshot
    if "screenshot" in prompt_lower or "screen capture" in prompt_lower:
        return handle_screenshot(), False

    # 10. Memory Commands
    if re.search(r"\b(?:clear|reset|erase|wipe)\s+(?:all\s+)?(?:of\s+)?(?:my\s+)?(?:stored\s+)?(?:memor(?:y|ies))\b", prompt_lower) or "forget everything" in prompt_lower:
        PENDING_CONFIRMATION = {"action": "clear_memory"}
        return "This will permanently remove all stored memories. Are you sure?", False

    if prompt_lower.startswith("forget that") or prompt_lower.startswith("forget "):
        return handle_forget(prompt), False

    if (
        prompt_lower.startswith("remember")
        or "remember that" in prompt_lower
        or "remember my name" in prompt_lower
        or "save in memory" in prompt_lower
    ):
        return handle_remember(prompt), False

    mem_resp = handle_memory_query(prompt)
    if mem_resp:
        return mem_resp, False

    # 11. Read Text Files
    handled_read, read_resp = handle_read_file(prompt)
    if handled_read:
        return read_resp, False

    # 12. File Search
    handled_file_search, search_file_resp = handle_file_search(prompt)
    if handled_file_search:
        return search_file_resp, False

    # 13. Folder Control
    if "open" in prompt_lower or "launch" in prompt_lower or "explore" in prompt_lower:
        handled_folder, folder_resp = handle_open_folder(prompt_lower)
        if handled_folder:
            return folder_resp, False

    # 14. Web Search
    handled_search, search_resp = handle_search_web(prompt)
    if handled_search:
        return search_resp, False

    # 15. Open Websites
    if "open" in prompt_lower or "launch" in prompt_lower or "start" in prompt_lower:
        handled_web, web_resp = handle_open_website(prompt_lower)
        if handled_web:
            return web_resp, False

        # 16. Open Applications
        handled_app, app_resp = handle_open_app(prompt_lower)
        if handled_app:
            return app_resp, False

    # 17. Safe Calculator
    if "calculate" in prompt_lower or "percent of" in prompt_lower or re.search(r"what is \d+", prompt_lower):
        math_candidate = re.sub(r"^(calculate|what is|how much is)\s*", "", prompt_lower, flags=re.IGNORECASE)
        math_candidate = math_candidate.rstrip("?.").strip()
        result = safe_calculate(math_candidate)
        if result is not None:
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            return f"The result is {result}.", False

    # 18. Fallback to Gemini AI Brain
    ai_response = ask_ai(prompt)
    return ai_response, False


# =============================================================================
# VOICE & AUDIO INPUT PIPELINE
# =============================================================================
def record_with_sounddevice(
    fs: int = 16000,
    max_seconds: float = 12.0,
    silence_limit: float = 1.0,
    listen_timeout: float = 5.0,
) -> Optional[object]:
    """
    Captures voice from Windows default microphone using sounddevice.
    Maintains a rolling pre-speech ring buffer so initial words are never clipped.
    """
    if sd is None or np is None or sr is None:
        return None

    block_size = 1024
    pre_buffer_size = 6
    pre_buffer = collections.deque(maxlen=pre_buffer_size)
    frames = []

    try:
        with sd.InputStream(samplerate=fs, channels=1, dtype="int16") as stream:
            ambient_energies = []
            for _ in range(max(1, int(fs / block_size * 0.2))):
                data, _ = stream.read(block_size)
                rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
                ambient_energies.append(rms)

            avg_ambient = float(np.mean(ambient_energies)) if ambient_energies else 30.0
            speech_threshold = max(avg_ambient * 1.3, 120.0)

            print("\nLISTENING... (Speak now or type command)")

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
                        frames.extend(list(pre_buffer))
                        silence_start = None
                    elif elapsed > listen_timeout:
                        return None
                else:
                    frames.append(data.copy())
                    if rms < speech_threshold:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= silence_limit:
                            break
                    else:
                        silence_start = None

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
    Captures voice input from the microphone or falls back cleanly to console text.
    """
    if recognizer is None or sr is None or mic_backend is None:
        try:
            user_text = input("You (type command): ").strip()
            return user_text
        except (EOFError, KeyboardInterrupt):
            return "exit"

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
# FEATURE 13: STARTUP EXPERIENCE & BANNER
# =============================================================================
def print_banner(ai_connected: bool, mic_ready: bool):
    """Displays the startup banner in the terminal matching V2 specifications."""
    ai_status = "CONNECTED" if ai_connected else "OFFLINE (Check .env)"
    voice_status = "READY" if mic_ready else "KEYBOARD MODE"

    banner = f"""
========================================
             J.A.R.V.I.S V2
         PERSONAL AI ASSISTANT
========================================
STATUS: ONLINE
AI: {ai_status}
VOICE: {voice_status}
MEMORY: READY
SYSTEM: READY
========================================
"""
    print(banner)


def detect_microphone_backend() -> Tuple[Optional[str], Optional[str]]:
    """Detects available microphone hardware and driver backend."""
    if sd is not None and np is not None:
        try:
            input_device = sd.default.device[0]
            if input_device is not None and input_device >= 0:
                device_info = sd.query_devices(input_device, "input")
                device_name = device_info.get("name", "Windows Audio Device")
                return "sounddevice", device_name
        except Exception:
            pass

    if sr is not None:
        try:
            with sr.Microphone():
                return "pyaudio", "PyAudio Device"
        except Exception:
            pass

    return None, None


def main():
    """Main execution loop for JARVIS V2."""
    recognizer = sr.Recognizer() if sr is not None else None
    mic_backend, mic_device_name = detect_microphone_backend()
    ai_connected = bool(os.environ.get("GEMINI_API_KEY"))

    print_banner(ai_connected=ai_connected, mic_ready=bool(mic_backend))

    if mic_backend:
        print(f"[Microphone: Ready ({mic_device_name})]")
    else:
        print("[Microphone: Not detected. Interactive keyboard input mode enabled]")

    startup_greeting = get_greeting()
    speak(startup_greeting)

    while True:
        try:
            raw_input = listen(recognizer, mic_backend)

            if not raw_input or not raw_input.strip():
                continue

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
