with open("/Users/pranaysb/Documents/portfolio projects/Agentic/apiforge-ai/backend/app/api/stream.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_try = False
for i, line in enumerate(lines):
    if line.startswith("        try:"):
        in_try = True
        new_lines.append(line)
        continue
    
    if in_try:
        if line.startswith("        finally:"):
            in_try = False
            new_lines.append(line)
        elif line == "\n":
            new_lines.append(line)
        elif i >= 57 and i <= 165:
            new_lines.append("    " + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open("/Users/pranaysb/Documents/portfolio projects/Agentic/apiforge-ai/backend/app/api/stream.py", "w") as f:
    f.writelines(new_lines)

print("Done")
