import os
import jarvis

test_cases = [
    ("Hello Jarvis.", False),
    ("What time is it?", False),
    ("What is today's date?", False),
    ("Open YouTube.", False),
    ("Open Calculator.", False),
    ("Open Downloads.", False),
    ("Open Documents.", False),
    ("Increase volume.", False),
    ("Decrease volume.", False),
    ("Mute volume.", False),
    ("Search the web for Python news.", False),
    ("What is my RAM usage?", False),
    ("What is my CPU usage?", False),
    ("What operating system am I using?", False),
    ("Calculate 45 * 23", False),
    ("Calculate 1000 / 8", False),
    ("What is 25 percent of 800?", False),
    ("Take a screenshot.", False),
    ("What can you do?", False),
    ("System status.", False),
    ("Find my Python files.", False),
    ("Read requirements.txt", False),
    ("Remember that my name is Zeeshan.", False),
    ("Remember that my favorite language is Python.", False),
    ("Remember that I am working on a data science project.", False),
    ("What is my name?", False),
    ("What is my favorite language?", False),
    ("What project am I working on?", False),
    ("What do you remember about me?", False),
    ("Look at my screen.", False),
    ("What is Python?", False),  # Tests Gemini AI fallback or API key notice
    ("Goodbye Jarvis.", True),
]

print("=== RUNNING JARVIS V2 COMMAND ROUTER TEST SUITE ===\n")
all_passed = True
for prompt, expected_exit in test_cases:
    resp, should_exit = jarvis.route_command(prompt)
    print(f"INPUT:       {prompt}")
    print(f"RESPONSE:    {resp}")
    print(f"SHOULD EXIT: {should_exit}")
    print("-" * 65)
    if should_exit != expected_exit:
        print(f"FAILED on exit status for: {prompt}")
        all_passed = False

# Test Confirmation Flow for memory clearing
print("\n=== TESTING CONFIRMATION SYSTEM ===")
resp1, _ = jarvis.route_command("Clear all my memory.")
print(f"REQUEST CLEAR:  {resp1}")
resp2, _ = jarvis.route_command("Yes")
print(f"CONFIRMATION:   {resp2}")

if "permanently cleared" in resp2.lower() or "cleared" in resp2.lower():
    print("Confirmation test passed successfully!")
else:
    print("Confirmation test failed!")
    all_passed = False

if all_passed:
    print("\nALL V2 TEST SCENARIOS PASSED SUCCESSFULLY!")
else:
    print("\nSOME TESTS FAILED!")
