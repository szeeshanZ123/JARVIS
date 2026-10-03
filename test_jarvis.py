import os
import jarvis

test_cases = [
    ("Hello Jarvis.", False),
    ("What time is it?", False),
    ("What is today's date?", False),
    ("Open YouTube.", False),
    ("Open Calculator.", False),
    ("Search the web for Python Pandas.", False),
    ("What is my RAM usage?", False),
    ("What is my CPU usage?", False),
    ("What operating system am I using?", False),
    ("Calculate 45 * 23", False),
    ("Calculate 1000 / 8", False),
    ("What is 25 percent of 800?", False),
    ("Take a screenshot.", False),
    ("What can you do?", False),
    ("Who created you?", False),
    ("What is Python?", False),  # Will test Gemini fallback (or missing key handling if unset)
    ("Goodbye Jarvis.", True),
]

print("=== RUNNING JARVIS COMMAND ROUTER TEST SUITE ===\n")
all_passed = True
for prompt, expected_exit in test_cases:
    resp, should_exit = jarvis.route_command(prompt)
    print(f"INPUT:       {prompt}")
    print(f"RESPONSE:    {resp}")
    print(f"SHOULD EXIT: {should_exit}")
    print("-" * 55)
    if should_exit != expected_exit:
        print(f"FAILED on exit status for: {prompt}")
        all_passed = False

if all_passed:
    print("\nALL TEST SCENARIOS PASSED SUCCESSFULLY!")
else:
    print("\nSOME TESTS FAILED!")
