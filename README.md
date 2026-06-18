# ⚔️ Genshin Team Optimizer

A free, open-source web app that fetches your Genshin Impact character data from **Enka Network** and uses an **evolutionary algorithm + GCSim** to find the strongest 4-person team from your own roster.

🌐 **Live app:** *(paste your Streamlit Cloud URL here after deploying)*

---

## What it does

1. **Reads your public showcase** from [Enka Network](https://enka.network) using your UID — no login or password required.
2. **Builds GCSim simulation configs** automatically from your characters' actual stats, weapons, and artifacts.
3. **Runs an evolutionary algorithm** that explores thousands of team combinations, simulating each one with [GCSim](https://gcsim.app).
4. **Returns a ranked Pareto front** — teams that are best across DPS, max single hit, and consistency simultaneously.

---

## Privacy

- **Your UID is public.** Genshin Impact UIDs are not secret — anyone can look up your showcase on Enka Network the same way this app does.
- **Only your displayed characters are read.** Enka Network only exposes characters you have chosen to show on your in-game profile. Hidden characters are never visible.
- **No data is stored.** Everything lives in your browser session and is discarded when you close the tab. Nothing is written to any database or server.
- **No authentication.** The app never asks for your HoYoverse account, password, or cookies.

---

## Optimizer modes

### Preset Rotations (faster)
Optimises **which characters** to put on the team. The rotation is chosen from a curated bank of proven templates (national, quickswap, hyperbloom, etc.). Good for a quick answer.

### Evolve Rotations (more powerful)
Co-evolves both the **team composition** and the **action sequence** simultaneously. The rotation is encoded as a gene and undergoes mutation and crossover alongside the team. Slower, but can discover non-obvious combos.

### Pareto mode
Instead of a single "best" answer, the optimizer maintains a *Pareto front* — a set of teams where no team is strictly worse than another across all three objectives:
- **DPS** — average damage per second
- **Max hit** — largest single damage instance
- **SD** — standard deviation (lower = more consistent)

This gives you options: a consistent team for Spiral Abyss, a nuke team for burst-check floors, etc.

---

## Hosting it yourself for free

### Option A — Streamlit Community Cloud (recommended)

1. **Fork this repo** on GitHub (or push it to your own repo).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, select your repo, set the main file to `app.py`.
4. Click **Deploy**. That's it — Streamlit handles the rest.

The app runs on a Linux container, so the GCSim binary downloads automatically on first use.

### Option B — Hugging Face Spaces

1. Create a new Space on [huggingface.co/spaces](https://huggingface.co/spaces).
2. Choose **Streamlit** as the SDK.
3. Upload all files in this repo.
4. The Space builds automatically from `requirements.txt`.

### Option C — Run locally

```bash
git clone https://github.com/YOUR_USERNAME/genshin-optimizer
cd genshin-optimizer
pip install -r requirements.txt
streamlit run app.py
```

GCSim is downloaded to `/tmp/gcsim` automatically on first run (Linux/macOS).  
On **Windows**, download `gcsim_windows_amd64.exe` from the [GCSim releases](https://github.com/genshinsim/gcsim/releases) page and place it in the project folder. Then set `GCSIM_PATH` in `gcsim_manager.py` accordingly.

---

## Fixing the GitHub / Python issue

If Python isn't being found when you push to GitHub Actions or clone and run locally, try these fixes:

**On Windows:**
```powershell
# Check Python is installed and in PATH
python --version
# If not found, reinstall from python.org and check "Add Python to PATH"
pip install -r requirements.txt
streamlit run app.py
```

**Wrong Python version:** Add a `runtime.txt` (already included) with `python-3.11`. Streamlit Cloud uses this to pin the correct version.

**pip not found:**
```bash
python -m pip install -r requirements.txt
```

**`enka` package errors:** Make sure you install `enka` (not `enkanetwork` or `enka-py` — those are older forks):
```bash
pip uninstall enka enka-api enka-py enkanetwork -y
pip install enka
```

---

## File structure

```
genshin-optimizer/
├── app.py                 # Streamlit UI
├── enka_fetcher.py        # Pulls character data from Enka Network
├── gcsim_manager.py       # Downloads GCSim binary, runs simulations
├── config_builder.py      # Converts character data → GCSim configs
├── optimizer_pareto.py    # EA with preset rotations (Pareto mode)
├── optimizer_rotation.py  # EA that co-evolves team + rotation
├── requirements.txt       # Python dependencies
├── runtime.txt            # Python version pin for Streamlit Cloud
└── .gitignore
```

---

## Configuration knobs

| Setting | What it does |
|---|---|
| **Sim duration** | How many seconds each GCSim run lasts. Longer = more accurate, but slower. |
| **Sim iterations** | How many Monte Carlo runs per team. Higher = lower variance. |
| **Population size** | Number of teams evaluated per generation. |
| **Generations** | How many evolutionary rounds to run. |
| **Mutation rate** | Probability of randomly changing a character or action. |
| **Lock characters** | Force specific characters to always appear in the team. |
| **Min character level** | Skip characters below this level. |
| **Pareto mode** | Optimise DPS + max hit + consistency simultaneously. |

**Rough time estimates on Streamlit Community Cloud (free tier):**

| Preset | ~Time |
|---|---|
| Quick Test | 1–3 min |
| Standard | 5–15 min |
| Thorough | 30–90 min |

---

## Credits

- [Enka Network](https://enka.network) — public Genshin Impact showcase API
- [GCSim](https://gcsim.app) — Genshin Impact damage simulator
- [Streamlit](https://streamlit.io) — free Python web app hosting
- Evolutionary algorithm design and integration by the project author

---

## License

MIT — do whatever you want, just don't remove the credits above.
