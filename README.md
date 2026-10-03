# 🤖 J.A.R.V.I.S V2 — Personal AI Desktop Assistant

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](https://www.microsoft.com/windows)

An intelligent, lightweight, and reliable personal desktop AI assistant for Windows powered by **Google Gemini AI** with persistent personal memory, safe application & folder launching, volume controls, file searching, reading and summarizing text files, screen vision analysis, system health monitoring, and natural voice interaction.

---

## ✨ What's New in V2

- 🧠 **Personal Persistent Memory (`jarvis_memory.json`)**: Remember facts ("Remember that my name is Zeeshan", "What project am I working on?", "What do you remember about me?").
- 🔒 **Confirmation Mechanism**: Asks for confirmation before executing destructive operations like memory wipes.
- 👁️ **Screen Vision**: Analyzes your screen with Gemini Vision ("Jarvis, look at my screen").
- 📂 **Folder Control**: Seamlessly opens standard Windows folders (Downloads, Documents, Desktop, Pictures).
- 🔊 **System Volume Control**: Windows master audio adjustment (Increase, Decrease, Mute, Set %).
- 🔎 **Safe File Search**: Search user directories for specific files or formats ("Find my Python files", "Find resume.pdf").
- 📖 **Read & Summarize Text Files**: Reads and summarizes `.txt`, `.md`, `.py`, `.csv`, `.json` files safely without code execution.
- 💬 **Rolling Session Context**: Retains conversational context across multi-turn queries.
- ⚡ **Structured Command Priority Router**: Executes local actions instantly without unnecessary API calls.
- 📊 **Status & Help Systems**: Instant access to system health (`System status`) and full capability lists (`What can you do?`).

---

## 🛠️ Requirements & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/szeeshanZ123/JARVIS.git
cd JARVIS
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

> **Note on Voice Input (PyAudio):**
> On Windows, if microphone voice input is desired, install `PyAudio`:
> ```bash
> pip install PyAudio
> ```
> *If PyAudio is not installed, JARVIS automatically falls back to interactive console text input while maintaining full voice output (TTS).*

---

## ⚙️ Configuration

1. Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and set your key:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

---

## 🚀 Running JARVIS V2

Start the assistant:
```bash
python jarvis.py
```

### 🗣️ Example Commands & Voice Queries

| Category | Example Voice / Text Queries |
| :--- | :--- |
| **Personal Memory** | *"Remember that my name is Zeeshan"*<br>*"What is my name?"*<br>*"What do you remember about me?"*<br>*"Forget that my favorite language is Python"*<br>*"Clear my memory"* *(Prompts for confirmation)* |
| **Screen Vision** | *"Jarvis, look at my screen"*<br>*"What is on my screen?"* |
| **App & Folder Control** | *"Open Chrome"*, *"Open VS Code"*, *"Open Spotify"*<br>*"Open Downloads"*, *"Open Documents"*, *"Open Desktop"* |
| **File Operations** | *"Find my Python files"*<br>*"Find resume.pdf"*<br>*"Read requirements.txt"* |
| **Volume Control** | *"Increase volume"*, *"Decrease volume"*, *"Mute volume"*, *"Set volume to 50%"* |
| **Conversational AI** | *"Explain quantum computing in simple terms"*<br>*"Who created Python?"* |
| **System Diagnostics**| *"System status"*<br>*"What is my CPU usage?"*<br>*"Check RAM usage"* |
| **Web Search** | *"Search google for latest space missions"*<br>*"Open YouTube"* |
| **Calculations** | *"Calculate 15 percent of 4500"*<br>*"What is (250 * 4) + 120?"* |
| **Exit** | *"Exit"*, *"Quit"*, *"Goodbye"*, *"Shutdown"* |

---

## 🧪 Running Tests

Execute the automated test suite:
```bash
python test_jarvis.py
```

---

## 🛡️ Security & Privacy

- **Memory & Keys Protected**: `.env` and `jarvis_memory.json` are automatically ignored by `.gitignore`.
- **Safe Sandboxing**: No arbitrary code execution from AI responses or inspected files.
- **Confirmation Guards**: Destructive operations require explicit user confirmation.

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
