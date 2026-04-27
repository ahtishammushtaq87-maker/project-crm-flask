import os

path = 'app/routes/sales.py'
with open(path, 'rb') as f:
    data = f.read()

# Replace the problematic bytes (em dash in some encodings is x97 or similar)
# We'll just replace the whole Select Group string with something safe.
# We'll search for the bytes of 'Select Group' and go backwards/forwards.

safe_bytes = b"Select Group"
if safe_bytes in data:
    # Let's try to just replace any non-ascii bytes in the file
    new_data = bytearray()
    for b in data:
        if b < 128:
            new_data.append(b)
        else:
            new_data.append(ord('-')) # Replace with dash
    
    with open(path, 'wb') as f:
        f.write(new_data)
    print("Cleaned non-ASCII characters from app/routes/sales.py")
else:
    print("Select Group not found in binary data?")
