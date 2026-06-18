"""
app.py  –  Genshin Team Optimizer
"""
import io
import json
import queue
import threading
import time
import traceback

import pandas as pd
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Genshin Team Optimizer",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
:root { --accent:#d4af37; --accent2:#7eb8d4; --border:rgba(212,175,55,0.3); }
.stApp { background: linear-gradient(135deg,#0f0c1a 0%,#1a1535 50%,#0c1a2e 100%); }
[data-testid="stSidebar"] {
    background: rgba(15,12,26,0.95);
    border-right: 1px solid var(--border);
}
.char-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    text-align: center;
}
.char-card .name { color: var(--accent); font-weight:700; font-size:1rem; }
.char-card .stats { color:#ccc; font-size:0.78rem; line-height:1.6; }
.status-bar {
    border-radius: 8px;
    padding: 14px 20px;
    margin-bottom: 18px;
    font-size: 1rem;
    font-weight: 600;
}
.status-idle    { background:rgba(80,80,80,0.3);  border:1px solid #555; color:#aaa; }
.status-running { background:rgba(212,175,55,0.15); border:1px solid var(--accent); color:var(--accent); }
.status-done    { background:rgba(0,200,100,0.12); border:1px solid #0c6; color:#0c6; }
.status-error   { background:rgba(200,50,50,0.15); border:1px solid #c33; color:#f88; }
.result-card {
    background:rgba(255,255,255,0.05);
    border:1px solid var(--accent2);
    border-radius:8px;
    padding:16px;
    margin-bottom:12px;
}
.gen-log {
    background:#0a0a0a;
    border:1px solid #333;
    border-radius:6px;
    padding:10px;
    font-family:monospace;
    font-size:0.78rem;
    color:#00ff88;
    max-height:220px;
    overflow-y:auto;
}
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
    "status": "idle",          # idle | downloading | running | done | error
    "status_msg": "",
    "gen_done": 0,
    "gen_total": 1,
    # Freeze optimizer params when Start is clicked so reruns don't change them
    "frozen_params": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── GCSim (download once per session) ────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _cached_gcsim():
    from gcsim_manager import ensure_gcsim
    return ensure_gcsim()


# ── Helpers ───────────────────────────────────────────────────────────────

def char_card(row):
    name = row["Character Name"]
    level = int(row.get("Character Level", 0) or 0)
    cons  = int(row.get("Character Constellations", 0) or 0)
    weapon = row.get("Weapon Name", "—") or "—"
    fr    = int(row.get("Character Friendship", 0) or 0)
    bonus = row.get("Artifact Set Bonus", "—") or "—"
    st.markdown(f"""
    <div class="char-card">
      <div class="name">{name}</div>
      <div class="stats">
        Lv {level} · C{cons} · F{fr}<br>
        🗡 {weapon}<br>
        <span style="color:#d4af37">{bonus}</span>
      </div>
    </div>""", unsafe_allow_html=True)


def _merge_df(existing, new_df):
    combined = pd.concat([existing, new_df], ignore_index=True)
    return combined.drop_duplicates(
        subset=["UID", "Character Name"], keep="last"
    ).reset_index(drop=True)


def status_bar(level, msg):
    cls = {"idle":"status-idle","downloading":"status-running",
           "running":"status-running","done":"status-done","error":"status-error"}[level]
    icon = {"idle":"💤","downloading":"⬇️","running":"🧬","done":"✅","error":"❌"}[level]
    st.markdown(
        f'<div class="status-bar {cls}">{icon} {msg}</div>',
        unsafe_allow_html=True,
    )


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
                st.error(f"Fetch failed: {e}")

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

    st.markdown("---")

    # ── 2. Configure ──────────────────────────────────────────────────────
    if st.session_state.characters_df is not None:
        st.markdown("**2 · Configure**")

        mode = st.radio(
            "Optimizer mode",
            ["Preset Rotations (faster)", "Evolve Rotations (powerful)"],
            disabled=st.session_state.opt_running,
        )

        char_names = sorted(st.session_state.characters_df["Character Name"].unique())
        lock_chars = st.multiselect(
            "Lock characters (always on team)",
            options=char_names,
            max_selections=4,
            disabled=st.session_state.opt_running,
        )

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

        st.markdown("---")
        st.markdown("**3 · Run**")

        run_col, stop_col = st.columns(2)
        run_clicked  = run_col.button("▶ Start", use_container_width=True,
                                       disabled=st.session_state.opt_running, type="primary")
        stop_clicked = stop_col.button("⏹ Stop", use_container_width=True,
                                        disabled=not st.session_state.opt_running)

        if stop_clicked and st.session_state.opt_running:
            st.session_state.stop_flag[0] = True
            st.session_state.status = "idle"
            st.session_state.status_msg = "Stopping… (finishing current generation)"

        if run_clicked and not st.session_state.opt_running:
            # ── Resolve locked char names ──────────────────────────────────
            from config_builder import to_gcsim_name
            df_now = st.session_state.characters_df
            locked_gcsim = []
            for lc in lock_chars:
                rows = df_now[df_now["Character Name"] == lc]
                if not rows.empty:
                    gname = to_gcsim_name(lc, rows.iloc[0], [], {}, traveler_default)
                    if gname:
                        locked_gcsim.append(gname)

            # ── Freeze all params so reruns don't change them ──────────────
            st.session_state.frozen_params = dict(
                mode=mode,
                locked_gcsim=locked_gcsim,
                sim_duration=sim_duration,
                sim_iterations=sim_iterations,
                population_size=population_size,
                generations=generations,
                mutation_rate=mutation_rate,
                min_char_level=min_char_level,
                pareto_on=pareto_on,
                traveler_default=traveler_default,
            )

            # ── Reset progress state ───────────────────────────────────────
            st.session_state.stop_flag     = [False]
            st.session_state.progress_log  = []
            st.session_state.best_obj      = None
            st.session_state.pareto_summary= None
            st.session_state.pareto_configs= None
            st.session_state.best_config   = None
            st.session_state.warnings      = []
            st.session_state.gen_done      = 0
            st.session_state.gen_total     = generations
            st.session_state.status        = "downloading"
            st.session_state.status_msg    = "Downloading GCSim binary (first run only)…"
            st.session_state.opt_running   = True

            progress_q = queue.Queue()
            result_q   = queue.Queue()
            st.session_state.progress_q = progress_q
            st.session_state.result_q   = result_q

            fp = st.session_state.frozen_params

            def _worker():
                try:
                    # Download GCSim (cached after first run)
                    gcsim_path = _cached_gcsim()
                    progress_q.put(("status", "running", "Running optimizer…"))

                    def _cb(*args):
                        progress_q.put(("progress",) + args)

                    if "Preset" in fp["mode"]:
                        from optimizer_pareto import run_optimizer
                    else:
                        from optimizer_rotation import run_optimizer

                    result = run_optimizer(
                        df=st.session_state.characters_df,
                        lock_chars=fp["locked_gcsim"],
                        gcsim_bin=gcsim_path,
                        sim_duration=fp["sim_duration"],
                        sim_iterations=fp["sim_iterations"],
                        population_size=fp["population_size"],
                        generations=fp["generations"],
                        mutation_rate=fp["mutation_rate"],
                        min_character_level=fp["min_char_level"],
                        traveler_default=fp["traveler_default"],
                        pareto=fp["pareto_on"],
                        stop_flag=st.session_state.stop_flag,
                        progress_callback=_cb,
                    )
                    result_q.put(("ok", result))
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
<div style="text-align:center;padding:20px 0 12px">
  <h1 style="color:#d4af37;margin:0">⚔️ Genshin Team Optimizer</h1>
  <p style="color:#aaa;margin:6px 0 0">Evolutionary algorithm + GCSim finds your strongest team.</p>
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
            _, gen_num, gen_total, best_obj, top5, *_ = msg
            st.session_state.gen_done  = gen_num
            st.session_state.gen_total = gen_total
            st.session_state.best_obj  = best_obj
            st.session_state.status     = "running"
            st.session_state.status_msg = f"Generation {gen_num} / {gen_total}"

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
            st.session_state.status          = "done"
            st.session_state.status_msg      = (
                f"Done! Best DPS: {best_obj['dps']:,.0f}  "
                f"Max Hit: {best_obj['max_hit']:,.0f}"
            )
        else:
            st.session_state.status     = "error"
            st.session_state.status_msg = "Optimizer error — see details below."
            st.session_state.warnings   = [payload]


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
    pct = int(100 * gen_done / max(gen_total, 1))
    status_bar("running", f"🧬 Running… Generation {gen_done} / {gen_total}  ({pct}%)")
    st.progress(gen_done / max(gen_total, 1))
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

if st.session_state.opt_running:
    time.sleep(0.8)
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

cols = st.columns(min(len(df), 4))
for i, (_, row) in enumerate(df.iterrows()):
    with cols[i % 4]:
        char_card(row)

# ── Results ───────────────────────────────────────────────────────────────

if st.session_state.pareto_summary:
    st.markdown("---")
    st.markdown("### 🏆 Results")

    if st.session_state.warnings:
        with st.expander(f"⚠️ {len(st.session_state.warnings)} warning(s)"):
            for w in st.session_state.warnings:
                st.caption(w)

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
