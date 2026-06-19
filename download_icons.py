"""
download_icons.py  —  run this ONCE locally to download all character icons.

Usage:
    python download_icons.py

Downloads to assets/icons/ in the project folder.
Commit those files to GitHub and the app will use them as local images,
no network dependency needed.
"""
import os, time, requests
from character_icons import ICON_MAP, ENKA_CDN

OUT = "assets/icons"
os.makedirs(OUT, exist_ok=True)

session = requests.Session()
session.headers["User-Agent"] = "genshin-optimizer/1.0"

for name, key in ICON_MAP.items():
    # Download circle crop (used in cards)
    fname = f"{OUT}/{name}.png"
    if os.path.exists(fname):
        print(f"  skip  {name}")
        continue
    url = f"{ENKA_CDN}/UI_AvatarIcon_{key}_Circle.png"
    try:
        r = session.get(url, timeout=10)
        r.raise_for_status()
        with open(fname, "wb") as f:
            f.write(r.content)
        print(f"  ✓  {name}")
    except Exception as e:
        print(f"  ✗  {name}: {e}")
    time.sleep(0.15)   # be polite to the CDN

print(f"\nDone — {len(os.listdir(OUT))} icons in {OUT}/")
print("Now commit the assets/ folder to your GitHub repo.")
