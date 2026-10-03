# 🤖 J.A.R.V.I.S — Personal AI Desktop Voice Assistant

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](https://www.microsoft.com/windows)

An intelligent, lightweight, and responsive personal desktop AI voice assistant powered by **Google Gemini AI** with real-time speech recognition, text-to-speech synthesis, system monitoring, and automated desktop actions.

---

## ✨ Features

- 🧠 **Gemini AI Brain**: Continuous 1-on-1 conversational memory with automated multi-model fallback (`gemini-3.5-flash`, `gemini-3.7-flash`, etc.).
- 🎙️ **Dual Interaction Modes**: Seamless voice recognition via microphone and interactive keyboard console fallback.
- 🗣️ **Ultra-Smooth Speech Output (TTS)**: High-performance native Windows SAPI voice engine with `pyttsx3` fallback.
- 🖥️ **System Health Monitoring**: Real-time CPU load, RAM memory statistics, and OS hardware information.
- 🚀 **App Launcher & Window Controller**: Launch Notepad, VS Code, Google Chrome, Microsoft Edge, Calculator, File Explorer, and more.
- 🌐 **Web & Search Automation**: Quick search and direct navigation across Google, YouTube, GitHub, Stack Overflow, and custom URLs.
- 📸 **Screenshot Capture**: Instantly capture and save full-screen screenshots directly to your `Pictures/Screenshots` directory.
- 🔢 **Safe Math Engine**: AST-based secure mathematical evaluator for calculations and percentage problems without dangerous `eval()` execution.
- 🧪 **Comprehensive Test Suite**: Automated unit and integration testing via `test_jarvis.py`.

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
> *If PyAudio is not installed, JARVIS automatically provides smooth interactive console text input while maintaining full voice output (TTS).*

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

## 🚀 Running JARVIS

Start the assistant:
```bash
python jarvis.py
```

### 🗣️ Example Commands & Voice Queries

| Category | Example Voice / Text Queries |
| :--- | :--- |
| **Conversational AI** | *"Explain quantum computing in simple terms"*<br>*"Give me 3 tips to boost productivity"* |
| **System Diagnostics**| *"What is my CPU usage?"*<br>*"Check RAM usage"*<br>*"What OS am I running?"* |
| **App Launching** | *"Open VS Code"*<br>*"Launch Notepad"*<br>*"Open Chrome"*<br>*"Start Calculator"* |
| **Web Search** | *"Search google for latest space missions"*<br>*"Open YouTube"*<br>*"Open github.com"* |
| **Calculations** | *"Calculate 15 percent of 4500"*<br>*"What is (250 * 4) + 120?"* |
| **Utilities** | *"Take a screenshot"*<br>*"What time is it?"*<br>*"What is today's date?"* |
| **Exit** | *"Exit"*, *"Quit"*, *"Goodbye"*, *"Shutdown"* |

---

## 🧪 Running Tests

Execute the automated test suite:
```bash
python -m unittest test_jarvis.py
```

---

## 🛡️ Security & Privacy

- Secret keys stored inside `.env` are automatically ignored by `.gitignore` to prevent leaking credentials.
- Math expressions are parsed and evaluated securely using Python's Abstract Syntax Tree (AST) rather than unsafe `eval()` executions.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'feat: add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
