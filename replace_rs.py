import os
import re

# We will search for Rs or rs or RS or Rs. or RS.
# If we find it, we replace it with PKR
# We use lookbehinds and lookaheads to ensure we don't disrupt class names like 'rs-container'
# Our pattern requires that the characters preceding and following the currency 
# are NOT letters, dashes, or underscores.

# This means:
# (?<![a-zA-Z\-_]) -> not preceded by letter, -, _
# \b(?:Rs|rs|RS)\.? -> match the actual currency string optionally with a dot
# (?![a-zA-Z\-_]) -> not followed by letter, -, _

pattern = re.compile(r'(?<![a-zA-Z\-_])\b(?:Rs|rs|RS)\.?(?![a-zA-Z\-_])')

root_dir = 'app'
files_changed = 0
replacements_made = 0

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(('.html', '.py', '.js', '.css', '.txt')):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Perform replacement
            new_content, count = pattern.subn('PKR', content)
            
            if count > 0:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_changed += 1
                replacements_made += count
                print(f"Replaced {count} instances in {path}")

print(f"\nSuccessfully made {replacements_made} replacements across {files_changed} files.")
