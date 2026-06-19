"""
app.py  –  Genshin Team Optimizer
"""
import io
import json
import os
import queue
import threading
import time
import traceback

import pandas as pd
import streamlit as st

# Module-level imports — fail loudly at startup rather than during a button click
from config_builder import build_character_configs, to_gcsim_name

# character_icons.py is a new file — import defensively so the app still
# loads even if the user hasn't added it yet
try:
    from character_icons import get_icon_url as _get_icon_url
except ImportError:
    def _get_icon_url(name: str, circle: bool = True) -> str:
        return ""  # graceful no-op if file is missing

# ── Page config ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Genshin Team Optimizer",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Design tokens ─────────────────────────────────────────────────── */
:root {
    --gold:    #d4af37;
    --gold-dim: rgba(212,175,55,0.15);
    --gold-border: rgba(212,175,55,0.35);
    --blue:    #7eb8d4;
    --bg-dark: #0d0b18;
    --bg-mid:  #161230;
    --card-bg: rgba(255,255,255,0.04);
    --card-hover: rgba(255,255,255,0.08);
    --text-dim: #9a96b0;
}

/* ── Global background ─────────────────────────────────────────────── */
.stApp {
    background:
        radial-gradient(ellipse at 20% 10%, rgba(100,60,180,0.18) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 90%, rgba(30,80,150,0.18) 0%, transparent 50%),
        linear-gradient(160deg, #0d0b18 0%, #131028 50%, #0a1020 100%);
    font-family: 'Segoe UI', system-ui, sans-serif;
}

/* ── Sidebar ───────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: rgba(10,8,22,0.97);
    border-right: 1px solid var(--gold-border);
}
[data-testid="stSidebar"] .stMarkdown h3 {
    color: var(--gold);
    letter-spacing: 0.05em;
}

/* ── Character cards ───────────────────────────────────────────────── */
.char-card {
    background: var(--card-bg);
    border: 1px solid var(--gold-border);
    border-radius: 12px;
    padding: 12px 8px;
    margin-bottom: 8px;
    text-align: center;
    transition: background 0.15s;
}
.char-card:hover { background: var(--card-hover); }
.char-card .cname {
    color: var(--gold);
    font-weight: 700;
    font-size: 0.88rem;
    margin: 6px 0 2px;
    letter-spacing: 0.02em;
}
.char-card .clevel {
    color: var(--blue);
    font-size: 0.72rem;
    margin-bottom: 4px;
}
.char-card .cstats {
    color: var(--text-dim);
    font-size: 0.68rem;
    line-height: 1.7;
}
.char-card .cweapon {
    color: #c8bfff;
    font-size: 0.7rem;
    margin: 3px 0;
}
.char-card .cset {
    color: var(--gold);
    font-size: 0.67rem;
    opacity: 0.85;
}
/* Make Streamlit images round inside cards */
.char-card img,
[data-testid="stImage"] img {
    border-radius: 50% !important;
    border: 2px solid var(--gold-border) !important;
    background: rgba(0,0,0,0.3);
}

/* ── Result cards ──────────────────────────────────────────────────── */
.result-card {
    background: var(--card-bg);
    border: 1px solid var(--blue);
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.result-card:hover { background: var(--card-hover); }

/* ── Generation log ────────────────────────────────────────────────── */
.gen-log {
    background: #070610;
    border: 1px solid rgba(100,80,200,0.3);
    border-radius: 8px;
    padding: 12px;
    font-family: 'Courier New', monospace;
    font-size: 0.76rem;
    color: #7fffb0;
    max-height: 200px;
    overflow-y: auto;
    line-height: 1.6;
}

/* ── Streamlit widget overrides ────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #c49b2e, #e8c547) !important;
    color: #0d0b18 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #e8c547, #f5d85a) !important;
    transform: translateY(-1px);
}
.stProgress > div > div {
    background: linear-gradient(90deg, var(--gold), var(--blue)) !important;
}

/* ── Section divider ───────────────────────────────────────────────── */
hr { border-color: var(--gold-border) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────

DEFAULTS = {
    "characters_df": None,
    "player_info": None,
    "opt_running": False,
    "opt_thread": None,
    "progress_q": None,
    "result_q": None,
    "stop_flag": [False],
    "progress_log": [],
    "best_obj": None,
    "pareto_summary": None,
    "pareto_configs": None,
    "best_config": None,
    "warnings": [],
    "abyss_result": None,
    "status": "idle",          # idle | downloading | running | done | error
    "status_msg": "",
    "gen_done": 0,
    "gen_total": 1,
    "ind_done": 0,
    "ind_total": 0,
    # Freeze optimizer params when Start is clicked so reruns don't change them
    "frozen_params": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── GCSim (download once per session) ────────────────────────────────────

from gcsim_manager import ensure_gcsim

@st.cache_resource(show_spinner=False)
def _cached_gcsim():
    return ensure_gcsim()


# ── Helpers ───────────────────────────────────────────────────────────────

def _fmt(val, decimals=0):
    """Safely format a numeric stat value."""
    try:
        v = float(val)
        return f"{v:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(val) if val else "—"

def char_card(row):
    name   = row["Character Name"]
    # Escape HTML special chars so names with <, >, & don't break cards
    import html as _html
    name   = _html.escape(str(name))
    level  = int(row.get("Character Level", 0) or 0)
    cons   = int(row.get("Character Constellations", 0) or 0)
    weapon = row.get("Weapon Name", "—") or "—"
    fr     = int(row.get("Character Friendship", 0) or 0)
    bonus  = row.get("Artifact Set Bonus", "—") or "—"
    hp     = _fmt(row.get("HP", ""))
    atk    = _fmt(row.get("ATK", ""))
    def_   = _fmt(row.get("DEF", ""))
    cr     = row.get("Crit Rate", "")
    cd     = row.get("Crit DMG", "")

    # Icon: try local file first (if download_icons.py was run),
    # then the URL stored in the DataFrame, then the hardcoded mapping.
    local_path = f"assets/icons/{name}.png"
    icon_url   = str(row.get("Icon URL", "") or "")
    if not icon_url or "UI_" not in icon_url:
        icon_url = _get_icon_url(name, circle=True)

    with st.container():
        ini = name[0].upper() if name else "?"
        ph = (
            '<div style="width:90px;height:90px;border-radius:50%;'
            'border:2px solid rgba(212,175,55,0.4);background:rgba(212,175,55,0.1);'
            'display:flex;align-items:center;justify-content:center;'
            'color:#d4af37;font-size:1.5rem;font-weight:700;">' + ini + "</div>"
        )
        if os.path.exists(local_path):
            import base64
            try:
                with open(local_path, "rb") as _lf:
                    _b64 = base64.b64encode(_lf.read()).decode()
                icon_html = (
                    '<img src="data:image/png;base64,' + _b64
                    + '" style="width:90px;height:90px;border-radius:50%;'
                    'border:2px solid rgba(212,175,55,0.4);object-fit:cover;">'
                )
            except Exception:
                icon_html = ph
        elif icon_url:
            hidden_ph = ph.replace("display:flex", "display:none")
            icon_html = (
                '<img src="' + icon_url + '" width="90" height="90" '
                'style="border-radius:50%;border:2px solid rgba(212,175,55,0.4);object-fit:cover;" '
                'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';">'
                + hidden_ph
            )
        else:
            icon_html = ph
        st.markdown(
            '<div style="display:flex;justify-content:center;margin-bottom:4px">'
            + icon_html + "</div>",
            unsafe_allow_html=True,
        )


        st.markdown(f"""
        <div class="char-card">
          <div class="cname">{name}</div>
          <div class="clevel">Lv {level} &nbsp;·&nbsp; C{cons} &nbsp;·&nbsp; F{fr}</div>
          <div class="cweapon">🗡 {weapon}</div>
          <div class="cstats">
            ❤ {hp} &nbsp; ⚔ {atk} &nbsp; 🛡 {def_}<br>
            CR {cr} &nbsp;/&nbsp; CD {cd}
          </div>
          <div class="cset">{bonus}</div>
        </div>""", unsafe_allow_html=True)
def _merge_df(existing, new_df):
    combined = pd.concat([existing, new_df], ignore_index=True)
    # Normalise UID to string and Character Name to stripped string so that
    # "618867267", 618867267, and "618867267.0" all match each other,
    # preventing duplicate rows when mixing CSV uploads with live fetches.
    combined["UID"] = combined["UID"].astype(str).str.strip().str.split(".").str[0]
    combined["Character Name"] = combined["Character Name"].astype(str).str.strip()
    return combined.drop_duplicates(
        subset=["UID", "Character Name"], keep="last"
    ).reset_index(drop=True)


def status_bar(level, msg):
    """Use native Streamlit callouts — stable across reruns, no emoji flicker."""
    if level == "idle":
        st.info(msg, icon="💤")
    elif level in ("downloading", "running"):
        st.warning(msg, icon="⚙️")
    elif level == "done":
        st.success(msg, icon="✅")
    elif level == "error":
        st.error(msg, icon="🚨")


# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### ⚔️ Team Optimizer")
    st.markdown("---")

    # ── 1. Load characters ────────────────────────────────────────────────
    st.markdown("**1 · Load Characters**")
    st.caption(
        "Enka shows 8–12 characters at a time. "
        "Swap them in-game then click **＋ Merge** to add more."
    )

    uid_input = st.text_input("Genshin UID", placeholder="Your 9-digit UID",
                               disabled=st.session_state.opt_running)

    c1, c2, c3 = st.columns(3)
    fetch_clicked = c1.button("Fetch",   use_container_width=True, disabled=st.session_state.opt_running,
                               help="Load showcase, replacing current list.")
    add_clicked   = c2.button("＋ Merge", use_container_width=True, disabled=st.session_state.opt_running,
                               help="Add new characters to the existing list.")
    if c3.button("Clear", use_container_width=True, disabled=st.session_state.opt_running):
        for k in ("characters_df","player_info","best_config","pareto_summary",
                  "pareto_configs","status","progress_log","best_obj","warnings","gen_done"):
            st.session_state[k] = DEFAULTS.get(k)
        st.session_state.status = "idle"
        st.rerun()

    if (fetch_clicked or add_clicked) and uid_input.strip():
        with st.spinner("Fetching…"):
            try:
                from enka_fetcher import fetch_characters
                new_df, info = fetch_characters(int(uid_input.strip()))
                existing = st.session_state.characters_df
                if add_clicked and existing is not None:
                    merged = _merge_df(existing, new_df)
                    st.session_state.characters_df = merged
                    st.success(f"Merged — total **{len(merged)}** characters.")
                else:
                    st.session_state.characters_df = new_df
                    st.session_state.player_info = info
                    st.success(f"Loaded **{len(new_df)}** characters for **{info['nickname']}**.")
            except Exception as e:
                err_str = str(e)
                hint = ""
                if "SSL" in err_str or "certificate" in err_str.lower():
                    hint = " (SSL error — on Mac, run: pip install certifi)"
                elif "Cannot connect" in err_str or "ClientConnectorError" in err_str:
                    hint = " (Network error — check your internet connection)"
                elif "EnkaAPIError" in err_str or "retcode" in err_str:
                    hint = " (Enka API error — make sure your showcase is public in-game)"
                elif "401" in err_str or "403" in err_str:
                    hint = " (UID not found or showcase is private)"
                st.error(f"Fetch failed: {e}{hint}")

    csv_file = st.file_uploader("…or upload CSV", type=["csv"],
                                 disabled=st.session_state.opt_running)
    if csv_file is not None:
        try:
            new_df = pd.read_csv(csv_file)
            existing = st.session_state.characters_df
            if existing is not None:
                merged = _merge_df(existing, new_df)
                st.session_state.characters_df = merged
                st.success(f"CSV merged — total **{len(merged)}** characters.")
            else:
                st.session_state.characters_df = new_df
                st.session_state.player_info = {
                    "nickname": str(new_df.get("Player Nickname", ["CSV"]).iloc[0]),
                    "level": int(new_df.get("Player Level", [0]).iloc[0] or 0),
                    "signature": "",
                    "uid": str(new_df.get("UID", ["—"]).iloc[0]),
                }
                st.success(f"Loaded **{len(new_df)}** rows.")
        except Exception as e:
            st.error(f"CSV error: {e}")

    if st.session_state.characters_df is not None:
        n = len(st.session_state.characters_df)
        st.markdown(
            f'<div style="text-align:center;padding:5px;border:1px solid #d4af37;'
            f'border-radius:6px;color:#d4af37;font-weight:700">📋 {n} character{"s" if n!=1 else ""}</div>',
            unsafe_allow_html=True)

        # Download current roster as CSV
        csv_bytes = st.session_state.characters_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇ Download roster CSV",
            data=csv_bytes,
            file_name="genshin_data_export.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=st.session_state.opt_running,
            help=(
                "Saves all loaded characters to a CSV you can re-upload later. "
                "To update a character's stats, display them in-game and click ＋ Merge — "
                "their row is automatically replaced with the fresh data."
            ),
        )

    st.markdown("---")

    # ── 2. Configure ──────────────────────────────────────────────────────
    if st.session_state.characters_df is not None:
        st.markdown("**2 · Configure**")

        mode = st.radio(
            "Optimizer mode",
            ["Preset Rotations (faster)", "Evolve Rotations"],
            disabled=st.session_state.opt_running,
        )

        char_names = sorted(st.session_state.characters_df["Character Name"].unique())
        # Abyss mode toggle shown here so lock UI can adapt
        abyss_mode_early = st.checkbox(
            "⚔️ Spiral Abyss mode (two teams)",
            key="abyss_toggle",
            disabled=st.session_state.opt_running,
            help="Optimizes two separate teams. Characters on Team 1 can't appear on Team 2.",
        )

        if abyss_mode_early:
            st.caption("Lock characters to specific teams for Abyss mode.")
            lock_t1 = st.multiselect(
                "🔒 Lock to Team 1",
                options=char_names,
                max_selections=4,
                disabled=st.session_state.opt_running,
                key="lock_t1",
            )
            lock_t2 = st.multiselect(
                "🔒 Lock to Team 2",
                options=[c for c in char_names if c not in lock_t1],
                max_selections=4,
                disabled=st.session_state.opt_running,
                key="lock_t2",
            )
            lock_chars = lock_t1  # used for conflict checks below
        else:
            lock_t1 = []
            lock_t2 = []
            lock_chars = st.multiselect(
                "🔒 Lock IN (always on team)",
                options=char_names,
                max_selections=4,
                disabled=st.session_state.opt_running,
                help="These characters will always appear in every team.",
            )

        ban_chars = st.multiselect(
            "🚫 Lock OUT (never on team)",
            options=char_names,
            disabled=st.session_state.opt_running,
            help="Exclude characters from all teams — useful for benching weaker characters.",
        )
        _all_locked = list(lock_t1) + list(lock_t2) + (lock_chars if not abyss_mode_early else [])
        _conflicts = [c for c in _all_locked if c in ban_chars]
        if _conflicts:
            st.warning(f"⚠️ {', '.join(_conflicts)} can't be locked in and locked out.")

        with st.expander("⚙️ Advanced settings"):
            preset_name = st.selectbox(
                "Quick preset",
                ["Quick Test", "Standard", "Thorough", "Custom"],
                index=1,
                disabled=st.session_state.opt_running,
            )
            PRESETS = {
                "Quick Test": dict(sim_duration=15, sim_iterations=5,  population_size=20, generations=5),
                "Standard":   dict(sim_duration=30, sim_iterations=20, population_size=50, generations=20),
                "Thorough":   dict(sim_duration=90, sim_iterations=50, population_size=80, generations=40),
            }
            p = PRESETS.get(preset_name, {})
            sim_duration    = st.slider("Sim duration (s)",    5,  180, p.get("sim_duration",    30), disabled=st.session_state.opt_running)
            sim_iterations  = st.slider("Sim iterations",       1,  500, p.get("sim_iterations",  20), disabled=st.session_state.opt_running)
            population_size = st.slider("Population size",     10,  200, p.get("population_size", 50), disabled=st.session_state.opt_running)
            generations     = st.slider("Generations",          5,  100, p.get("generations",     20), disabled=st.session_state.opt_running)
            mutation_rate   = st.slider("Mutation rate",      0.05, 0.6, 0.15, step=0.05, disabled=st.session_state.opt_running)
            min_char_level  = st.slider("Min character level",  1,   90,  50,  disabled=st.session_state.opt_running)
            pareto_on       = st.checkbox("Pareto multi-objective", value=True, disabled=st.session_state.opt_running)
            traveler_default = st.selectbox(
                "Traveler element",
                ["anemo","geo","electro","dendro","hydro","pyro","cryo"],
                disabled=st.session_state.opt_running,
            )

            st.markdown("**Starting energy**")
            start_energy = st.select_slider(
                "Starting energy per character",
                options=[0, 25, 50, 75, 100],
                value=100,
                disabled=st.session_state.opt_running,
                help=(
                    "100 = all bursts available immediately (standard GCSim default, "
                    "gives highest DPS but is optimistic). "
                    "0 = realistic — characters must build energy before bursting. "
                    "Stygian Onslaught always starts at 0."
                ),
            )

            st.markdown("**Enemy**")
            ENEMY_PRESETS = {
                "Spiral Abyss F12": dict(level=100, resist=10),
                "Weekly Boss":      dict(level=95,  resist=10),
                "Overworld Elite":  dict(level=90,  resist=10),
                "Custom":           dict(level=100, resist=10),
            }
            enemy_preset = st.selectbox("Enemy preset", list(ENEMY_PRESETS.keys()),
                                         disabled=st.session_state.opt_running)
            ep = ENEMY_PRESETS[enemy_preset]
            _custom = (enemy_preset == "Custom") and not st.session_state.opt_running
            enemy_level      = st.slider("Enemy level", 1, 100, ep["level"], disabled=not _custom)
            enemy_resist_pct = st.slider("Enemy resistance (%)", 0, 75, ep["resist"], disabled=not _custom)
            if not _custom:
                enemy_level, enemy_resist_pct = ep["level"], ep["resist"]



        abyss_mode = abyss_mode_early   # already set above

        st.markdown("---")
        st.markdown("**3 · Run**")

        run_col, stop_col = st.columns(2)
        run_clicked  = run_col.button("▶ Start", use_container_width=True,
                                       disabled=st.session_state.opt_running, type="primary")
        stop_clicked = stop_col.button("⏹ Stop", use_container_width=True,
                                        disabled=not st.session_state.opt_running)

        if stop_clicked and st.session_state.opt_running:
            st.session_state.stop_flag[0] = True
            st.session_state.status = "running"
            st.session_state.status_msg = "Stopping… (finishing current generation, please wait)"
            # ✅ Force the running loop to check the flag more often
            st.rerun()

        if run_clicked and not st.session_state.opt_running:
            # Block if lock-in and lock-out conflict
            # Block if any locked character is also banned
            if abyss_mode_early:
                all_locked = lock_t1 + lock_t2
            else:
                all_locked = lock_chars

            _conflicts = [c for c in all_locked if c in ban_chars]
            if _conflicts:
                st.error(
                    f"Remove {', '.join(_conflicts)} from either Lock IN (or Team locks) or Lock OUT before running."
                )
                st.stop()

            # ── Resolve locked char names ──────────────────────────────────
            df_now = st.session_state.characters_df

            def _resolve_list(names):
                out = []
                for lc in names:
                    rows = df_now[df_now["Character Name"] == lc]
                    if not rows.empty:
                        gname = to_gcsim_name(lc, rows.iloc[0], [], {}, traveler_default)
                        if gname:
                            out.append(gname)
                return out

            locked_gcsim    = _resolve_list(lock_chars)
            locked_gcsim_t1 = _resolve_list(lock_t1)
            locked_gcsim_t2 = _resolve_list(lock_t2)
            banned_gcsim    = _resolve_list(ban_chars)

            st.session_state.frozen_params = dict(
                mode=mode,
                locked_gcsim=locked_gcsim,
                locked_gcsim_t1=locked_gcsim_t1,
                locked_gcsim_t2=locked_gcsim_t2,
                banned_gcsim=banned_gcsim,
                sim_duration=sim_duration,
                sim_iterations=sim_iterations,
                population_size=population_size,
                generations=generations,
                mutation_rate=mutation_rate,
                min_char_level=min_char_level,
                pareto_on=pareto_on,
                traveler_default=traveler_default,
                enemy_level=enemy_level,
                enemy_resist=enemy_resist_pct / 100.0,
                start_energy=start_energy,
                abyss_mode=abyss_mode,
            )

            # ── Reset progress state ───────────────────────────────────────
            st.session_state.stop_flag     = [False]
            st.session_state.progress_log  = []
            st.session_state.best_obj      = None
            st.session_state.pareto_summary= None
            st.session_state.pareto_configs= None
            st.session_state.best_config   = None
            st.session_state.warnings      = []
            st.session_state.abyss_result  = None   # clear previous abyss run
            st.session_state.gen_done      = 0
            st.session_state.gen_total     = generations
            st.session_state.status        = "downloading"
            st.session_state.status_msg    = "Downloading GCSim binary (first run only)…"
            st.session_state.opt_running   = True

            # ── Download GCSim in the main thread (thread-safe) ─────────────
            gcsim_path = _cached_gcsim()   # ✅ moved here
            st.session_state.status        = "running"
            st.session_state.status_msg    = "Running optimizer…"

            progress_q = queue.Queue()
            result_q   = queue.Queue()
            st.session_state.progress_q = progress_q
            st.session_state.result_q   = result_q

            fp = st.session_state.frozen_params

            # Capture as plain Python objects BEFORE thread starts.
            _df_snapshot = st.session_state.characters_df.copy()
            _stop_flag   = st.session_state.stop_flag

            def _worker():
                try:
                    # gcsim_path is now available from outer scope (closure)
                    progress_q.put(("status", "running", "Running optimizer…"))  # already running

                    if "Preset" in fp["mode"]:
                        from optimizer_pareto import run_optimizer
                    else:
                        from optimizer_rotation import run_optimizer

                    def _make_cb(label=""):
                        def _cb(*args):
                            progress_q.put(("progress", label) + args)
                        return _cb

                    def _run(extra_ban=None, label="", lock_override=None):
                        ban = list(fp["banned_gcsim"]) + (extra_ban or [])
                        lc  = lock_override if lock_override is not None else fp["locked_gcsim"]
                        return run_optimizer(
                            df=_df_snapshot,
                            lock_chars=lc,
                            ban_chars=ban,
                            gcsim_bin=gcsim_path,
                            sim_duration=fp["sim_duration"],
                            sim_iterations=fp["sim_iterations"],
                            population_size=fp["population_size"],
                            generations=fp["generations"],
                            mutation_rate=fp["mutation_rate"],
                            min_character_level=fp["min_char_level"],
                            traveler_default=fp["traveler_default"],
                            start_energy=fp["start_energy"],
                            enemy_level=fp["enemy_level"],
                            enemy_resist=fp["enemy_resist"],
                            pareto=fp["pareto_on"],
                            stop_flag=_stop_flag,
                            progress_callback=_make_cb(label),
                        )

                    if fp["abyss_mode"]:
                        progress_q.put(("status", "running", "Optimizing Team 1 (first half)…"))
                        result1 = _run(label="Team 1",
                                            lock_override=fp["locked_gcsim_t1"] or fp["locked_gcsim"])
                        best_cfg1, best_obj1, summary1, configs1, warnings1 = result1
                        team1_chars = summary1[0]["team"] if summary1 else []
                        progress_q.put(("status", "running",
                            f"Team 1 done ({', '.join(team1_chars)}). Optimizing Team 2…"))
                        # Team 2: ban team1 chars + user bans; use T2-specific locks
                        ban2 = list(fp["banned_gcsim"]) + team1_chars
                        from optimizer_pareto import run_optimizer as _run_pareto_t2
                        from optimizer_rotation import run_optimizer as _run_rot_t2
                        _run2_fn = _run_pareto_t2 if "Preset" in fp["mode"] else _run_rot_t2
                        result2 = _run2_fn(
                            df=_df_snapshot,
                            lock_chars=fp["locked_gcsim_t2"],
                            ban_chars=ban2,
                            gcsim_bin=gcsim_path,
                            sim_duration=fp["sim_duration"],
                            sim_iterations=fp["sim_iterations"],
                            population_size=fp["population_size"],
                            generations=fp["generations"],
                            mutation_rate=fp["mutation_rate"],
                            min_character_level=fp["min_char_level"],
                            traveler_default=fp["traveler_default"],
                            enemy_level=fp["enemy_level"],
                            enemy_resist=fp["enemy_resist"],
                            start_energy=fp["start_energy"],
                            pareto=fp["pareto_on"],
                            stop_flag=_stop_flag,
                            progress_callback=_make_cb("Team 2"),
                        )
                        best_cfg2, best_obj2, summary2, configs2, warnings2 = result2
                        result_q.put(("ok_abyss", (
                            best_cfg1, best_obj1, summary1, configs1,
                            best_cfg2, best_obj2, summary2, configs2,
                            warnings1 + warnings2,
                        )))
                    else:
                        result_q.put(("ok", _run()))
                except Exception:
                    result_q.put(("err", traceback.format_exc()))

            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            st.session_state.opt_thread = t

            # Force immediate rerun so the UI reflects the new state right away
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div style="text-align:center;padding:28px 0 8px">
  <div style="font-size:0.75rem;letter-spacing:0.25em;color:#7eb8d4;text-transform:uppercase;margin-bottom:6px">
    Evolutionary Algorithm · GCSim · Enka Network
  </div>
  <h1 style="color:#d4af37;margin:0;font-size:2rem;letter-spacing:0.05em;font-weight:800">
    ⚔️ Genshin Team Optimizer
  </h1>
  <p style="color:#9a96b0;margin:8px 0 0;font-size:0.9rem">
    Finds your strongest team from your roster.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Poll the background thread ────────────────────────────────────────────
# This runs every rerun so progress messages arrive quickly.

if st.session_state.opt_running:
    pq = st.session_state.progress_q
    rq = st.session_state.result_q

    # Drain every message currently in the queue
    while not pq.empty():
        msg = pq.get_nowait()
        if msg[0] == "status":
            _, level, text = msg
            st.session_state.status     = level
            st.session_state.status_msg = text
        elif msg[0] == "progress":
            _, _label, gen_num, gen_total, best_obj, top5, *rest = msg
            ind_info = rest[2] if len(rest) > 2 else {}
            ind_done  = ind_info.get("individuals_done", 0) if ind_info else 0
            ind_total = ind_info.get("individuals_total", 0) if ind_info else 0
            st.session_state.gen_done    = gen_num
            st.session_state.gen_total   = gen_total
            st.session_state.ind_done    = ind_done
            st.session_state.ind_total   = ind_total
            st.session_state.best_obj    = best_obj
            st.session_state.status      = "running"
            st.session_state.status_msg  = f"Generation {gen_num} / {gen_total}"

            # Format top-5 log entry
            t5_lines = []
            for ind, obj in top5:
                if isinstance(ind, tuple) and len(ind) > 4:
                    chars = list(ind[2:6])      # Pareto: (preset, start, c,c,c,c)
                else:
                    chars = list(ind[0]) if isinstance(ind, tuple) else []
                t5_lines.append(
                    f"  {'·'.join(str(c) for c in chars)}  "
                    f"DPS:{obj['dps']:.0f}  MaxHit:{obj['max_hit']:.0f}"
                )
            entry = (
                f"Gen {gen_num}/{gen_total}  "
                f"best DPS:{best_obj['dps']:.0f}  MaxHit:{best_obj['max_hit']:.0f}  SD:{best_obj['sd']:.0f}\n"
                + "\n".join(t5_lines)
            )
            st.session_state.progress_log.append(entry)

    # Check if the thread finished
    if not rq.empty():
        tag, payload = rq.get_nowait()
        st.session_state.opt_running = False
        st.session_state.opt_thread  = None
        if tag == "ok":
            best_config, best_obj, pareto_summary, pareto_configs, warnings = payload
            st.session_state.best_config     = best_config
            st.session_state.best_obj        = best_obj
            st.session_state.pareto_summary  = pareto_summary
            st.session_state.pareto_configs  = pareto_configs
            st.session_state.warnings        = warnings
            st.session_state.abyss_result    = None
            st.session_state.status          = "done"
            st.session_state.stop_flag       = [False]
            st.session_state["_needs_final_rerun"] = True
            st.session_state.status_msg      = (
                f"Done! Best DPS: {best_obj['dps']:,.0f}  "
                f"Max Hit: {best_obj['max_hit']:,.0f}"
            )
        elif tag == "ok_abyss":
            (best_cfg1, best_obj1, summary1, configs1,
             best_cfg2, best_obj2, summary2, configs2, warnings) = payload
            st.session_state.best_config    = best_cfg1
            st.session_state.best_obj       = best_obj1
            st.session_state.pareto_summary = summary1
            st.session_state.pareto_configs = configs1
            st.session_state.warnings       = warnings
            st.session_state.abyss_result   = {
                "team1": {"best_config": best_cfg1, "best_obj": best_obj1,
                          "summary": summary1, "configs": configs1},
                "team2": {"best_config": best_cfg2, "best_obj": best_obj2,
                          "summary": summary2, "configs": configs2},
            }
            t1 = summary1[0]["team"] if summary1 else []
            t2 = summary2[0]["team"] if summary2 else []
            combined_dps = (best_obj1["dps"] + best_obj2["dps"])
            st.session_state.status     = "done"
            st.session_state.stop_flag  = [False]
            st.session_state["_needs_final_rerun"] = True
            st.session_state.status_msg = (
                f"Abyss done! Team 1: {', '.join(t1)} | Team 2: {', '.join(t2)} | "
                f"Combined DPS: {combined_dps:,.0f}"
            )
        else:
            st.session_state.status     = "error"
            st.session_state.status_msg = "Optimizer crashed — see details below."
            st.session_state.warnings   = [payload]
            st.session_state.stop_flag  = [False]
            st.session_state["_needs_final_rerun"] = True


# ── Status bar (ALWAYS visible at top) ───────────────────────────────────

status = st.session_state.status
msg    = st.session_state.status_msg

if status == "idle" and st.session_state.characters_df is None:
    status_bar("idle", "Load your characters using the sidebar to get started.")
elif status == "idle" and st.session_state.characters_df is not None:
    status_bar("idle", "Characters loaded. Configure and press ▶ Start in the sidebar.")
elif status == "downloading":
    status_bar("downloading", msg or "Downloading GCSim binary (first run only)…")
elif status == "running":
    gen_done  = st.session_state.gen_done
    gen_total = st.session_state.gen_total
    ind_done  = st.session_state.get("ind_done", 0)
    ind_total = st.session_state.get("ind_total", 0)
    # Overall progress = fraction of all individuals across all generations
    total_inds = gen_total * max(ind_total, 1)
    done_inds  = (gen_done - 1) * max(ind_total, 1) + ind_done if gen_done > 0 else 0
    overall_pct = min(done_inds / total_inds, 1.0) if total_inds > 0 else gen_done / max(gen_total, 1)
    if ind_total > 0 and ind_done < ind_total:
        ind_label = f"  ·  evaluating {ind_done}/{ind_total} individuals"
    else:
        ind_label = ""
    status_bar("running", f"Running… Gen {gen_done}/{gen_total}{ind_label}")
    st.progress(overall_pct)
elif status == "done":
    status_bar("done", msg)
elif status == "error":
    status_bar("error", "An error occurred during optimization.")

# ── Progress detail (shown while running) ────────────────────────────────

if status == "running" and st.session_state.best_obj:
    obj = st.session_state.best_obj
    m1, m2, m3 = st.columns(3)
    m1.metric("Best DPS",     f"{obj['dps']:,.0f}")
    m2.metric("Best Max Hit", f"{obj['max_hit']:,.0f}")
    m3.metric("Consistency",  f"±{obj['sd']:,.0f} SD")

    log = st.session_state.progress_log[-15:]
    log_html = "<br>".join(
        line.replace(" ", "&nbsp;").replace("\n", "<br>") for line in log
    )
    st.markdown(f'<div class="gen-log">{log_html}</div>', unsafe_allow_html=True)

# ── Schedule next poll while running ─────────────────────────────────────
# Also rerun once immediately when the optimizer just finished so the sidebar
# buttons (Start/Stop) refresh without waiting for the next user interaction.

if st.session_state.opt_running:
    time.sleep(1.2)   # 1.2s is a good balance: responsive but not flickery
    st.rerun()
elif st.session_state.status in ("done", "error"):
    # One extra rerun after finishing to flush sidebar button states
    if st.session_state.get("_needs_final_rerun", False):
        st.session_state["_needs_final_rerun"] = False
        st.rerun()

# ── Abort early if no characters ─────────────────────────────────────────

if st.session_state.characters_df is None:
    with st.expander("ℹ️ How it works"):
        st.markdown("""
**Step 1 – Data** — Enter your UID, click **Fetch**. Only your displayed characters are read.
Enka Network needs no login; it only sees what you've set as your showcase.

**Step 2 – Merge batches** — Enka shows 8–12 characters at a time. Swap your showcase
in-game, click **＋ Merge** to accumulate more characters, and repeat.

**Step 3 – Configure & Run** — Choose a preset, lock any must-have characters, hit **▶ Start**.
The optimizer tries thousands of team combinations evaluated by GCSim.

**Step 4 – Results** — A Pareto front of teams is returned, each best at different trade-offs
(raw DPS vs. burst nuke vs. consistency). Download any config for use in GCSim directly.
        """)
    st.stop()

# ── Error display ─────────────────────────────────────────────────────────

if status == "error" and st.session_state.warnings:
    with st.expander("🔴 Error details", expanded=True):
        for w in st.session_state.warnings:
            st.code(w, language="text")

# ── Character grid ────────────────────────────────────────────────────────

info = st.session_state.player_info
df   = st.session_state.characters_df

st.markdown("---")
player_display = info["nickname"] if info else "Your Characters"
st.markdown(f"### {player_display}'s Roster")
if info:
    st.caption(f"AR {info['level']} · UID {info['uid']}  |  {len(df)} character(s) loaded")

# ✅ FIX: only create columns if df is not empty
if not df.empty:
    # Fixed 4-column grid looks neat and consistent
    cols = st.columns(4)
    for i, (_, row) in enumerate(df.iterrows()):
        with cols[i % 4]:
            char_card(row)
else:
    st.info("No character data to display. Use the sidebar to fetch or upload a CSV.")

# ── Results ───────────────────────────────────────────────────────────────

if st.session_state.pareto_summary:
    st.markdown("---")
    st.markdown("### 🏆 Results")

    if st.session_state.warnings:
        with st.expander(f"⚠️ {len(st.session_state.warnings)} warning(s)"):
            for w in st.session_state.warnings:
                st.caption(w)

    if st.session_state.abyss_result:
        tab_abyss, tab_pareto, tab_best, tab_all = st.tabs(
            ["🏆 Abyss Teams", "Pareto Front (T1)", "Best DPS (T1)", "All Configs"]
        )
        with tab_abyss:
            ar = st.session_state.abyss_result
            for half, key in [("Team 1 — First Half", "team1"), ("Team 2 — Second Half", "team2")]:
                half_data = ar[key]
                obj = half_data["best_obj"]
                summ = half_data["summary"]
                cfgs = half_data["configs"]
                st.markdown(f"#### {half}")
                if obj:
                    h1, h2, h3 = st.columns(3)
                    h1.metric("DPS", f"{obj['dps']:,.0f}")
                    h2.metric("Max Hit", f"{obj['max_hit']:,.0f}")
                    h3.metric("SD", f"{obj['sd']:,.0f}")
                for i, (entry, cfg) in enumerate(zip(summ[:3], cfgs[:3])):
                    team_str = " · ".join(entry.get("team", []))
                    preset   = entry.get("preset", "—")
                    dps      = entry.get("dps", 0)
                    mh       = entry.get("max_hit", 0)
                    st.markdown(f"""
                    <div class="result-card">
                      <b style="color:#d4af37">#{i+1}</b>
                      &nbsp;<span style="color:#7eb8d4">{team_str}</span><br>
                      <small style="color:#aaa">Rotation: {preset} &nbsp;·&nbsp;
                      DPS <b style="color:#d4af37">{dps:,.0f}</b> &nbsp;·&nbsp;
                      Max Hit <b style="color:#7eb8d4">{mh:,.0f}</b></small>
                    </div>""", unsafe_allow_html=True)
                    with st.expander(f"{key} config #{i+1}"):
                        st.code(cfg, language="text")
                        st.download_button(
                            f"⬇ Download {key} config #{i+1}",
                            data=cfg,
                            file_name=f"{key}_team_{i+1}.txt",
                            mime="text/plain",
                            key=f"dl_abyss_{key}_{i}",
                        )
                if half_data["best_config"]:
                    st.download_button(
                        f"⬇ Download best {half} config",
                        data=half_data["best_config"],
                        file_name=f"best_{key}.txt",
                        mime="text/plain",
                        key=f"dl_abyss_best_{key}",
                    )
    else:
        tab_pareto, tab_best, tab_all = st.tabs(["Pareto Front", "Best DPS Team", "All Configs"])

    with tab_pareto:
        summary = st.session_state.pareto_summary
        configs = st.session_state.pareto_configs or []
        for i, (entry, cfg) in enumerate(zip(summary, configs)):
            team_str = " · ".join(entry.get("team", []))
            preset   = entry.get("preset", "—")
            dps      = entry.get("dps", 0)
            mh       = entry.get("max_hit", 0)
            sd       = entry.get("sd", 0)
            st.markdown(f"""
            <div class="result-card">
              <b style="color:#d4af37">#{i+1}</b>
              &nbsp;&nbsp;<span style="color:#7eb8d4">{team_str}</span><br>
              <small style="color:#aaa">
                Rotation: {preset} &nbsp;·&nbsp;
                DPS <b style="color:#d4af37">{dps:,.0f}</b> &nbsp;·&nbsp;
                Max Hit <b style="color:#7eb8d4">{mh:,.0f}</b> &nbsp;·&nbsp;
                SD {sd:,.0f}
              </small>
            </div>""", unsafe_allow_html=True)
            with st.expander(f"GCSim config #{i+1}"):
                st.code(cfg, language="text")
                st.download_button(
                    f"⬇ Download config #{i+1}",
                    data=cfg,
                    file_name=f"team_{i+1}.txt",
                    mime="text/plain",
                    key=f"dl_{i}",
                )
        st.download_button(
            "⬇ Download all results (JSON)",
            data=json.dumps(summary, indent=2),
            file_name="pareto_summary.json",
            mime="application/json",
        )

    with tab_best:
        if st.session_state.best_config:
            obj = st.session_state.best_obj
            if obj:
                b1, b2, b3 = st.columns(3)
                b1.metric("DPS",     f"{obj['dps']:,.0f}")
                b2.metric("Max Hit", f"{obj['max_hit']:,.0f}")
                b3.metric("SD",      f"{obj['sd']:,.0f}")
            st.code(st.session_state.best_config, language="text")
            st.download_button(
                "⬇ Download best team config",
                data=st.session_state.best_config,
                file_name="best_team.txt",
                mime="text/plain",
            )

    with tab_all:
        all_txt = ("\n\n" + "="*60 + "\n\n").join(
            f"# Team {i+1}: {' · '.join(e.get('team',[]))}\n{c}"
            for i, (e, c) in enumerate(zip(summary, configs))
        )
        st.download_button(
            "⬇ Download all configs (.txt)",
            data=all_txt,
            file_name="all_teams.txt",
            mime="text/plain",
        )