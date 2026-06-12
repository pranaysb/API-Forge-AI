import re

with open("/Users/pranaysb/Documents/portfolio projects/Agentic/apiforge-ai/backend/app/api/stream.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_try = False
for line in lines:
    if line.strip() == "try:":
        in_try = True
        new_lines.append(line)
        continue
        
    if in_try and line.startswith("        ") and not line.strip().startswith("finally:"):
        new_lines.append("    " + line) # Add one level of indentation
    elif in_try and line.strip() == "finally:":
        in_try = False
        new_lines.append(line)
    elif in_try and line.startswith("        finally:"):
        in_try = False
        new_lines.append(line)
    elif in_try and line == "\n":
        new_lines.append(line)
    elif in_try:
        # Check if line was correctly indented previously
        if line.startswith("        "):
            new_lines.append("    " + line)
        elif line.startswith("    "):
            # It was dedented previously?
            if line.strip() == "":
                new_lines.append(line)
            else:
                new_lines.append("    " + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)
