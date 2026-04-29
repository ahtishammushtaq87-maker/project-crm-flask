import os
import re

# We will search for Rs or rs or RS or Rs. or RS.
# Often it is preceded or followed by a space.
rs_pattern = re.compile(r'\b(Rs\.?|RS\.?|rs\.?)(?=\s|\b|$)')

root_dir = 'app'
count = 0
files_with_rs = []

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(('.html', '.py', '.js', '.css')):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                matches = len(rs_pattern.findall(content))
                if matches > 0:
                    count += matches
                    files_with_rs.append((path, matches))

print(f'Total occurrences: {count}')
print(f'Files: {len(files_with_rs)}')
for f, c in sorted(files_with_rs, key=lambda x: x[1], reverse=True)[:50]:
    print(f'{c:3d} matches in {f}')
