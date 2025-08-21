def scan_null_bytes(filepath):
    with open(filepath, "rb") as f:  # pakai mode binary supaya null byte kebaca
        lines = f.readlines()

    found = False
    for i, line in enumerate(lines, start=1):
        if b"\x00" in line:
            print(f"Null byte ditemukan di baris {i}: {line}")
            found = True

    if not found:
        print("✅ Tidak ada null byte di file ini.")

# Ganti dengan path file kamu
scan_null_bytes("price_researcher.py")
