"""
gcsim_manager.py
Downloads the correct GCSim binary for the current platform on first use.
"""
import os
import stat
import json
import platform
import tempfile
import subprocess
import requests

GCSIM_VERSION = "v2.42.2"
BASE_URL = f"https://github.com/genshinsim/gcsim/releases/download/{GCSIM_VERSION}"


def _get_binary_name() -> str:
    system  = platform.system().lower()
    machine = platform.machine().lower()
    if system == "linux":
        return "gcsim_linux_amd64"
    elif system == "darwin":
        return "gcsim_darwin_arm64" if ("arm" in machine or "aarch" in machine) else "gcsim_darwin_amd64"
    elif system == "windows":
        return "gcsim_windows_amd64.exe"
    return "gcsim_linux_amd64"   # Streamlit Cloud fallback


GCSIM_PATH = f"/tmp/{_get_binary_name()}"


def ensure_gcsim(status_callback=None) -> str:
    if os.path.exists(GCSIM_PATH) and os.access(GCSIM_PATH, os.X_OK):
        return GCSIM_PATH

    binary_name = _get_binary_name()
    url = f"{BASE_URL}/{binary_name}"

    if status_callback:
        status_callback(f"Downloading GCSim {GCSIM_VERSION} ({binary_name})…")

    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()

    with open(GCSIM_PATH, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    st = os.stat(GCSIM_PATH)
    os.chmod(GCSIM_PATH, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    if status_callback:
        status_callback("GCSim ready.")
    return GCSIM_PATH


def run_gcsim(config_str: str, gcsim_bin: str = GCSIM_PATH,
              iterations: int = 150, duration: int = 20) -> dict:
    import subprocess
    import tempfile
    import os
    import json
    import signal
    import time

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(config_str)
        cfg_path = f.name
    out_path = cfg_path + ".json"

    try:
        proc = subprocess.Popen(
            [gcsim_bin, "-c", cfg_path, "-out", out_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        # ✅ Much tighter timeout: sim_duration + 10s buffer, min 15s
        timeout = max(15, duration + 10)
        start = time.time()
        while proc.poll() is None:
            if time.time() - start > timeout:
                proc.kill()
                proc.wait(timeout=1)
                return {"dps": 0.0, "max_hit": 0.0, "sd": 0.0, "error": "timeout"}
            time.sleep(0.5)
        
        stdout, stderr = proc.communicate(timeout=5)
        if proc.returncode != 0:
            return {"dps": 0.0, "max_hit": 0.0, "sd": 0.0,
                    "error": stderr[:300] if stderr else "unknown error"}

        with open(out_path, "r") as jf:
            data = json.load(jf)

        stats = data["statistics"]
        dps = float(stats["dps"]["mean"])
        sd = float(stats["dps"]["sd"])
        max_hit = 0.0
        for bucket in stats.get("damage_buckets", {}).get("buckets", []):
            if isinstance(bucket, dict):
                max_hit = max(max_hit, bucket.get("max", 0.0))
        if max_hit == 0.0:
            max_hit = float(stats.get("total_damage", 0.0))

        return {"dps": dps, "max_hit": max_hit, "sd": sd}

    except Exception as e:
        return {"dps": 0.0, "max_hit": 0.0, "sd": 0.0, "error": str(e)}
    finally:
        for p in [cfg_path, out_path]:
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass