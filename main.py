"""
=============================================================================
J.A.R.V.I.S V3 - Main Application Launcher
=============================================================================
Launches the J.A.R.V.I.S V3 Desktop AI Assistant.
Default Mode: Futuristic PySide6 Desktop Graphical User Interface
Console Mode: python main.py --cli (or python jarvis.py)
=============================================================================
"""

import sys
import os

# Ensure current working directory is in sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import jarvis


def main():
    """Main application dispatcher for J.A.R.V.I.S V3."""
    # Check if CLI/console mode requested via arguments
    if "--cli" in sys.argv or "--console" in sys.argv:
        print("\nStarting J.A.R.V.I.S V3 in Console Mode...\n")
        jarvis.main()
        return

    # Launch PySide6 Desktop GUI by default
    try:
        from gui import launch_gui
        sys.exit(launch_gui())
    except ImportError as e:
        print(f"\n[Warning: PySide6 could not be loaded: {e}]")
        print("Falling back to terminal console mode...\n")
        jarvis.main()
    except Exception as e:
        print(f"\n[Error launching GUI: {e}]")
        print("Falling back to terminal console mode...\n")
        jarvis.main()


if __name__ == "__main__":
    main()
