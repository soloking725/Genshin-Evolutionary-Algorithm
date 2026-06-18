"""
app.py  –  Genshin Team Optimizer
Streamlit front-end for the Enka Network + GCSim evolutionary optimizer.
"""
import io
import json
import queue
import threading
import time

import pandas as pd
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Genshin Team Optimizer",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Dark Genshin-ish palette */
:root {
    --accent: #d4af37;
    --accent2: #7eb8d4;
    --bg-card: rgba(255,255,255,0.05);
    --border: rgba(212,175,55,0.3);
}
.stApp { background: linear-gradient(135deg, #0f0c1a 0%, #1a1535 50%, #0c1a2e 100%); }
[data-testid="stSidebar"] { background: rgba(15,12,26,0.95); border-right: 1px solid var(--border); }

.char-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    text-align: center;
}
.char-card .name { color: var(--accent); font-weight: 700; font-size: 1rem; }
.char-card .stats { color: #ccc; font-size: 0.78rem; line-height: 1.6; }

.result-card {
    background: var(--bg-card);
    border: 1px solid var(--accent2);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}
.result-card .rank { color: var(--accent); font-size: 1.4rem; font-weight: 700; }
.result-card .team { color: var(--accent2); font-size: 1.1rem; margin: 4px 0; }
.result-card .metrics { color: #ccc; font-size: 0.85rem; }

.banner {
    background: linear-gradient(90deg, rgba(212,175,55,0.15), rgba(126,184,212,0.15));
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px 32px;
    text-align: center;
    margin-bottom: 24px;
}
.banner h1 { color: var(--accent); font-size: 2.2rem; margin: 0; }
.banner p  { color: #aaa; margin: 8px 0 0 0; }

.gen-log {
    background: #0a0a0a;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 10px;
    font-family: monospace;
    font-size: 0.8rem;
    color: #00ff88;
    max-height: 280px;
    overflow-y: auto;
}
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────

for key, default in {
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
    "gcsim_ready": False,
    "gcsim_status": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── GCSim init (download once per session) ────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_gcsim_path():
    from gcsim_manager import ensure_gcsim
    return ensure_gcsim()


# ── Helper: character display card ────────────────────────────────────────

ELEMENT_COLOR = {
    "Pyro": "#ff6b35", "Hydro": "#4fc3f7", "Anemo": "#80deea",
    "Cryo": "#b3e5fc", "Electro": "#ce93d8", "Geo": "#ffcc02",
    "Dendro": "#a5d6a7", "Physical": "#cccccc",
}


def char_card(row: pd.Series):
    name = row["Character Name"]
    level = int(row.get("Character Level", 0))
    cons = int(row.get("Character Constellations", 0))
    weapon = row.get("Weapon Name", "—")
    friendship = int(row.get("Character Friendship", 0))
    set_bonus = row.get("Artifact Set Bonus", "—")

    st.markdown(f"""
    <div class="char-card">
      <div class="name">{name}</div>
      <div class="stats">
        Lv {level} · C{cons} · F{friendship}<br>
        🗡 {weapon}<br>
        <span style="color:#d4af37">{set_bonus}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚔️ Team Optimizer")
    st.markdown("---")

    # ── Step 1: Fetch characters ──────────────────────────────────────────
    st.markdown("**1 · Load Your Characters**")
    uid_input = st.text_input("Genshin UID", placeholder="e.g. 618867267")

    csv_file = st.file_uploader(
        "…or upload a genshin_data_export.csv",
        type=["csv"],
        help="Use this if your showcase is hidden or if you already have a CSV.",
    )

    col_fetch, col_clear = st.columns(2)
    with col_fetch:
        fetch_clicked = st.button("Fetch", use_container_width=True, disabled=st.session_state.opt_running)
    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state.characters_df = None
            st.session_state.player_info = None
            st.session_state.best_config = None
            st.session_state.pareto_summary = None
            st.rerun()

    if fetch_clicked and uid_input.strip():
        with st.spinner("Fetching from Enka Network…"):
            try:
                from enka_fetcher import fetch_characters
                df, info = fetch_characters(int(uid_input.strip()))
                st.session_state.characters_df = df
                st.session_state.player_info = info
                st.success(f"Loaded {len(df)} character(s) for {info['nickname']}")
            except Exception as e:
                st.error(f"Fetch failed: {e}")

    if csv_file is not None and st.session_state.characters_df is None:
        try:
            df = pd.read_csv(csv_file)
            st.session_state.characters_df = df
            st.session_state.player_info = {
                "nickname": str(df["Player Nickname"].iloc[0]) if "Player Nickname" in df else "CSV",
                "level": int(df["Player Level"].iloc[0]) if "Player Level" in df else 0,
                "signature": "",
                "uid": str(df["UID"].iloc[0]) if "UID" in df else "—",
            }
            st.success(f"Loaded {len(df)} rows from CSV.")
        except Exception as e:
            st.error(f"CSV parse failed: {e}")

    st.markdown("---")

    # ── Step 2: Configure optimizer ───────────────────────────────────────
    if st.session_state.characters_df is not None:
        df = st.session_state.characters_df
        st.markdown("**2 · Configure Optimizer**")

        mode = st.radio(
            "Optimizer mode",
            ["Preset Rotations (faster)", "Evolve Rotations (powerful)"],
            help=(
                "**Preset Rotations** picks the best *team* from a bank of proven "
                "rotation templates.\n\n"
                "**Evolve Rotations** also evolves the action sequence itself — slower "
                "but can discover non-obvious combos."
            ),
        )

        char_names = sorted(df["Character Name"].unique())
        lock_chars = st.multiselect(
            "Lock characters (always on team)",
            options=char_names,
            max_selections=4,
            help="These characters will always appear in the optimized team.",
        )

        with st.expander("⚙️ Advanced settings", expanded=False):
            preset_name = st.selectbox(
                "Quick preset",
                ["Quick Test", "Standard", "Thorough", "Custom"],
                index=1,
            )

            PRESETS = {
                "Quick Test": dict(sim_duration=15, sim_iterations=5, population_size=20, generations=5),
                "Standard":   dict(sim_duration=30, sim_iterations=20, population_size=50, generations=20),
                "Thorough":   dict(sim_duration=90, sim_iterations=50, population_size=80, generations=40),
            }

            if preset_name != "Custom":
                p = PRESETS[preset_name]
            else:
                p = {}

            sim_duration   = st.slider("Sim duration (s)",    5,  180, p.get("sim_duration",   30))
            sim_iterations = st.slider("Sim iterations",       1,  500, p.get("sim_iterations", 20))
            population_size= st.slider("Population size",     10,  200, p.get("population_size",50))
            generations    = st.slider("Generations",          5,  100, p.get("generations",    20))
            mutation_rate  = st.slider("Mutation rate",      0.05, 0.6, 0.15, step=0.05)
            min_char_level = st.slider("Min character level", 1,   90,  50)
            pareto_on      = st.checkbox("Pareto multi-objective", value=True,
                                         help="Optimise for DPS + max hit + consistency simultaneously.")
            traveler_default = st.selectbox(
                "Traveler element (if auto-detect fails)",
                ["anemo", "geo", "electro", "dendro", "hydro", "pyro", "cryo"],
            )

        st.markdown("---")
        st.markdown("**3 · Run**")

        run_col, stop_col = st.columns(2)
        with run_col:
            run_clicked = st.button(
                "▶ Start",
                use_container_width=True,
                disabled=st.session_state.opt_running,
                type="primary",
            )
        with stop_col:
            stop_clicked = st.button(
                "⏹ Stop",
                use_container_width=True,
                disabled=not st.session_state.opt_running,
            )

        if stop_clicked:
            st.session_state.stop_flag[0] = True

        if run_clicked and not st.session_state.opt_running:
            # Determine GCSim path
            try:
                gcsim_path = get_gcsim_path()
            except Exception as e:
                st.error(f"GCSim download failed: {e}")
                st.stop()

            # Resolve locked char gcsim names
            from config_builder import build_character_configs, to_gcsim_name
            import re
            locked_gcsim = []
            for lc in lock_chars:
                row = df[df["Character Name"] == lc].iloc[0]
                gname = to_gcsim_name(lc, row, [], {}, traveler_default)
                if gname:
                    locked_gcsim.append(gname)

            # Reset state
            st.session_state.stop_flag = [False]
            st.session_state.progress_log = []
            st.session_state.best_obj = None
            st.session_state.pareto_summary = None
            st.session_state.pareto_configs = None
            st.session_state.best_config = None

            progress_q = queue.Queue()
            result_q   = queue.Queue()

            def _progress_cb(*args):
                progress_q.put(args)

            def _worker():
                try:
                    if "Preset" in mode:
                        from optimizer_pareto import run_optimizer
                    else:
                        from optimizer_rotation import run_optimizer

                    result = run_optimizer(
                        df=st.session_state.characters_df,
                        lock_chars=locked_gcsim,
                        gcsim_bin=gcsim_path,
                        sim_duration=sim_duration,
                        sim_iterations=sim_iterations,
                        population_size=population_size,
                        generations=generations,
                        mutation_rate=mutation_rate,
                        min_character_level=min_char_level,
                        traveler_default=traveler_default,
                        pareto=pareto_on,
                        stop_flag=st.session_state.stop_flag,
                        progress_callback=_progress_cb,
                    )
                    result_q.put(("ok", result))
                except Exception as e:
                    result_q.put(("err", str(e)))

            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            st.session_state.opt_running  = True
            st.session_state.opt_thread   = t
            st.session_state.progress_q   = progress_q
            st.session_state.result_q     = result_q


# ── Main area ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="banner">
  <h1>⚔️ Genshin Team Optimizer</h1>
  <p>Fetches your showcase from Enka Network and uses an evolutionary algorithm + GCSim to find your strongest team.</p>
</div>
""", unsafe_allow_html=True)

if st.session_state.characters_df is None:
    st.info("👈 Enter your UID in the sidebar and click **Fetch** to get started. "
            "You can also upload an exported CSV.")

    with st.expander("ℹ️ How it works"):
        st.markdown("""
**Step 1 – Data**  
Your UID is used to read your public showcase from [Enka Network](https://enka.network).
No login or password is required — Enka Network only reads the characters
you have chosen to display on your profile. Your UID is treated as a read-only
identifier; nothing is stored beyond your current browser session.

**Step 2 – Config building**  
Each character's stats, weapon, and artifacts are translated into a
[GCSim](https://gcsim.app) simulation config.

**Step 3 – Evolutionary algorithm**  
An evolutionary algorithm explores thousands of team combinations, evaluating
each one with GCSim.  
*Preset Rotations* mode tests fixed proven rotations.  
*Evolve Rotations* mode evolves both the team and the action sequence simultaneously.

**Step 4 – Pareto front**  
In Pareto mode the optimizer tracks teams that are not dominated on any of three
objectives: average DPS, maximum single hit, and consistency (low standard deviation).
        """)
    st.stop()

# ── Character grid ────────────────────────────────────────────────────────

info = st.session_state.player_info
df   = st.session_state.characters_df

player_display = info["nickname"] if info else "Your Characters"
st.markdown(f"### {player_display}'s Showcase")
if info:
    st.caption(f"AR {info['level']} · UID {info['uid']}  |  {len(df)} character(s) loaded")

cols = st.columns(min(len(df), 4))
for i, (_, row) in enumerate(df.iterrows()):
    with cols[i % 4]:
        char_card(row)

# ── Optimizer progress ────────────────────────────────────────────────────

if st.session_state.opt_running:
    st.markdown("---")
    st.markdown("### 🧬 Optimizer Running…")

    pq = st.session_state.progress_q
    rq = st.session_state.result_q

    # Drain progress queue
    while not pq.empty():
        update = pq.get()
        gen_num = update[0]
        total_gens = update[1]
        best_obj = update[2]
        top5 = update[3]

        # Format top 5
        if top5:
            t5_lines = []
            for ind, obj in top5:
                if isinstance(ind, tuple) and len(ind) > 2:
                    # Pareto mode: (preset_id, start_idx, char1, char2, char3, char4)
                    chars = list(ind[2:])
                else:
                    # Rotation mode: ((team_tuple), rotation_tokens)
                    chars = list(ind[0]) if isinstance(ind, tuple) else []
                t5_lines.append(
                    f"  {'·'.join(chars[:4])}  DPS:{obj['dps']:.0f}  MaxHit:{obj['max_hit']:.0f}"
                )
            log_entry = (
                f"Gen {gen_num}/{total_gens}  best DPS:{best_obj['dps']:.0f} "
                f"MaxHit:{best_obj['max_hit']:.0f} SD:{best_obj['sd']:.0f}\n"
                + "\n".join(t5_lines)
            )
        else:
            log_entry = f"Gen {gen_num}/{total_gens}  DPS:{best_obj['dps']:.0f}"

        st.session_state.progress_log.append(log_entry)
        st.session_state.best_obj = best_obj

    # Show progress
    progress_bar = st.progress(0)
    if st.session_state.progress_log:
        last_line = st.session_state.progress_log[-1]
        gen_done = int(last_line.split("/")[0].split()[-1]) if "/" in last_line else 0
        total_gens = int(last_line.split("/")[1].split()[0]) if "/" in last_line else 1
        progress_bar.progress(min(gen_done / total_gens, 1.0))
        st.caption(f"Generation {gen_done}/{total_gens}")

    if st.session_state.best_obj:
        obj = st.session_state.best_obj
        m1, m2, m3 = st.columns(3)
        m1.metric("Best DPS",     f"{obj['dps']:.0f}")
        m2.metric("Best Max Hit", f"{obj['max_hit']:.0f}")
        m3.metric("Consistency",  f"SD {obj['sd']:.0f}")

    # Scrollable log
    log_text = "\n\n".join(st.session_state.progress_log[-20:])
    st.markdown(f'<div class="gen-log">{log_text.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

    # Check for completion
    if not st.session_state.result_q.empty():
        status, payload = st.session_state.result_q.get()
        st.session_state.opt_running = False
        st.session_state.opt_thread  = None
        if status == "ok":
            best_config, best_obj, pareto_summary, pareto_configs, warnings = payload
            st.session_state.best_config     = best_config
            st.session_state.best_obj        = best_obj
            st.session_state.pareto_summary  = pareto_summary
            st.session_state.pareto_configs  = pareto_configs
            st.session_state.warnings        = warnings
        else:
            st.error(f"Optimizer error: {payload}")
        st.rerun()
    else:
        time.sleep(1.0)
        st.rerun()

# ── Results ───────────────────────────────────────────────────────────────

if st.session_state.pareto_summary:
    st.markdown("---")
    st.markdown("### 🏆 Results")

    if st.session_state.warnings:
        with st.expander(f"⚠️ {len(st.session_state.warnings)} warning(s)"):
            for w in st.session_state.warnings:
                st.caption(w)

    tab_pareto, tab_best, tab_raw = st.tabs(["Pareto Front", "Best DPS Team", "Raw Configs"])

    with tab_pareto:
        summary = st.session_state.pareto_summary
        configs = st.session_state.pareto_configs or []

        for i, (entry, cfg) in enumerate(zip(summary, configs)):
            team_str = " · ".join(entry.get("team", []))
            preset   = entry.get("preset", "—")
            dps      = entry.get("dps", 0)
            max_hit  = entry.get("max_hit", 0)
            sd       = entry.get("sd", 0)

            with st.container():
                st.markdown(f"""
                <div class="result-card">
                  <span class="rank">#{i+1}</span>
                  <div class="team">{team_str}</div>
                  <div class="metrics">
                    Rotation: {preset} &nbsp;·&nbsp;
                    DPS: <b style="color:#d4af37">{dps:,.0f}</b> &nbsp;·&nbsp;
                    Max Hit: <b style="color:#7eb8d4">{max_hit:,.0f}</b> &nbsp;·&nbsp;
                    SD: {sd:,.0f}
                  </div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander(f"GCSim config #{i+1}"):
                    st.code(cfg, language="text")
                    st.download_button(
                        f"⬇ Download config #{i+1}",
                        data=cfg,
                        file_name=f"team_{i+1}_{'_'.join(entry.get('team', []))}.txt",
                        mime="text/plain",
                        key=f"dl_pareto_{i}",
                    )

        # Download all as JSON
        json_summary = json.dumps(summary, indent=2)
        st.download_button(
            "⬇ Download all results (JSON)",
            data=json_summary,
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

    with tab_raw:
        st.caption("All Pareto front configs in one download.")
        all_txt = "\n\n" + "=" * 60 + "\n\n".join(
            f"# Team {i+1}: {' · '.join(e.get('team', []))}\n{c}"
            for i, (e, c) in enumerate(zip(summary, configs))
        )
        st.download_button(
            "⬇ Download all configs (.txt)",
            data=all_txt,
            file_name="all_teams.txt",
            mime="text/plain",
        )

elif (
    not st.session_state.opt_running
    and st.session_state.characters_df is not None
    and st.session_state.best_config is None
):
    st.info("Configure the optimizer in the sidebar and click **▶ Start**.")
