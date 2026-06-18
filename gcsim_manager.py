"""
gcsim_manager.py
Downloads the GCSim binary on first use and provides a helper to run configs.
"""
import os
import stat
import json
import tempfile
import subprocess
import requests

GCSIM_VERSION = "v2.42.2"
GCSIM_URL = (
    f"https://github.com/genshinsim/gcsim/releases/download/"
    f"{GCSIM_VERSION}/gcsim_linux_amd64"
)
GCSIM_PATH = "/tmp/gcsim"


def ensure_gcsim(status_callback=None) -> str:
    """Download gcsim binary if needed. Returns path to binary."""
    if os.path.exists(GCSIM_PATH) and os.access(GCSIM_PATH, os.X_OK):
        return GCSIM_PATH

    if status_callback:
        status_callback(f"Downloading GCSim {GCSIM_VERSION}...")

    resp = requests.get(GCSIM_URL, stream=True, timeout=60)
    resp.raise_for_status()

    with open(GCSIM_PATH, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    # Make executable
    st = os.stat(GCSIM_PATH)
    os.chmod(GCSIM_PATH, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    if status_callback:
        status_callback("GCSim ready.")
    return GCSIM_PATH


def run_gcsim(config_str: str, gcsim_bin: str = GCSIM_PATH,
              iterations: int = 150, duration: int = 20) -> dict:
    """
    Write config to a temp file, run gcsim, parse JSON output.
    Returns dict with keys: dps, max_hit, sd (all float, 0.0 on error).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(config_str)
        cfg_path = f.name
    out_path = cfg_path + ".json"

    try:
        result = subprocess.run(
            [gcsim_bin, "-c", cfg_path, "-out", out_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return {"dps": 0.0, "max_hit": 0.0, "sd": 0.0}

        with open(out_path, "r") as jf:
            data = json.load(jf)

        stats = data["statistics"]
        dps = float(stats["dps"]["mean"])
        sd = float(stats["dps"]["sd"])

        max_hit = 0.0
        buckets_info = stats.get("damage_buckets")
        if buckets_info:
            for bucket in buckets_info.get("buckets", []):
                if isinstance(bucket, dict):
                    max_hit = max(max_hit, bucket.get("max", 0.0))
        if max_hit == 0.0:
            max_hit = float(stats.get("total_damage", 0.0))

        return {"dps": dps, "max_hit": max_hit, "sd": sd}

    except Exception:
        return {"dps": 0.0, "max_hit": 0.0, "sd": 0.0}
    finally:
        for p in [cfg_path, out_path]:
            if os.path.exists(p):
                os.unlink(p)
