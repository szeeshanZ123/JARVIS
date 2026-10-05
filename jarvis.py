"""
=============================================================================
J.A.R.V.I.S - Personal AI Desktop Voice Assistant (V2.1)
=============================================================================
An intelligent, lightweight, and reliable personal desktop AI assistant
for Windows powered by Google Gemini AI with persistent memory, safe application
& folder launching, volume controls, recursive user file search, text file reading,
PDF extraction (via pypdf), screen vision, system monitoring, and natural voice.

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

# PDF text extraction
try:
    import pypdf
except ImportError:
    pypdf = None

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
# SYSTEM 1: REAL PERSISTENT MEMORY SYSTEM (jarvis_memory.json)
# =============================================================================
MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.json")


def load_memory() -> Dict[str, Any]:
    """
    Safely loads memory from jarvis_memory.json.
    Automatically creates/recreates the structure if corrupted or missing.
    Format:
    {
      "memories": [
        {"id": 1, "text": "My favorite language is Python", "created_at": "..."}
      ]
    }
    """
    default_structure: Dict[str, Any] = {"memories": []}

    if not os.path.isfile(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(default_structure, f, indent=2)
        except Exception:
            pass
        return default_structure

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "memories" in data and isinstance(data["memories"], list):
                return data
            # Migrate from older format if encountered
            if isinstance(data, dict) and "statements" in data:
                new_memories = []
                for i, st in enumerate(data.get("statements", []), 1):
                    new_memories.append({
                        "id": i,
                        "text": st,
                        "created_at": datetime.datetime.now().isoformat(),
                    })
                migrated = {"memories": new_memories}
                save_memory(migrated)
                return migrated
    except Exception:
        pass

    # Corrupted file recovery
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(default_structure, f, indent=2)
    except Exception:
        pass

    return default_structure


def save_memory(data: Dict[str, Any]) -> bool:
    """Safely writes memory dictionary to jarvis_memory.json on disk."""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def get_memory_count() -> int:
    """Returns the total number of stored persistent memories."""
    mem_data = load_memory()
    return len(mem_data.get("memories", []))


def handle_remember(raw_text: str) -> str:
    """
    Extracts and stores an explicit personal memory into jarvis_memory.json on disk.
    Examples:
    - 'Remember that my favorite language is Python.'
    - 'Remember that my main project is Vision Lens.'
    - 'Remember my favorite color is blue.'
    - 'Remember that I live in New York.'
    """
    # Clean leading trigger phrases
    fact_text = re.sub(
        r"^(?:please\s+|can\s+you\s+)?(?:remember\s+that|remember|save\s+in\s+memory(?:\s+that)?|save\s+to\s+memory(?:\s+that)?)\s+",
        "",
        raw_text,
        flags=re.IGNORECASE,
    ).strip()
    fact_text = fact_text.rstrip(".").strip()

    if not fact_text:
        return "What would you like me to remember?"

    mem_data = load_memory()
    memories = mem_data.get("memories", [])

    # Check for duplicate
    for m in memories:
        if m.get("text", "").lower() == fact_text.lower():
            return "I already have that saved in my memory."

    # Compute next ID
    next_id = 1
    if memories:
        existing_ids = [m.get("id", 0) for m in memories if isinstance(m.get("id"), int)]
        next_id = max(existing_ids) + 1 if existing_ids else len(memories) + 1

    new_entry = {
        "id": next_id,
        "text": fact_text,
        "created_at": datetime.datetime.now().isoformat(),
    }
    memories.append(new_entry)
    mem_data["memories"] = memories

    if save_memory(mem_data):
        return "I've saved that to my memory."
    return "I couldn't write to memory storage at the moment."


def handle_memory_query(query: str) -> Optional[str]:
    """
    Retrieves stored memories from jarvis_memory.json.
    Supports general recall ('What do you remember about me?') and targeted questions
    ('What is my favorite language?', 'What is my main project?').
    """
    t = query.lower().strip().rstrip("?.,!")
    mem_data = load_memory()
    memories = mem_data.get("memories", [])

    # 1. General memory recall
    general_recall_triggers = [
        "what do you remember about me",
        "what do you remember",
        "what is in your memory",
        "what's in your memory",
        "show my memory",
        "show memories",
        "list my memories",
        "list memories",
        "tell me what you remember",
        "check your memory",
    ]
    if any(q == t or q in t for q in general_recall_triggers):
        if not memories:
            return "I don't have any stored memories about you yet. You can tell me by saying 'Remember that...'."
        
        mem_lines = [f"• {m['text']}" for m in memories]
        return "Here is what I have saved in my memory:\n" + "\n".join(mem_lines)

    # 2. Targeted memory retrieval questions
    if not memories:
        return None

    # Fast direct substring/keyword matching on stored memory texts
    keywords = [w for w in re.findall(r"\b\w+\b", t) if w not in ["what", "is", "my", "the", "a", "an", "do", "you", "know", "tell", "me", "about", "which"]]
    
    # Try direct keyword matching
    for m in memories:
        m_text = m.get("text", "")
        m_text_lower = m_text.lower()
        
        # Exact keyword overlap check
        if all(kw in m_text_lower for kw in keywords if len(kw) > 2) and len(keywords) >= 2:
            return f"According to my memory, {m_text}."

    # If Gemini is available, query Gemini using local JSON memory as source of truth
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key and genai is not None:
        try:
            memories_formatted = "\n".join([f"- {m['text']}" for m in memories])
            prompt = (
                f"You are JARVIS. Answer the user's question strictly using ONLY the following saved personal memories:\n"
                f"{memories_formatted}\n\n"
                f"User Question: {query}\n\n"
                f"If the answer is found in the memories, provide a direct, concise, natural 1-sentence answer suitable for speech output. "
                f"If the answer is NOT mentioned anywhere in the memories, reply with exactly: 'MEMORY_NOT_FOUND'."
            )
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=100),
            )
            if resp and resp.text:
                cleaned = resp.text.replace("**", "").replace("*", "").strip()
                if "MEMORY_NOT_FOUND" not in cleaned:
                    return cleaned
        except Exception:
            pass

    return None


def handle_forget(raw_text: str) -> str:
    """
    Removes a matching memory entry from jarvis_memory.json.
    Example: 'Forget that my favorite language is Python.'
    """
    target = re.sub(
        r"^(?:please\s+|can\s+you\s+)?(?:forget\s+that|forget|delete\s+memory(?:\s+of)?|remove\s+memory(?:\s+of)?)\s+",
        "",
        raw_text,
        flags=re.IGNORECASE,
    ).strip().rstrip(".").lower()

    if not target:
        return "What memory would you like me to forget?"

    mem_data = load_memory()
    memories = mem_data.get("memories", [])
    initial_count = len(memories)

    # Filter out matching items
    new_memories = []
    for m in memories:
        m_text_lower = m.get("text", "").lower()
        if target in m_text_lower or m_text_lower in target:
            continue
        new_memories.append(m)

    if len(new_memories) < initial_count:
        mem_data["memories"] = new_memories
        save_memory(mem_data)
        return "I've removed that from my memory."

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
            default_mem: Dict[str, Any] = {"memories": []}
            save_memory(default_mem)
            return "All stored memories have been permanently cleared.", False
        return "Action confirmed and executed.", False

    elif cleaned in ["no", "n", "cancel", "stop", "nevermind", "abort", "don't", "nope"]:
        PENDING_CONFIRMATION = None
        return "Operation cancelled. Your data remains unchanged.", False

    return "Please confirm with 'yes' to proceed or 'no' to cancel.", False


# =============================================================================
# SMART CONTEXT & ENTITY EXTRACTION SYSTEM
# =============================================================================
class ConversationContext:
    """
    Maintains a lightweight, non-sticky conversation context object:
    - last_intent: e.g., 'OPEN_FOLDER', 'FILE_SEARCH', 'OPEN_WEBSITE', 'OPEN_APP'
    - last_location: e.g., 'Downloads', 'Desktop', 'Documents'
    - last_search_query: e.g., 'Week 4 video', 'resume'
    - last_found_files: list of full absolute file paths from the latest search
    - last_opened_file: file path of most recently opened file
    - last_opened_application: name of most recently launched application
    """
    def __init__(self):
        self.last_intent = None
        self.last_location = None
        self.last_search_query = None
        self.last_found_files = []
        self.last_opened_file = None
        self.last_opened_application = None
        self.last_action_time = time.time()

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.last_action_time = time.time()

    def clear(self):
        self.last_intent = None
        self.last_location = None
        self.last_search_query = None
        self.last_found_files = []
        self.last_opened_file = None
        self.last_opened_application = None


context = ConversationContext()


# =============================================================================
# SYSTEM 2: COMPREHENSIVE WINDOWS USER FILE SEARCH & LAUNCHER
# =============================================================================
def get_user_search_roots() -> List[str]:
    """
    Dynamically discovers all accessible user folders on Windows.
    Desktop, Documents, Downloads, Pictures, Videos, Music, and OneDrive (if present).
    Never hardcodes usernames.
    """
    user_home = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    standard_folders = ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music"]
    roots = []

    # Current working directory first for instant project files match
    cwd = os.getcwd()
    roots.append(cwd)

    for folder in standard_folders:
        path = os.path.join(user_home, folder)
        if os.path.isdir(path) and path not in roots:
            roots.append(path)

    # Check OneDrive
    onedrive_path = os.environ.get("OneDrive", os.path.join(user_home, "OneDrive"))
    if os.path.isdir(onedrive_path) and onedrive_path not in roots:
        roots.append(onedrive_path)
        for folder in ["Desktop", "Documents", "Pictures"]:
            sub = os.path.join(onedrive_path, folder)
            if os.path.isdir(sub) and sub not in roots:
                roots.append(sub)

    return roots


def search_user_files(
    query_term: str,
    target_ext: Optional[str] = None,
    specific_folder: Optional[str] = None,
    max_results: int = 10,
) -> List[str]:
    """
    Performs a fast, case-insensitive, recursive search across user folders.
    Skips system/hidden/temp folders.
    """
    search_roots = get_user_search_roots()
    if specific_folder:
        matched_roots = [r for r in search_roots if specific_folder.lower() in r.lower()]
        if matched_roots:
            search_roots = matched_roots

    matched_files: List[Tuple[int, str]] = []  # (score, path)
    scanned_count = 0
    max_scan = 1500
    cleaned_query = query_term.lower().strip()
    query_words = [
        w for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", cleaned_query)
        if w not in ["my", "the", "file", "files", "pdf", "txt", "csv", "doc", "docx", "video", "videos"]
    ]

    for root_dir in search_roots:
        if not os.path.exists(root_dir):
            continue
        try:
            for root, dirs, files in os.walk(root_dir):
                # Skip hidden/system directories
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d.lower() not in ["appdata", "node_modules", ".git", "venv", ".venv", "__pycache__", "$recycle.bin"]
                ]
                
                # Bounded search depth (max 4 levels below root)
                rel_path = os.path.relpath(root, root_dir)
                depth = len(rel_path.split(os.sep)) if rel_path != "." else 0
                if depth > 4:
                    dirs[:] = []
                    continue

                for f in files:
                    scanned_count += 1
                    if scanned_count > max_scan:
                        break

                    f_lower = f.lower()
                    
                    # Extension check
                    if target_ext:
                        if not f_lower.endswith(target_ext.lower()):
                            continue

                    # Keyword match check
                    if query_words:
                        if all(kw in f_lower for kw in query_words):
                            base_no_ext, _ = os.path.splitext(f_lower)
                            if base_no_ext == cleaned_query or f_lower == cleaned_query:
                                score = 4
                            elif f_lower.startswith(cleaned_query):
                                score = 3
                            else:
                                score = 2
                            matched_files.append((score, os.path.join(root, f)))
                    elif target_ext:
                        matched_files.append((1, os.path.join(root, f)))

                if scanned_count > max_scan or len(matched_files) >= max_results * 2:
                    break
        except Exception:
            continue

    # Deduplicate and sort by score & recency
    seen = set()
    unique_matches = []
    matched_files.sort(key=lambda x: x[0], reverse=True)

    for _, path in matched_files:
        norm = os.path.normcase(os.path.abspath(path))
        if norm not in seen and os.path.isfile(path):
            seen.add(norm)
            unique_matches.append(path)
            if len(unique_matches) >= max_results:
                break

    return unique_matches


def extract_search_target(query: str, current_context: Optional[ConversationContext] = None) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Extracts search term, target extension, and specific folder from natural phrasing.
    Understands:
    - Explicit folders: 'in Downloads', 'on Desktop', 'in Documents', etc.
    - Contextual location references: 'there', 'in that folder' -> uses context.last_location.
    - Extensions: '.pdf', '.txt', '.csv', '.py', 'video', 'pdf files', 'word document'.
    """
    q = query.strip()
    q_lower = q.lower()
    
    # 1. Check for explicit folder
    specific_folder = None
    folder_keywords = ["downloads", "documents", "desktop", "pictures", "videos", "music", "onedrive"]
    for fld in folder_keywords:
        if (
            f"in {fld}" in q_lower
            or f"on {fld}" in q_lower
            or f"from {fld}" in q_lower
            or f"my {fld}" in q_lower
            or f"under {fld}" in q_lower
        ):
            specific_folder = fld.title()
            break

    # 2. Check for contextual reference 'there' or 'in that folder'
    if not specific_folder and current_context and current_context.last_location:
        if re.search(r"\b(?:there|in\s+there|in\s+that\s+folder|in\s+the\s+folder)\b", q_lower):
            specific_folder = current_context.last_location

    # 3. Check for explicit file with extension like 'test_notes.txt', 'GST_Assignment.pdf', 'Week 4.mp4'
    match_file = re.search(r"\b([a-zA-Z0-9_\-\s]+\.[a-zA-Z0-9]{2,4})\b", q)
    if match_file:
        full_name = match_file.group(1).strip()
        base, ext = os.path.splitext(full_name)
        return base, ext.lower(), specific_folder

    # 4. Extension mappings
    ext_map = {
        "pdf": ".pdf",
        "csv": ".csv",
        "python": ".py",
        "py": ".py",
        "text": ".txt",
        "txt": ".txt",
        "json": ".json",
        "excel": ".xlsx",
        "word": ".docx",
        "doc": ".docx",
        "docx": ".docx",
        "markdown": ".md",
        "md": ".md",
        "video": ".mp4",
        "videos": ".mp4",
        "audio": ".mp3",
        "image": ".png",
    }

    target_ext = None
    for name, ext in ext_map.items():
        if (
            f"{name} file" in q_lower
            or f"{name} files" in q_lower
            or q_lower.endswith(f" {name}")
            or f" {name} in " in f" {q_lower} "
            or f" {name} on " in f" {q_lower} "
        ):
            target_ext = ext
            break

    # 5. Clean query text
    clean_text = re.sub(
        r"^(?:jarvis\s+|hey\s+jarvis\s+|please\s+|can\s+you\s+)?(?:find(?:\s+me)?|search(?:\s+for)?|where\s+is|locate|open|read|summarize)\s+(?:my\s+|the\s+|file\s+|files\s+)?",
        "",
        q,
        flags=re.IGNORECASE,
    ).strip()
    
    clean_text = re.sub(r"\b(?:in|on|from|under)\s+(?:my\s+)?(?:downloads|documents|desktop|pictures|videos|music|onedrive|that\s+folder)\b", "", clean_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r"\b(?:there|in\s+there)\b", "", clean_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r"\b(?:files?|pdf|txt|csv|docx?)\b", "", clean_text, flags=re.IGNORECASE).strip()
    clean_text = clean_text.rstrip("?.,").strip()

    return clean_text, target_ext, specific_folder


def handle_file_search_command(raw_input: str) -> Tuple[bool, str]:
    """
    Handles natural file search queries with smart context awareness.
    """
    q = raw_input.lower().strip()

    # Distinguish from web/youtube search
    if any(q.startswith(x) or f" {x} " in f" {q} " for x in ["search the web", "search google", "search youtube", "google "]):
        return False, ""

    search_triggers = ["find", "search for", "search my", "search", "where is my", "where is the", "where is", "locate"]
    is_search = False
    for trig in search_triggers:
        if q.startswith(trig) or f" {trig} " in f" {q} ":
            is_search = True
            break

    if not is_search:
        return False, ""

    # For queries starting with "search":
    # It's a FILE search ONLY IF it mentions a file/document/location/extension explicitly or via context
    file_clues = [
        r"\b(?:in|on|from|under)\s+(?:downloads|documents|desktop|pictures|videos|music|onedrive)\b",
        r"\b(?:my\s+)?(?:downloads|documents|desktop|pictures|videos|music|onedrive)\b",
        r"\b(?:file|files|folder|folders|pdf|txt|csv|docx?|xlsx?|py|mp4|mp3|video|videos|assignment|resume|notes|code|script)\b",
        r"\b(?:there|in\s+there)\b",
        r"\.[a-zA-Z0-9]{2,4}\b",
    ]
    has_file_clue = any(re.search(pat, q) for pat in file_clues)
    is_explicit_file_verb = any(q.startswith(v) for v in ["find", "where is", "locate"])

    if not has_file_clue and not is_explicit_file_verb:
        return False, ""

    target_term, target_ext, specific_folder = extract_search_target(raw_input, context)

    if "there" in q and not specific_folder:
        return True, "Which location or folder did you mean by 'there'?"

    if not target_term and not target_ext:
        return True, "What file would you like me to search for?"

    if specific_folder:
        context.update(last_location=specific_folder)

    results = search_user_files(target_term, target_ext, specific_folder, max_results=10)

    context.update(
        last_intent="FILE_SEARCH",
        last_search_query=target_term or target_ext,
        last_found_files=results,
    )

    loc_desc = f" in {specific_folder}" if specific_folder else ""
    if not results:
        desc = f"'{target_term}'" if target_term else f"{target_ext} files"
        return True, f"I searched your user folders{loc_desc}, but couldn't find any matching files for {desc}."

    result_lines = [f"I found {len(results)} matching file{'s' if len(results) > 1 else ''}{loc_desc}:"]
    for i, path in enumerate(results, 1):
        result_lines.append(f"{i}. {path}")

    return True, "\n".join(result_lines)


def handle_open_found_file(raw_input: str) -> Tuple[bool, str]:
    """
    Searches for a requested user file by name or extension and opens it.
    Example: 'Open resume.pdf' or 'Open GST_Assignment.pdf'
    """
    q = raw_input.lower().strip()
    if not ("open" in q or "launch" in q):
        return False, ""

    # Don't intercept folders, apps, or websites
    folder_names = ["downloads", "documents", "desktop", "pictures", "music", "videos", "onedrive"]
    if any(f"{w} {fld}" in q for fld in folder_names for w in ["open", "launch"]):
        return False, ""
    if any(f"{w} {app}" in q for app in SAFE_APP_MAP for w in ["open", "launch"]):
        return False, ""
    if any(f"{w} {site}" in q for site in POPULAR_SITES for w in ["open", "launch"]):
        return False, ""

    target_term, target_ext, specific_folder = extract_search_target(raw_input, context)
    if not target_term and not target_ext:
        return False, ""

    results = search_user_files(target_term, target_ext, specific_folder, max_results=5)
    if not results:
        return True, f"I couldn't find '{target_term or target_ext}' in your user folders to open."

    best_match = results[0]
    try:
        os.startfile(best_match)
        filename = os.path.basename(best_match)
        context.update(last_intent="OPEN_FILE", last_opened_file=best_match, last_found_files=results)
        return True, f"Opening {filename} from {os.path.dirname(best_match)}."
    except Exception as e:
        return True, f"Failed to open {os.path.basename(best_match)}: {e}"


# =============================================================================
# SYSTEM 3: TXT & TEXT FILE READING AND SUMMARIZATION
# =============================================================================
SAFE_TEXT_EXTENSIONS = [".txt", ".csv", ".md", ".json", ".log", ".ini", ".env", ".xml", ".yaml", ".yml", ".py"]


def read_text_file(file_path: str, max_chars: int = 10000) -> Tuple[bool, str]:
    """
    Safely reads text from a text-based file on disk. Never executes code.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_chars)
        return True, content
    except Exception as e:
        return False, str(e)


def handle_read_txt_command(raw_input: str) -> Tuple[bool, str]:
    """
    Handles reading and summarizing text files.
    Example: 'Read my notes.txt' or 'Summarize my notes.txt' or 'Read requirements.txt'
    """
    q = raw_input.lower().strip()
    is_summarize = "summarize" in q or "summary" in q or "explain" in q
    is_read = "read" in q or is_summarize

    if not is_read or "pdf" in q:
        return False, ""

    target_term, target_ext, specific_folder = extract_search_target(raw_input, context)
    if not target_term and not target_ext:
        return False, ""

    # Look for matching text files
    candidates = search_user_files(target_term, target_ext or ".txt", specific_folder, max_results=3)
    if not candidates and not target_ext:
        candidates = search_user_files(target_term, None, specific_folder, max_results=3)
        candidates = [c for c in candidates if os.path.splitext(c)[1].lower() in SAFE_TEXT_EXTENSIONS]

    if not candidates:
        return True, f"I couldn't find the text file '{target_term}' in your project or user folders."

    target_path = candidates[0]
    filename = os.path.basename(target_path)
    _, ext = os.path.splitext(target_path)

    if ext.lower() not in SAFE_TEXT_EXTENSIONS:
        return True, f"For security reasons, I only read text documents ({', '.join(SAFE_TEXT_EXTENSIONS)}). I never execute binary or script files."

    context.update(last_intent="READ_FILE", last_found_files=[target_path])

    success, content = read_text_file(target_path)
    if not success:
        return True, f"Could not read {filename}: {content}"

    if not content.strip():
        return True, f"The file '{filename}' is currently empty."

    char_count = len(content)

    # Automatic summarization if requested or if long
    if is_summarize or char_count > 400:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if api_key and genai is not None:
            try:
                client = genai.Client(api_key=api_key)
                prompt = (
                    f"Provide a concise, professional 2-3 sentence summary of the following document '{filename}' "
                    f"suitable for speech synthesis:\n\n{content[:6000]}"
                )
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=250),
                )
                if resp and resp.text:
                    cleaned_summary = resp.text.replace("**", "").replace("*", "").strip()
                    return True, f"I found {filename} ({char_count:,} characters). Here is the summary:\n\n{cleaned_summary}"
            except Exception:
                pass

    if char_count <= 400:
        return True, f"Content of {filename}:\n\n{content.strip()}"

    excerpt = content[:300].strip().replace("\n", " ")
    return True, f"I found {filename}. It contains {char_count:,} characters:\n\n\"{excerpt}...\""


# =============================================================================
# SYSTEM 4: REAL PDF EXTRACTION & SUMMARIZATION (via pypdf)
# =============================================================================
def extract_pdf_text(pdf_path: str, max_pages: int = 25, max_chars: int = 12000) -> Tuple[bool, str, int]:
    """
    Extracts real text from a PDF file using pypdf.
    Returns (success, extracted_text, page_count).
    """
    if pypdf is None:
        return False, "The pypdf library is not installed. Please run: pip install pypdf", 0

    try:
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        pages_to_read = min(total_pages, max_pages)
        extracted_sections = []

        for i in range(pages_to_read):
            try:
                page_text = reader.pages[i].extract_text()
                if page_text and page_text.strip():
                    extracted_sections.append(page_text.strip())
            except Exception:
                continue

        full_text = "\n\n".join(extracted_sections).strip()
        return True, full_text[:max_chars], total_pages
    except Exception as e:
        return False, str(e), 0


def handle_read_pdf_command(raw_input: str) -> Tuple[bool, str]:
    """
    Locates, extracts text from, and summarizes PDF files.
    Examples:
    - 'Read my GST assignment PDF'
    - 'Summarize my GST assignment'
    - 'Find my resume PDF'
    - 'Read test.pdf'
    """
    q = raw_input.lower().strip()
    is_summarize = "summarize" in q or "summary" in q
    is_read = "read" in q or is_summarize or "extract" in q

    if not is_read and not ("pdf" in q and "find" not in q):
        return False, ""

    target_term, _, specific_folder = extract_search_target(raw_input, context)
    if not target_term:
        target_term = "pdf"

    candidates = search_user_files(target_term, ".pdf", specific_folder, max_results=3)
    if not candidates:
        return True, f"I couldn't find any PDF matching '{target_term}' in your user folders."

    pdf_path = candidates[0]
    filename = os.path.basename(pdf_path)
    context.update(last_intent="READ_PDF", last_found_files=[pdf_path])

    success, text, page_count = extract_pdf_text(pdf_path)
    if not success:
        return True, f"Error extracting text from {filename}: {text}"

    # Handle Scanned / Image-only PDFs
    if not text or not text.strip():
        return True, f"I found {filename} in {os.path.dirname(pdf_path)}, but it appears to be scanned or image-based. Text extraction wasn't available for this file."

    char_count = len(text)

    # Summarize with Gemini
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key and genai is not None:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are JARVIS. Provide a clear, professional 2-3 sentence summary of the following PDF document "
                f"'{filename}' ({page_count} pages) suitable for speech output:\n\n{text[:8000]}"
            )
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=300),
            )
            if resp and resp.text:
                summary = resp.text.replace("**", "").replace("*", "").strip()
                return True, f"I extracted {filename} ({page_count} page{'s' if page_count > 1 else ''}, {char_count:,} characters):\n\n{summary}"
        except Exception:
            pass

    excerpt = text[:350].strip().replace("\n", " ")
    return True, f"I extracted {filename} ({page_count} pages, {char_count:,} characters):\n\n\"{excerpt}...\""


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
        pattern = rf"\b(?:open|launch|start)\s+(?:the\s+)?{re.escape(key)}\b"
        if re.search(pattern, q):
            name = app_data.get("name", key.title())

            if "uri" in app_data:
                try:
                    os.system(f"start {app_data['uri']}")
                    context.update(last_intent="OPEN_APP", last_opened_application=name)
                    return True, f"Opening {name}."
                except Exception:
                    pass

            cmd = app_data.get("cmd")
            if cmd and shutil.which(cmd):
                try:
                    subprocess.Popen([cmd], shell=True)
                    context.update(last_intent="OPEN_APP", last_opened_application=name)
                    return True, f"Opening {name}."
                except Exception as e:
                    return True, f"Failed to launch {name}: {e}"

            if key in KNOWN_APP_PATHS:
                for path in KNOWN_APP_PATHS[key]:
                    if os.path.exists(path.split(" --")[0]):
                        try:
                            os.startfile(path)
                            context.update(last_intent="OPEN_APP", last_opened_application=name)
                            return True, f"Opening {name}."
                        except Exception as e:
                            return True, f"Failed to start {name}: {e}"

            if cmd:
                try:
                    os.startfile(cmd)
                    context.update(last_intent="OPEN_APP", last_opened_application=name)
                    return True, f"Opening {name}."
                except Exception:
                    pass

            if "web" in app_data:
                try:
                    webbrowser.open(app_data["web"])
                    context.update(last_intent="OPEN_APP", last_opened_application=name)
                    return True, f"Opening {name} Web in your browser."
                except Exception:
                    pass

            return True, f"I couldn't find {name} installed on your system."

    return False, ""


# =============================================================================
# FEATURE 3: SAFE FOLDER CONTROL
# =============================================================================
def get_user_directories() -> Dict[str, str]:
    """Returns safe standard Windows user directories."""
    user_home = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    return {
        "downloads": os.path.join(user_home, "Downloads"),
        "documents": os.path.join(user_home, "Documents"),
        "pictures": os.path.join(user_home, "Pictures"),
        "desktop": os.path.join(user_home, "Desktop"),
        "music": os.path.join(user_home, "Music"),
        "videos": os.path.join(user_home, "Videos"),
    }


def handle_open_folder(query: str) -> Tuple[bool, str]:
    """Opens safe standard user folders in Windows File Explorer and updates context."""
    folders = get_user_directories()
    q = query.lower().strip()

    for name, path in folders.items():
        pattern = rf"\b(?:open|show|explore|launch)\s+(?:my\s+)?{name}(?:\s+folder)?\b"
        if re.search(pattern, q):
            if os.path.exists(path):
                try:
                    os.startfile(path)
                    context.update(
                        last_intent="OPEN_FOLDER",
                        last_location=name.title(),
                        last_found_files=[],
                    )
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

    if "mute" in q or "unmute" in q:
        try:
            ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
            return True, "Volume muted or unmuted."
        except Exception as e:
            return True, f"Failed to toggle volume mute: {e}"

    if any(p in q for p in ["increase volume", "volume up", "turn up volume", "raise volume", "louder"]):
        try:
            for _ in range(5):
                ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
            return True, "Volume increased."
        except Exception as e:
            return True, f"Failed to increase volume: {e}"

    if any(p in q for p in ["decrease volume", "volume down", "lower volume", "turn down volume", "softer"]):
        try:
            for _ in range(5):
                ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
            return True, "Volume decreased."
        except Exception as e:
            return True, f"Failed to decrease volume: {e}"

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
        mem_data = load_memory()
        memories = mem_data.get("memories", [])

        memory_context = ""
        if memories:
            items = [f"- {m['text']}" for m in memories[:10]]
            memory_context = f"\nUser Personal Context & Saved Memories from jarvis_memory.json:\n" + "\n".join(items)

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

        # 1. Continuous chat session
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

        # 2. Fallback
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
        cleaned = expression_str.lower()
        cleaned = re.sub(r"\bmultiplied\s+by\b", "*", cleaned)
        cleaned = re.sub(r"\btimes\b", "*", cleaned)
        cleaned = re.sub(r"\bdivided\s+by\b", "/", cleaned)
        cleaned = re.sub(r"\bplus\b", "+", cleaned)
        cleaned = re.sub(r"\bminus\b", "-", cleaned)
        
        cleaned = re.sub(
            r"(\d+(?:\.\d+)?)\s*(?:percent|%)\s*(?:of)\s*(\d+(?:\.\d+)?)",
            r"((\1 / 100) * \2)",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.replace("x", "*").replace("^", "**")
        sanitized = re.sub(r"[^0-9\+\-\*/\%\(\)\.\s]", "", cleaned).strip()
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
        "• Remember & recall personal memories (jarvis_memory.json)\n"
        "• Search user files & open matching documents\n"
        "• Read and summarize text files (.txt, .md, .csv, .json)\n"
        "• Extract and summarize PDF documents (via pypdf)\n"
        "• Open applications (Chrome, WhatsApp, VS Code, Spotify, etc.)\n"
        "• Open user folders (Downloads, Documents, Desktop, Pictures)\n"
        "• Search the web & open websites\n"
        "• Control system volume (Up, Down, Mute, Set %)\n"
        "• Check CPU and RAM performance\n"
        "• Take screenshots & analyze your screen visually\n"
        "• Perform safe mathematical calculations"
    )


def handle_system_status() -> str:
    """Returns current comprehensive system & assistant status."""
    ai_status = "Connected" if os.environ.get("GEMINI_API_KEY") else "Offline (No API Key)"
    mic_status = "Ready" if sr is not None else "Keyboard Mode"
    speaker_status = "Ready (Windows SAPI)" if WIN32COM_AVAILABLE else ("Ready (pyttsx3)" if pyttsx3 else "Text-only")
    mem_count = get_memory_count()

    cpu_str = f"{psutil.cpu_percent(interval=0.2)}%" if psutil else "N/A"
    ram_str = f"{psutil.virtual_memory().percent}%" if psutil else "N/A"
    time_str = datetime.datetime.now().strftime("%I:%M %p")

    status_report = (
        "JARVIS STATUS\n"
        f"AI: {ai_status}\n"
        f"Microphone: {mic_status}\n"
        f"Speaker: {speaker_status}\n"
        f"Memory: Ready ({mem_count} items stored)\n"
        f"CPU: {cpu_str}\n"
        f"RAM: {ram_str}\n"
        f"Current time: {time_str}"
    )
    return status_report


# =============================================================================
# CONTEXTUAL ACTION HANDLERS & WEB HANDLERS
# =============================================================================
def handle_contextual_action(raw_input: str) -> Tuple[bool, str]:
    """
    Handles context-dependent requests referring to previously found files or results:
    - 'open it', 'open that', 'open the file', 'open the first one', 'open the second one'
    - 'show me the largest one', 'largest one'
    - 'read it', 'read that', 'read the first one'
    - 'summarize it', 'summarize that'
    """
    q = raw_input.lower().strip().rstrip(".,!?")

    # 1. Largest / Size ranking
    if "largest" in q or "biggest" in q:
        if not context.last_found_files:
            return True, "I don't have a list of search results to compare."
        
        valid_files = [f for f in context.last_found_files if os.path.isfile(f)]
        if not valid_files:
            return True, "The previous search results are no longer available on disk."
        
        largest_file = max(valid_files, key=lambda f: os.path.getsize(f))
        size_bytes = os.path.getsize(largest_file)
        size_str = f"{round(size_bytes / (1024 * 1024), 2)} MB" if size_bytes >= 1024 * 1024 else f"{round(size_bytes / 1024, 1)} KB"
        
        context.update(last_found_files=[largest_file])
        return True, f"The largest one is {os.path.basename(largest_file)} ({size_str}) located at {largest_file}."

    # 2. 'Open it / that / the first one / the second one'
    open_pronoun_patterns = [
        r"^open\s+(?:it|that|this|the\s+file|the\s+one\s+you\s+found|the\s+first\s+one|the\s+second\s+one|the\s+third\s+one|first\s+one|second\s+one)$",
        r"^launch\s+(?:it|that|this|the\s+file|the\s+first\s+one)$",
    ]
    if any(re.match(pat, q) for pat in open_pronoun_patterns) or q in ["open it", "open that", "open this", "open file", "open the file"]:
        if not context.last_found_files:
            return True, "I don't have a previously found file in my current context to open."
        
        idx = 0
        if "second" in q:
            idx = 1 if len(context.last_found_files) > 1 else 0
        elif "third" in q:
            idx = 2 if len(context.last_found_files) > 2 else 0

        target_file = context.last_found_files[idx]
        if not os.path.isfile(target_file):
            return True, f"I found the reference to {os.path.basename(target_file)}, but it is no longer at that location."

        try:
            os.startfile(target_file)
            filename = os.path.basename(target_file)
            context.update(last_intent="OPEN_FILE", last_opened_file=target_file)
            return True, f"Opening {filename}."
        except Exception as e:
            return True, f"Failed to open {os.path.basename(target_file)}: {e}"

    # 3. 'Read it / that / the first one'
    read_pronoun_patterns = [
        r"^(?:read|extract)\s+(?:it|that|this|the\s+file|the\s+first\s+one)$",
    ]
    if any(re.match(pat, q) for pat in read_pronoun_patterns) or q in ["read it", "read that", "read this", "read the file"]:
        if not context.last_found_files:
            return True, "I don't have a previously found document in my current context to read."
        
        target_file = context.last_found_files[0]
        _, ext = os.path.splitext(target_file)
        
        if ext.lower() == ".pdf":
            success, text, page_count = extract_pdf_text(target_file)
            if not success:
                return True, f"Failed to extract PDF: {text}"
            if not text.strip():
                return True, f"I found {os.path.basename(target_file)}, but it appears to be scanned or image-based. Text extraction wasn't available for this file."
            return True, f"I extracted {os.path.basename(target_file)} ({page_count} pages, {len(text):,} characters):\n\n\"{text[:350].strip()}...\""

        elif ext.lower() in SAFE_TEXT_EXTENSIONS:
            success, content = read_text_file(target_file)
            if not success:
                return True, f"Failed to read file: {content}"
            return True, f"Content of {os.path.basename(target_file)}:\n\n{content.strip()}"

        return True, f"I can only read text documents and PDF files, not {ext} files."

    # 4. 'Summarize it / that / the first one'
    summarize_pronoun_patterns = [
        r"^summarize\s+(?:it|that|this|the\s+file|the\s+first\s+one)$",
        r"^give\s+me\s+a\s+summary\s+of\s+(?:it|that|this)$",
    ]
    if any(re.match(pat, q) for pat in summarize_pronoun_patterns) or q in ["summarize it", "summarize that", "summarize this"]:
        if not context.last_found_files:
            return True, "I don't have a previously found document in my current context to summarize."
        
        target_file = context.last_found_files[0]
        _, ext = os.path.splitext(target_file)
        
        doc_text = ""
        filename = os.path.basename(target_file)
        
        if ext.lower() == ".pdf":
            success, text, _ = extract_pdf_text(target_file)
            if not success or not text.strip():
                return True, f"I could not extract text from {filename} to summarize."
            doc_text = text
        elif ext.lower() in SAFE_TEXT_EXTENSIONS:
            success, content = read_text_file(target_file)
            if not success or not content.strip():
                return True, f"I could not read {filename} to summarize."
            doc_text = content
        else:
            return True, f"Cannot summarize {ext} files."

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if api_key and genai is not None:
            try:
                client = genai.Client(api_key=api_key)
                prompt = f"Provide a concise, clear 2-3 sentence summary of the document '{filename}':\n\n{doc_text[:8000]}"
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=250),
                )
                if resp and resp.text:
                    summary = resp.text.replace("**", "").replace("*", "").strip()
                    return True, f"Here is the summary of {filename}:\n\n{summary}"
            except Exception as e:
                return True, f"Could not generate summary: {e}"

        return True, f"Summary preview of {filename}:\n\n\"{doc_text[:350].strip()}...\""

    return False, ""


POPULAR_SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "gmail": "https://mail.google.com",
    "chatgpt": "https://chatgpt.com",
    "reddit": "https://www.reddit.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "wikipedia": "https://www.wikipedia.org",
    "linkedin": "https://www.linkedin.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
}


def handle_open_website(query: str) -> Tuple[bool, str]:
    """
    Detects and opens websites cleanly.
    Recognizes:
    - 'open youtube', 'open youtube.com', 'go to youtube', 'launch youtube.com'
    - 'open google.com', 'open github', 'open chatgpt'
    - Custom domain formats like 'open example.com'
    """
    q = query.lower().strip()
    
    # 1. Match known website names
    for name, url in POPULAR_SITES.items():
        pattern = rf"\b(?:open|launch|go\s+to|start|visit|browse)?\s*{re.escape(name)}(?:\.com|\.org|\.io|\.net)?\b"
        if re.search(pattern, q):
            try:
                webbrowser.open(url)
                context.update(last_intent="OPEN_WEBSITE")
                return True, f"Opening {name.title()}."
            except Exception as e:
                return True, f"Could not open {name}: {e}"

    # 2. Match generic domain formats like 'open xyz.com', 'visit abc.org'
    match_domain = re.search(r"\b(?:open|launch|go\s+to|visit)\s+([a-zA-Z0-9\-]+\.[a-zA-Z]{2,6}(?:/[^\s]*)?)\b", q)
    if match_domain:
        domain = match_domain.group(1)
        url = f"https://{domain}" if not domain.startswith("http") else domain
        try:
            webbrowser.open(url)
            context.update(last_intent="OPEN_WEBSITE")
            return True, f"Opening {domain}."
        except Exception as e:
            return True, f"Could not open {domain}: {e}"

    return False, ""


def handle_search_web(query: str) -> Tuple[bool, str]:
    """
    Handles web search queries and YouTube searches in the default browser.
    Examples:
    - 'search YouTube for Week 4 video' -> searches YouTube
    - 'search the web for Python tutorial' -> searches Google
    - 'search Python tutorial' -> searches Google
    - 'google latest tech news' -> searches Google
    """
    q = query.strip()
    q_lower = q.lower()

    # 1. Search YouTube specifically
    yt_match = re.search(r"search\s+youtube\s+(?:for\s+)?(.+)", q_lower)
    if yt_match:
        term = yt_match.group(1).strip().rstrip("?.,!")
        if term:
            url = f"https://www.youtube.com/results?search_query={term.replace(' ', '+')}"
            try:
                webbrowser.open(url)
                return True, f"Searching YouTube for {term}."
            except Exception as e:
                return True, f"Failed to search YouTube: {e}"

    # 2. Search web / Google
    web_patterns = [
        r"search\s+the\s+web\s+(?:for\s+)?(.+)",
        r"search\s+google\s+(?:for\s+)?(.+)",
        r"^google\s+(.+)",
        r"^search\s+for\s+(.+)",
        r"^search\s+(.+)",
    ]

    for pattern in web_patterns:
        match = re.search(pattern, q_lower)
        if match:
            search_term = match.group(1).strip().rstrip("?.,!")
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
        pictures_dir = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Pictures")
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
# FEATURE 11: SMART CONTEXT COMMAND PRIORITY ROUTER
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
    Main V2.1 Smart Context Priority Routing Pipeline:
    1. Check pending confirmation state
    2. Check exit / offline commands
    3. Conversational Greetings
    4. Help & Status Commands
    5. Screen Vision
    6. Volume Control
    7. Time & Date
    8. System Diagnostics (CPU, RAM, OS)
    9. Screenshot
    10. Memory Commands (remember, recall, forget, clear)
    11. Contextual Action on previous result ('open it', 'read it', 'summarize it', 'largest one')
    12. Explicit Website Opening ('open youtube', 'open youtube.com', 'open github', etc.)
    13. Explicit Folder Opening ('open downloads', 'open desktop', 'open documents', etc.)
    14. Explicit Application Opening ('open vs code', 'open chrome', 'open spotify', etc.)
    15. PDF Reading & Extraction ('read GST assignment PDF', 'summarize GST assignment')
    16. TXT / Text Document Reading ('read notes.txt', 'summarize notes.txt')
    17. Open Specific File by Name ('open resume.pdf', 'open notes.txt')
    18. File Search across user folders ('find my resume on Desktop', 'search Week 4 video in Downloads', 'search Week 4 video there')
    19. Web Search ('search Python tutorial', 'search the web for ...', 'search YouTube for ...')
    20. Safe Mathematical Calculator ('what is 50 times 20', 'what is 25 multiplied by 40')
    21. Fallback to Gemini AI Brain with clean prompt and saved memory context
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

    if any(p in prompt_lower for p in ["system status", "status report", "jarvis status", "about system status", "tell me about system status", "status"]):
        return handle_system_status(), False

    # 5. Screen Vision
    if any(p in prompt_lower for p in ["look at my screen", "what is on my screen", "analyze my screen", "describe my screen"]):
        return handle_screen_vision(), False

    # 6. Volume Control
    handled_vol, vol_resp = handle_volume_control(prompt_lower)
    if handled_vol:
        return vol_resp, False

    # 7. Time and Date
    if re.search(r"\btime\b", prompt_lower) and not re.search(r"\b\d+\s+times\b|\btimes\s+\d+\b", prompt_lower) and any(w in prompt_lower for w in ["what", "tell", "current"]):
        return handle_time(), False

    if re.search(r"\b(?:date|today)\b", prompt_lower) and any(w in prompt_lower for w in ["what", "tell", "current"]):
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
        or "save in memory" in prompt_lower
        or "save to memory" in prompt_lower
    ):
        return handle_remember(prompt), False

    mem_resp = handle_memory_query(prompt)
    if mem_resp:
        return mem_resp, False

    # 11. Contextual Actions on previous result ('open it', 'read it', 'summarize it', 'largest one')
    handled_ctx, ctx_resp = handle_contextual_action(prompt)
    if handled_ctx:
        return ctx_resp, False

    # 12. Explicit Website Opening ('open youtube', 'open youtube.com', 'open github', etc.)
    handled_web, web_resp = handle_open_website(prompt_lower)
    if handled_web:
        return web_resp, False

    # 13. Explicit Folder Opening ('open downloads', 'open desktop', 'open documents', etc.)
    handled_folder, folder_resp = handle_open_folder(prompt_lower)
    if handled_folder:
        return folder_resp, False

    # 14. Explicit Application Opening ('open vs code', 'open chrome', 'open spotify', etc.)
    handled_app, app_resp = handle_open_app(prompt_lower)
    if handled_app:
        return app_resp, False

    # 15. PDF Reading & Extraction ('read GST assignment PDF', 'summarize GST assignment')
    if "pdf" in prompt_lower or ".pdf" in prompt_lower:
        handled_pdf, pdf_resp = handle_read_pdf_command(prompt)
        if handled_pdf:
            return pdf_resp, False

    # 16. TXT / Text Document Reading ('read notes.txt', 'summarize notes.txt')
    handled_read, read_resp = handle_read_txt_command(prompt)
    if handled_read:
        return read_resp, False

    # 17. Open Specific File by Name ('open resume.pdf', 'open notes.txt')
    handled_open_file, open_file_resp = handle_open_found_file(prompt)
    if handled_open_file:
        return open_file_resp, False

    # 18. File Search across user folders ('find my resume on Desktop', 'search Week 4 video in Downloads', 'search Week 4 video there')
    handled_file_search, search_file_resp = handle_file_search_command(prompt)
    if handled_file_search:
        return search_file_resp, False

    # 19. Web Search ('search Python tutorial', 'search the web for ...', 'search YouTube for ...')
    handled_search, search_resp = handle_search_web(prompt)
    if handled_search:
        return search_resp, False

    # 20. Safe Mathematical Calculator ('what is 50 times 20', 'what is 25 multiplied by 40')
    if (
        "calculate" in prompt_lower
        or "percent of" in prompt_lower
        or "times" in prompt_lower
        or "multiplied by" in prompt_lower
        or "divided by" in prompt_lower
        or re.search(r"what is \d+", prompt_lower)
        or re.search(r"^\d+\s*[\+\-\*/\%]\s*\d+", prompt_lower)
    ):
        math_candidate = re.sub(r"^(calculate|what is|how much is)\s*", "", prompt_lower, flags=re.IGNORECASE)
        math_candidate = math_candidate.rstrip("?.").strip()
        result = safe_calculate(math_candidate)
        if result is not None:
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            return f"The result is {result}.", False

    # 21. Fallback to Gemini AI Brain
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
    memory_count = get_memory_count()

    banner = f"""
========================================
             J.A.R.V.I.S V2
         PERSONAL AI ASSISTANT
========================================
STATUS: ONLINE
AI: {ai_status}
VOICE: {voice_status}
MEMORY: READY
MEMORIES: {memory_count}
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
