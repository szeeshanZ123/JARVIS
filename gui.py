"""
=============================================================================
J.A.R.V.I.S V3 - Futuristic PySide6 Desktop GUI Interface
=============================================================================
A modern, dark-navy, electric-cyan desktop assistant interface for Windows.
Features:
- Animated AI Orb with 5 visual states (IDLE, LISTENING, THINKING, SPEAKING, ERROR)
- Real-time System Telemetry (CPU %, RAM %, AI status, Microphone, Audio, Memory)
- Thread-safe Asynchronous Operations (Speech, Voice Input, Command Routing, AI)
- Conversational Communication Log with message bubble formatting
- Full Voice & Text Dual-Mode Interaction with Instant Interruption support
=============================================================================
"""

import os
import sys
import math
import time
import datetime
from typing import Optional, List, Dict, Any

from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, Slot, QPointF, QRectF, QSize
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient,
    QFont, QIcon, QPainterPath
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QScrollArea,
    QProgressBar, QFrame, QSizePolicy, QGraphicsDropShadowEffect
)

import jarvis


# =============================================================================
# WORKER THREADS (NON-BLOCKING ASYNC OPERATIONS)
# =============================================================================
class CommandWorker(QThread):
    """Executes assistant commands in a background thread so GUI never freezes."""
    finished = Signal(str, bool)  # response_text, should_exit
    error = Signal(str)

    def __init__(self, command_text: str):
        super().__init__()
        self.command_text = command_text

    def run(self):
        try:
            response, should_exit = jarvis.route_command(self.command_text)
            self.finished.emit(response, should_exit)
        except Exception as e:
            self.error.emit(f"Error processing command: {e}")


class SpeechWorker(QThread):
    """Speaks responses via TTS in background and signals when started/finished."""
    started_speaking = Signal()
    finished_speaking = Signal()

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        try:
            self.started_speaking.emit()
            jarvis.speak(self.text)
        except Exception:
            pass
        finally:
            self.finished_speaking.emit()


class VoiceWorker(QThread):
    """Listens to microphone in background and emits recognized speech."""
    recognized = Signal(str)
    unrecognized = Signal()
    error = Signal(str)
    finished = Signal()

    def run(self):
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer() if jarvis.sr is not None else None
            backend, _ = jarvis.detect_microphone_backend()
            text = jarvis.listen(recognizer, backend)
            if text:
                self.recognized.emit(text)
            else:
                self.unrecognized.emit()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


# =============================================================================
# ANIMATED AI ORB WIDGET (PySide6 Canvas Painting)
# =============================================================================
class AIOrbWidget(QWidget):
    """
    Futuristic animated AI Orb with visual representations of assistant state:
    - IDLE: Gentle sinusoidal pulse in deep cyan and electric blue
    - LISTENING: Vibrant cyan-emerald glow with expanding sonic ripple rings
    - THINKING: Dual counter-rotating segmented orbital rings with energetic pulsing
    - SPEAKING: Undulating audio waveform frequencies and high-energy core
    - ERROR: Crimson warning pulse with smooth recovery
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.state = "IDLE"  # IDLE, LISTENING, THINKING, SPEAKING, ERROR
        self.phase = 0.0
        self.orbit_angle1 = 0.0
        self.orbit_angle2 = 0.0
        self.ripple_phases = [0.0, 0.33, 0.66]

        # 30 FPS animation timer
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._update_animation)
        self.anim_timer.start(33)

    def set_state(self, state: str):
        if state in ["IDLE", "LISTENING", "THINKING", "SPEAKING", "ERROR"]:
            self.state = state
            self.update()

    def _update_animation(self):
        speed = 0.05
        if self.state == "THINKING":
            speed = 0.12
            self.orbit_angle1 = (self.orbit_angle1 + 4.0) % 360
            self.orbit_angle2 = (self.orbit_angle2 - 2.5) % 360
        elif self.state == "SPEAKING":
            speed = 0.15
            self.orbit_angle1 = (self.orbit_angle1 + 2.0) % 360
            self.orbit_angle2 = (self.orbit_angle2 - 1.5) % 360
        elif self.state == "LISTENING":
            speed = 0.08
            self.orbit_angle1 = (self.orbit_angle1 + 1.0) % 360
            self.orbit_angle2 = (self.orbit_angle2 - 0.8) % 360
        else:
            speed = 0.04
            self.orbit_angle1 = (self.orbit_angle1 + 0.6) % 360
            self.orbit_angle2 = (self.orbit_angle2 - 0.4) % 360

        self.phase = (self.phase + speed) % (2 * math.pi)
        self.ripple_phases = [(p + speed * 0.8) % 1.0 for p in self.ripple_phases]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        base_radius = min(w, h) * 0.28

        # Color configurations by state
        if self.state == "LISTENING":
            core_color = QColor(0, 242, 254)
            glow_color = QColor(0, 255, 180, 80)
            ring_color = QColor(0, 255, 200, 160)
            pulse_mod = math.sin(self.phase * 2) * 8.0
        elif self.state == "THINKING":
            core_color = QColor(0, 195, 255)
            glow_color = QColor(79, 172, 254, 90)
            ring_color = QColor(0, 210, 255, 200)
            pulse_mod = math.sin(self.phase * 3) * 6.0
        elif self.state == "SPEAKING":
            core_color = QColor(0, 230, 255)
            glow_color = QColor(0, 200, 255, 110)
            ring_color = QColor(100, 220, 255, 220)
            pulse_mod = (math.sin(self.phase * 4) + math.cos(self.phase * 2)) * 6.0
        elif self.state == "ERROR":
            core_color = QColor(255, 75, 75)
            glow_color = QColor(255, 50, 50, 80)
            ring_color = QColor(255, 100, 100, 180)
            pulse_mod = math.sin(self.phase * 2) * 5.0
        else:  # IDLE
            core_color = QColor(0, 210, 255)
            glow_color = QColor(0, 180, 255, 50)
            ring_color = QColor(0, 210, 255, 120)
            pulse_mod = math.sin(self.phase) * 4.0

        current_radius = max(20.0, base_radius + pulse_mod)

        # 1. Outer Deep Ambient Glow
        ambient_grad = QRadialGradient(QPointF(cx, cy), current_radius * 2.2)
        ambient_grad.setColorAt(0.0, glow_color)
        ambient_grad.setColorAt(0.6, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 20))
        ambient_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(ambient_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), current_radius * 2.2, current_radius * 2.2)

        # 2. Expanding Ripple Waves (Listening and Speaking)
        if self.state in ["LISTENING", "SPEAKING"]:
            for r_phase in self.ripple_phases:
                r_dist = current_radius + (r_phase * base_radius * 1.4)
                r_alpha = int((1.0 - r_phase) * 140)
                if r_alpha > 0:
                    r_color = QColor(ring_color.red(), ring_color.green(), ring_color.blue(), r_alpha)
                    r_pen = QPen(r_color, 1.5)
                    painter.setPen(r_pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(cx, cy), r_dist, r_dist)

        # 3. Outer Orbital Segmented Rings
        ring1_pen = QPen(ring_color, 2.0, Qt.DashLine)
        painter.setPen(ring1_pen)
        painter.setBrush(Qt.NoBrush)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.orbit_angle1)
        r_outer = current_radius * 1.35
        painter.drawEllipse(QPointF(0, 0), r_outer, r_outer)

        # Draw orbital data tick markers
        painter.rotate(self.orbit_angle2 * 1.5)
        r_inner_orbit = current_radius * 1.15
        ring2_pen = QPen(QColor(ring_color.red(), ring_color.green(), ring_color.blue(), 100), 1.2, Qt.DotLine)
        painter.setPen(ring2_pen)
        painter.drawEllipse(QPointF(0, 0), r_inner_orbit, r_inner_orbit)
        painter.restore()

        # 4. Central Glowing Orb Core
        core_grad = QRadialGradient(QPointF(cx - current_radius * 0.25, cy - current_radius * 0.25), current_radius)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 230))
        core_grad.setColorAt(0.3, core_color)
        core_grad.setColorAt(0.8, QColor(core_color.red() // 2, core_color.green() // 2, core_color.blue() // 2, 200))
        core_grad.setColorAt(1.0, QColor(10, 20, 45, 180))

        painter.setBrush(QBrush(core_grad))
        painter.setPen(QPen(QColor(255, 255, 255, 160), 1.5))
        painter.drawEllipse(QPointF(cx, cy), current_radius, current_radius)


# =============================================================================
# MAIN WINDOW CLASS (PySide6)
# =============================================================================
class JarvisV3Window(QMainWindow):
    """Futuristic J.A.R.V.I.S V3 Desktop GUI Application Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S V3 // Personal Desktop Assistant")
        self.resize(1100, 720)
        self.setMinimumSize(960, 640)

        # Worker holders
        self.cmd_worker: Optional[CommandWorker] = None
        self.speech_worker: Optional[SpeechWorker] = None
        self.voice_worker: Optional[VoiceWorker] = None

        self._init_ui()
        self._init_telemetry_timer()

        # Initial welcome message in log
        self.append_bot_message("Good day. J.A.R.V.I.S V3 is online and standing by. How may I assist you?")

    def _init_ui(self):
        # Apply Futuristic Dark Theme Stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #060b13;
            }
            QWidget {
                color: #e0f2fe;
                font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
            }
            QFrame#panelFrame {
                background-color: rgba(10, 22, 40, 0.85);
                border: 1px solid rgba(0, 242, 254, 0.22);
                border-radius: 10px;
            }
            QLabel#panelTitle {
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 1.5px;
                color: #00f2fe;
                padding-bottom: 6px;
                border-bottom: 1px solid rgba(0, 242, 254, 0.15);
            }
            QLabel#headerTitle {
                font-size: 20px;
                font-weight: 800;
                letter-spacing: 3px;
                color: #00f2fe;
            }
            QLabel#headerSubtitle {
                font-size: 11px;
                letter-spacing: 1px;
                color: #7dd3fc;
            }
            QTextEdit#chatLog {
                background-color: transparent;
                border: none;
                color: #e0f2fe;
                font-size: 13px;
                line-height: 1.4;
            }
            QLineEdit#inputField {
                background-color: rgba(14, 28, 52, 0.9);
                border: 1px solid rgba(0, 242, 254, 0.35);
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
                color: #ffffff;
            }
            QLineEdit#inputField:focus {
                border: 1px solid #00f2fe;
                background-color: rgba(18, 36, 68, 0.95);
            }
            QPushButton#actionBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0088cc, stop:1 #00f2fe);
                color: #050b14;
                font-weight: 700;
                font-size: 13px;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
            }
            QPushButton#actionBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00aaff, stop:1 #38f9d7);
            }
            QPushButton#micBtn {
                background-color: rgba(14, 34, 60, 0.85);
                border: 1px solid rgba(0, 242, 254, 0.4);
                color: #00f2fe;
                font-weight: 700;
                border-radius: 8px;
                padding: 10px 16px;
            }
            QPushButton#micBtn:hover {
                background-color: rgba(0, 242, 254, 0.2);
                border-color: #00f2fe;
            }
            QPushButton#stopBtn {
                background-color: rgba(60, 20, 24, 0.85);
                border: 1px solid rgba(255, 75, 75, 0.4);
                color: #ff6b6b;
                font-weight: 700;
                border-radius: 8px;
                padding: 10px 16px;
            }
            QPushButton#stopBtn:hover {
                background-color: rgba(255, 75, 75, 0.25);
                border-color: #ff6b6b;
            }
            QPushButton#clearBtn {
                background-color: transparent;
                border: 1px solid rgba(125, 211, 252, 0.2);
                color: #7dd3fc;
                font-size: 11px;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton#clearBtn:hover {
                border-color: #00f2fe;
                color: #00f2fe;
            }
            QProgressBar {
                background-color: rgba(10, 20, 36, 0.8);
                border: 1px solid rgba(0, 242, 254, 0.2);
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                height: 12px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052d4, stop:1 #00f2fe);
                border-radius: 4px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 14, 18, 16)
        main_layout.setSpacing(14)

        # ---------------------------------------------------------------------
        # TOP HEADER BAR
        # ---------------------------------------------------------------------
        top_bar = QHBoxLayout()
        header_left = QVBoxLayout()
        title_label = QLabel("J.A.R.V.I.S  //  V3.0")
        title_label.setObjectName("headerTitle")
        sub_label = QLabel("ADVANCED DESKTOP AI ASSISTANT")
        sub_label.setObjectName("headerSubtitle")
        header_left.addWidget(title_label)
        header_left.addWidget(sub_label)
        top_bar.addLayout(header_left)

        top_bar.addStretch()

        # Status badge
        ai_online = bool(os.environ.get("GEMINI_API_KEY"))
        self.ai_badge = QLabel("AI: CONNECTED" if ai_online else "AI: OFFLINE")
        self.ai_badge.setStyleSheet(f"""
            background-color: {'rgba(0, 255, 180, 0.15)' if ai_online else 'rgba(255, 60, 60, 0.15)'};
            color: {'#00ffb4' if ai_online else '#ff4b4b'};
            border: 1px solid {'#00ffb4' if ai_online else '#ff4b4b'};
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 11px;
            font-weight: 700;
        """)
        top_bar.addWidget(self.ai_badge)

        main_layout.addLayout(top_bar)

        # ---------------------------------------------------------------------
        # 3-COLUMN CONTENT AREA
        # ---------------------------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        # =====================================================================
        # LEFT PANEL: COMMUNICATION LOG
        # =====================================================================
        left_panel = QFrame()
        left_panel.setObjectName("panelFrame")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 12, 14, 12)
        left_layout.setSpacing(10)

        left_header = QHBoxLayout()
        left_title = QLabel("COMMUNICATION LOG")
        left_title.setObjectName("panelTitle")
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("clearBtn")
        clear_btn.clicked.connect(self._clear_chat_log)
        left_header.addWidget(left_title)
        left_header.addStretch()
        left_header.addWidget(clear_btn)
        left_layout.addLayout(left_header)

        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chatLog")
        self.chat_display.setReadOnly(True)
        left_layout.addWidget(self.chat_display)

        content_layout.addWidget(left_panel, stretch=38)

        # =====================================================================
        # CENTER PANEL: ANIMATED AI ORB & CORE STATUS
        # =====================================================================
        center_panel = QFrame()
        center_panel.setObjectName("panelFrame")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(14, 16, 14, 16)
        center_layout.setAlignment(Qt.AlignCenter)

        self.orb = AIOrbWidget()
        center_layout.addWidget(self.orb, alignment=Qt.AlignCenter)

        # State text label beneath orb
        self.orb_state_label = QLabel("SYSTEM ONLINE - STANDBY")
        self.orb_state_label.setAlignment(Qt.AlignCenter)
        self.orb_state_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 2px;
            color: #00f2fe;
            margin-top: 10px;
        """)
        center_layout.addWidget(self.orb_state_label)

        # Quick Suggestion Chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)
        chips = [("List Desktop", "List files on my Desktop."), ("Downloads", "Open Downloads."), ("Status", "System status report.")]
        for label, cmd in chips:
            chip_btn = QPushButton(label)
            chip_btn.setStyleSheet("""
                background-color: rgba(0, 242, 254, 0.08);
                border: 1px solid rgba(0, 242, 254, 0.25);
                border-radius: 12px;
                font-size: 11px;
                padding: 4px 10px;
                color: #7dd3fc;
            """)
            chip_btn.clicked.connect(lambda _, c=cmd: self._send_command_text(c))
            chips_layout.addWidget(chip_btn)
        center_layout.addLayout(chips_layout)

        content_layout.addWidget(center_panel, stretch=34)

        # =====================================================================
        # RIGHT PANEL: SYSTEM TELEMETRY
        # =====================================================================
        right_panel = QFrame()
        right_panel.setObjectName("panelFrame")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 12, 14, 12)
        right_layout.setSpacing(12)

        right_title = QLabel("SYSTEM TELEMETRY")
        right_title.setObjectName("panelTitle")
        right_layout.addWidget(right_title)

        # CPU Gauge
        cpu_label_box = QHBoxLayout()
        cpu_label_box.addWidget(QLabel("CPU UTILIZATION:"))
        self.cpu_text = QLabel("0.0%")
        self.cpu_text.setStyleSheet("color: #00f2fe; font-weight: 700;")
        cpu_label_box.addWidget(self.cpu_text, alignment=Qt.AlignRight)
        right_layout.addLayout(cpu_label_box)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        right_layout.addWidget(self.cpu_bar)

        # RAM Gauge
        ram_label_box = QHBoxLayout()
        ram_label_box.addWidget(QLabel("RAM ALLOCATION:"))
        self.ram_text = QLabel("0.0%")
        self.ram_text.setStyleSheet("color: #00f2fe; font-weight: 700;")
        ram_label_box.addWidget(self.ram_text, alignment=Qt.AlignRight)
        right_layout.addLayout(ram_label_box)

        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        right_layout.addWidget(self.ram_bar)

        # Telemetry info items
        right_layout.addSpacing(6)
        self.tel_mic = QLabel("Microphone: Detecting...")
        self.tel_audio = QLabel("Audio Engine: Ready (Windows SAPI)")
        self.tel_mem = QLabel(f"Memory Banks: {jarvis.get_memory_count()} Memories")
        self.tel_loc = QLabel("Location Context: System Root")

        for lbl in [self.tel_mic, self.tel_audio, self.tel_mem, self.tel_loc]:
            lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
            right_layout.addWidget(lbl)

        right_layout.addStretch()
        content_layout.addWidget(right_panel, stretch=28)

        main_layout.addLayout(content_layout, stretch=1)

        # ---------------------------------------------------------------------
        # BOTTOM CONTROL BAR (INPUT, SEND, MIC, STOP)
        # ---------------------------------------------------------------------
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("inputField")
        self.input_field.setPlaceholderText("Type a command or click the microphone to speak...")
        self.input_field.returnPressed.connect(self._handle_send_clicked)
        bottom_bar.addWidget(self.input_field, stretch=1)

        self.send_btn = QPushButton("SEND")
        self.send_btn.setObjectName("actionBtn")
        self.send_btn.clicked.connect(self._handle_send_clicked)
        bottom_bar.addWidget(self.send_btn)

        self.mic_btn = QPushButton("VOICE")
        self.mic_btn.setObjectName("micBtn")
        self.mic_btn.clicked.connect(self._toggle_voice_listening)
        bottom_bar.addWidget(self.mic_btn)

        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.clicked.connect(self._stop_active_operations)
        bottom_bar.addWidget(self.stop_btn)

        main_layout.addLayout(bottom_bar)

    def _init_telemetry_timer(self):
        """Updates hardware usage, AI status, and memory bank counts every 2 seconds."""
        self.tel_timer = QTimer(self)
        self.tel_timer.timeout.connect(self._refresh_telemetry)
        self.tel_timer.start(2000)
        self._refresh_telemetry()

    def _refresh_telemetry(self):
        metrics = jarvis.get_system_telemetry()
        cpu_val = int(metrics.get("cpu", 0))
        ram_val = int(metrics.get("ram", 0))

        self.cpu_bar.setValue(cpu_val)
        self.cpu_text.setText(f"{metrics.get('cpu', 0.0):.1f}%")

        self.ram_bar.setValue(ram_val)
        self.ram_text.setText(f"{metrics.get('ram', 0.0):.1f}%")

        mem_count = metrics.get("memory_count", 0)
        self.tel_mem.setText(f"Memory Banks: {mem_count} Saved Facts")

        active_loc = metrics.get("active_location", "System Root")
        self.tel_loc.setText(f"Active Folder: {active_loc}")

        # Check mic backend
        backend, name = jarvis.detect_microphone_backend()
        if backend:
            self.tel_mic.setText(f"Microphone: {name}")
        else:
            self.tel_mic.setText("Microphone: Not Detected (Keyboard Mode)")

    def _clear_chat_log(self):
        self.chat_display.clear()

    def append_user_message(self, text: str):
        now_str = datetime.datetime.now().strftime("%I:%M %p")
        bubble = (
            f"<div style='margin-bottom: 12px; text-align: right;'>"
            f"<span style='color: #94a3b8; font-size: 10px;'>{now_str}</span><br>"
            f"<div style='display: inline-block; background-color: rgba(0, 136, 204, 0.35); "
            f"border: 1px solid rgba(0, 242, 254, 0.4); border-radius: 8px; padding: 8px 12px; "
            f"color: #ffffff; text-align: left; max-width: 85%; font-weight: 500;'>"
            f"<b>YOU:</b> {text}</div></div>"
        )
        self.chat_display.append(bubble)
        self._scroll_chat_to_bottom()

    def append_bot_message(self, text: str):
        now_str = datetime.datetime.now().strftime("%I:%M %p")
        formatted = text.replace("\n", "<br>")
        bubble = (
            f"<div style='margin-bottom: 12px; text-align: left;'>"
            f"<span style='color: #00f2fe; font-size: 10px;'>JARVIS • {now_str}</span><br>"
            f"<div style='display: inline-block; background-color: rgba(10, 24, 48, 0.75); "
            f"border-left: 3px solid #00f2fe; border-radius: 0 8px 8px 0; padding: 8px 12px; "
            f"color: #e0f2fe; max-width: 90%;'>"
            f"{formatted}</div></div>"
        )
        self.chat_display.append(bubble)
        self._scroll_chat_to_bottom()

    def _scroll_chat_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # =========================================================================
    # COMMAND PROCESSING (TEXT & VOICE)
    # =========================================================================
    def _handle_send_clicked(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self._send_command_text(text)

    def _send_command_text(self, text: str):
        self.append_user_message(text)

        # Set Orb State to THINKING
        self.orb.set_state("THINKING")
        self.orb_state_label.setText("PROCESSING COMMAND...")

        # Run command asynchronously in worker thread
        self.cmd_worker = CommandWorker(text)
        self.cmd_worker.finished.connect(self._on_command_finished)
        self.cmd_worker.error.connect(self._on_command_error)
        self.cmd_worker.start()

    @Slot(str, bool)
    def _on_command_finished(self, response: str, should_exit: bool):
        if response:
            self.append_bot_message(response)
            # Speak response in background thread
            self._start_speaking(response)
        else:
            self.orb.set_state("IDLE")
            self.orb_state_label.setText("SYSTEM ONLINE - STANDBY")

        if should_exit:
            QTimer.singleShot(1500, self.close)

    @Slot(str)
    def _on_command_error(self, err_msg: str):
        self.append_bot_message(f"Command Error: {err_msg}")
        self.orb.set_state("ERROR")
        self.orb_state_label.setText("ERROR ENCOUNTERED")
        QTimer.singleShot(2500, lambda: self.orb.set_state("IDLE"))
        QTimer.singleShot(2500, lambda: self.orb_state_label.setText("SYSTEM ONLINE - STANDBY"))

    # =========================================================================
    # VOICE INPUT INTERACTION
    # =========================================================================
    def _toggle_voice_listening(self):
        if self.voice_worker and self.voice_worker.isRunning():
            return

        self.orb.set_state("LISTENING")
        self.orb_state_label.setText("LISTENING... SPEAK NOW")
        self.mic_btn.setText("LISTENING...")
        self.mic_btn.setStyleSheet("""
            background-color: rgba(0, 242, 254, 0.35);
            border: 1px solid #00f2fe;
            color: #ffffff;
            font-weight: 700;
            border-radius: 8px;
            padding: 10px 16px;
        """)

        self.voice_worker = VoiceWorker()
        self.voice_worker.recognized.connect(self._on_voice_recognized)
        self.voice_worker.unrecognized.connect(self._on_voice_unrecognized)
        self.voice_worker.error.connect(self._on_voice_error)
        self.voice_worker.finished.connect(self._on_voice_finished)
        self.voice_worker.start()

    @Slot(str)
    def _on_voice_recognized(self, text: str):
        self._reset_mic_button()
        self._send_command_text(text)

    @Slot()
    def _on_voice_unrecognized(self):
        self._reset_mic_button()
        self.orb.set_state("IDLE")
        self.orb_state_label.setText("SPEECH NOT RECOGNIZED")
        QTimer.singleShot(2000, lambda: self.orb_state_label.setText("SYSTEM ONLINE - STANDBY"))

    @Slot(str)
    def _on_voice_error(self, err_msg: str):
        self._reset_mic_button()
        self.orb.set_state("ERROR")
        self.orb_state_label.setText("MIC ERROR")
        self.append_bot_message(f"Microphone input issue: {err_msg}")
        QTimer.singleShot(2000, lambda: self.orb.set_state("IDLE"))
        QTimer.singleShot(2000, lambda: self.orb_state_label.setText("SYSTEM ONLINE - STANDBY"))

    @Slot()
    def _on_voice_finished(self):
        self._reset_mic_button()

    def _reset_mic_button(self):
        self.mic_btn.setText("VOICE")
        self.mic_btn.setStyleSheet("""
            background-color: rgba(14, 34, 60, 0.85);
            border: 1px solid rgba(0, 242, 254, 0.4);
            color: #00f2fe;
            font-weight: 700;
            border-radius: 8px;
            padding: 10px 16px;
        """)

    # =========================================================================
    # SPEECH OUTPUT & INTERRUPTION
    # =========================================================================
    def _start_speaking(self, text: str):
        self.speech_worker = SpeechWorker(text)
        self.speech_worker.started_speaking.connect(self._on_speech_started)
        self.speech_worker.finished_speaking.connect(self._on_speech_finished)
        self.speech_worker.start()

    @Slot()
    def _on_speech_started(self):
        self.orb.set_state("SPEAKING")
        self.orb_state_label.setText("SPEAKING...")

    @Slot()
    def _on_speech_finished(self):
        self.orb.set_state("IDLE")
        self.orb_state_label.setText("SYSTEM ONLINE - STANDBY")

    def _stop_active_operations(self):
        """Immediately interrupts active speech synthesis and cancels operations."""
        jarvis.stop_speaking()
        self.orb.set_state("IDLE")
        self.orb_state_label.setText("OPERATIONS HALTED")
        QTimer.singleShot(1500, lambda: self.orb_state_label.setText("SYSTEM ONLINE - STANDBY"))


# =============================================================================
# GUI ENTRY POINT FUNCTION
# =============================================================================
def launch_gui():
    """Initializes and runs the PySide6 J.A.R.V.I.S V3 Desktop GUI Application."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = JarvisV3Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(launch_gui())
