import sys
import re
sys.stdout.reconfigure(encoding='utf-8')

file_path = "d:/git/problem-first-AI-capstone-team13/final-capstone-system-design-FINAL-lean-per-ticker.md"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Print lines around the definition of canonical extraction in Section 6.1
start_idx = content.find("## 6.1 Architecture and design")
if start_idx != -1:
    print("=== Section 6.1 Snippet ===")
    print(content[start_idx:start_idx+1500])

# Search for loop / batch / parallel / article mentions in relation to LLM call in extraction
print("\n=== Mentions of article loops or batching ===")
for match in re.finditer(r"(?i)extraction", content):
    pos = match.start()
    snippet = content[max(0, pos-100):min(len(content), pos+100)]
    snippet_cleaned = snippet.strip().replace('\n', ' ')
    print(f"Match: {snippet_cleaned}")

