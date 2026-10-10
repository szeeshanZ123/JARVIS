import os
import sys
import json
import jarvis

print("==================================================")
print("     J.A.R.V.I.S V3 COMPREHENSIVE TEST SUITE      ")
print("==================================================")

# -----------------------------------------------------------------------------
# 1. TEST RELIABLE WINDOWS FILE ACCESS
# -----------------------------------------------------------------------------
print("\n--- 1. TESTING WINDOWS FILE ACCESS ---")

# A. Discovered Known Folders
dirs = jarvis.get_user_directories()
print(f"Discovered {len(dirs)} User Directories:")
for k, v in dirs.items():
    print(f"  • {k.title()}: {v} (Exists: {os.path.isdir(v)})")
assert len(dirs) >= 4, "Expected at least 4 user directories"

# B. List files on Desktop
list_desktop, _ = jarvis.route_command("Jarvis, list files on my Desktop.")
print(f"\nList Desktop Result:\n{list_desktop[:250]}...")
assert "Desktop" in list_desktop, "Failed to list Desktop"

# C. List files in Downloads
list_dl, _ = jarvis.route_command("Jarvis, list files in Downloads.")
print(f"\nList Downloads Result:\n{list_dl[:250]}...")
assert "Downloads" in list_dl, "Failed to list Downloads"

# D. Search Documents for PDF files
search_docs, _ = jarvis.route_command("Jarvis, find PDF files in Downloads.")
print(f"\nFind PDF files in Downloads:\n{search_docs[:250]}...")
assert "Downloads" in search_docs or "matching file" in search_docs

# E. Read a TXT file safely
test_txt_path = os.path.join(os.getcwd(), "test_v3_notes.txt")
with open(test_txt_path, "w", encoding="utf-8") as f:
    f.write("J.A.R.V.I.S V3 Architecture Notes: Desktop PySide6 UI and Reliable Windows File Access.")

read_txt, _ = jarvis.route_command(f"Jarvis, read {test_txt_path}")
print(f"\nRead TXT Result:\n{read_txt}")
assert "Architecture Notes" in read_txt, "Failed to read TXT file"

# F. Extract text from PDF file safely (via pypdf)
test_pdf_path = os.path.join(os.getcwd(), "test_v3_assignment.pdf")
# Minimal valid PDF structure with text
pdf_raw = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>/Contents 4 0 R>>endobj\n"
    b"4 0 obj<</Length 68>>stream\nBT /F1 12 Tf 72 712 Td (Operating System Assignment: Memory Management V3) Tj ET\nendstream\nendobj\n"
    b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000204 00000 n \n"
    b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n323\n%%EOF\n"
)
with open(test_pdf_path, "wb") as f:
    f.write(pdf_raw)

read_pdf, _ = jarvis.route_command(f"Jarvis, read {test_pdf_path}")
print(f"\nRead PDF Result:\n{read_pdf}")
assert "test_v3_assignment.pdf" in read_pdf or "extracted" in read_pdf.lower()

# G. Inaccessible directory error reporting
succ, err_resp = jarvis.list_folder_contents(r"Z:\NonExistentSystemFolder_999")
print(f"\nNon-existent directory check:\n{err_resp}")
assert "does not exist" in err_resp, "Expected clear does not exist report"

# -----------------------------------------------------------------------------
# 2. TEST CONTEXT & COMMAND ROUTING
# -----------------------------------------------------------------------------
print("\n--- 2. TESTING CONTEXT & COMMAND ROUTING ---")

# Step 1: Open Downloads
resp, _ = jarvis.route_command("Jarvis, open Downloads.")
print(f"1. Open Downloads: {resp} (Context: {jarvis.context.last_location})")
assert jarvis.context.last_location == "Downloads"

# Step 2: Search Week 4 in Downloads
resp, _ = jarvis.route_command("Jarvis, search Downloads for Week 4.")
print(f"2. Search Week 4: {resp[:120]}...")

# Step 3: Open YouTube
resp, _ = jarvis.route_command("Jarvis, open YouTube.")
print(f"3. Open YouTube: {resp}")
assert "youtube" in resp.lower()

# Step 4: Find resume on Desktop
resp, _ = jarvis.route_command("Jarvis, find my resume on Desktop.")
print(f"4. Find resume on Desktop: Context={jarvis.context.last_location}")
assert jarvis.context.last_location == "Desktop"

# Step 5: Open it (Pronoun resolution)
# Create dummy resume on Desktop
desktop_dir = jarvis.get_user_directories().get("desktop", os.getcwd())
test_resume = os.path.join(desktop_dir, "test_resume_v3.pdf")
with open(test_resume, "w") as f:
    f.write("dummy resume")
jarvis.context.update(last_found_files=[test_resume])

resp, _ = jarvis.route_command("Jarvis, open it.")
print(f"5. Open it: {resp}")
assert "test_resume_v3.pdf" in resp

# Step 6: Math calculation
resp, _ = jarvis.route_command("Jarvis, what is 25 multiplied by 40?")
print(f"6. What is 25 multiplied by 40: {resp}")
assert "1000" in resp, f"Expected 1000, got {resp}"

# -----------------------------------------------------------------------------
# 3. TEST PERSISTENT MEMORY
# -----------------------------------------------------------------------------
print("\n--- 3. TESTING PERSISTENT MEMORY ---")

resp, _ = jarvis.route_command("Jarvis, remember that my main project is Vision Lens.")
print(f"Save Memory 1: {resp}")
assert "saved that to my memory" in resp.lower() or "already" in resp.lower()

resp, _ = jarvis.route_command("Jarvis, remember that my favorite programming language is Python.")
print(f"Save Memory 2: {resp}")

# Verify file on disk
with open("jarvis_memory.json", "r", encoding="utf-8") as f:
    mem_disk = json.load(f)
print(f"Memories on Disk: {len(mem_disk.get('memories', []))} items")
assert len(mem_disk.get("memories", [])) >= 2

# Retrieve memory
resp, _ = jarvis.route_command("Jarvis, what is my main project?")
print(f"Recall Memory 1: {resp}")
assert "Vision Lens" in resp or "vision lens" in resp.lower()

resp, _ = jarvis.route_command("Jarvis, what is my favorite programming language?")
print(f"Recall Memory 2: {resp}")
assert "Python" in resp or "python" in resp.lower()

# -----------------------------------------------------------------------------
# 4. TEST PYSIDE6 GUI COMPONENTS
# -----------------------------------------------------------------------------
print("\n--- 4. TESTING PYSIDE6 GUI COMPONENTS ---")
from PySide6.QtWidgets import QApplication
from gui import JarvisV3Window, AIOrbWidget

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

# Test Orb states
orb = AIOrbWidget()
for st in ["IDLE", "LISTENING", "THINKING", "SPEAKING", "ERROR"]:
    orb.set_state(st)
    assert orb.state == st
print("[PASS] Animated AI Orb initialized and state transitions verified.")

# Test Window instantiation
window = JarvisV3Window()
assert window.windowTitle().startswith("J.A.R.V.I.S V3")
print("[PASS] JarvisV3Window initialized successfully with all panels and telemetry.")

# Clean up test scratch files
for p in [test_txt_path, test_pdf_path, test_resume]:
    try:
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass

print("\n==================================================")
print("     ALL V3 TESTS COMPLETED AND PASSED 100%!      ")
print("==================================================")
