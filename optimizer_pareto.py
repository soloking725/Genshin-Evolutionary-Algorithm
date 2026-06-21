"""
optimizer_pareto.py
Evolutionary algorithm that optimises TEAM COMPOSITION.
Rotation is chosen from a bank of hand-crafted presets.
Objectives: maximise DPS + max single hit, minimise SD (Pareto-mode).
"""
import random
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from config_builder import build_character_configs
from gcsim_manager import run_gcsim, GCSIM_PATH

# ── Rotation presets ──────────────────────────────────────────────────────

# ── Rotation presets ──────────────────────────────────────────────────────

FILLER_ACTION = {'ganyu': 'aim', 'neuvillette': 'charge'}

def _filler(active):
    return FILLER_ACTION.get(active, 'attack')

# ---------- Existing generic presets (already safe) ----------

def _preset_standard(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body

def _preset_support_first(team, active=None):
    main_dps, others = team[-1], team[:-1]; active = active or team[0]
    body = ""
    for n in others:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  if .{main_dps}.burst.ready {{ {main_dps} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body

def _preset_quickswap(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body

def _preset_raiden_hyper(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  if .{active}.name == "raiden" {{ {active} attack:15; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body

def _preset_ganyu_aimed(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  if .{active}.name == "ganyu" {{ {active} aim; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body

def _preset_wriothesley(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  if .{active}.name == "wriothesley" {{ {active} charge; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body

def _preset_heavy_filler(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)},{_filler(active)},{_filler(active)};\n'
    return active, body

def _preset_burst_skill_weave(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body

def _preset_national(team, active=None):
    main_dps, others = team[-1], team[:-1]; active = active or team[0]
    body = ""
    for n in others:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  if .{main_dps}.burst.ready {{ {main_dps} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body

def _preset_hyperbloom(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)}:6;\n'
    return active, body

def _preset_battery_first(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body

def _preset_melt_ganyu(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  if .{active}.name == "ganyu" {{ {active} aim; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body

def _preset_tanky(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)},{_filler(active)};\n'
    return active, body

def _preset_kinich(team, active=None):
    active = active or team[0]; body = ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  if .{active}.name == "kinich" {{ {active} attack:4; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body

# ---------- Helper fallback for specialised presets ----------

def _generic_dps_fallback(team, active_char):
    body = "  for let i=0; i<4; i=i+1 {\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} attack:6;\n'
    body += f'    if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += "  }\n"
    return body

# ---------- New generic presets (character‑agnostic) ----------

def _preset_generic_support_burst(team, active_char):
    body = ""
    for n in team:
        if n != active_char:
            body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
            body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'  if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += f'  {active_char} attack;\n'
    return body

def _preset_generic_charge_dps(team, active_char):
    body = f"  for let i=0; i<4; i=i+1 {{\n"
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} attack;\n'
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += f'    delay(17);\n'
    body += f'    {active_char} charge:8;\n'
    body += f'    {active_char} charge; {active_char} charge[final=1]; {active_char} dash;\n'
    body += f'    {active_char} charge:2;\n'
    body += f'    delay(18);\n'
    body += f'  }}\n'
    return body

def _preset_generic_bond_dps(team, active_char):
    body = f"  for let i=0; i<4; i=i+1 {{\n"
    body += f'    {active_char} skill; delay(11);\n'
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    {active_char} charge;\n'
    body += f'    {active_char} attack:6;\n'
    body += f'    {active_char} attack:6;\n'
    body += f'    {active_char} attack:3;\n'
    body += f'  }}\n'
    return body

def _preset_generic_aim_dps(team, active_char):
    body = f"  for let r=0; r<4; r=r+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += f'    {active_char} aim:4;\n'
    body += f'    {active_char} aim[bullets=4];\n'
    body += f'  }}\n'
    body += f'  wait(82);\n'
    return body

def _preset_generic_hypercarry(team, active_char):
    body = f"  {active_char} skill;\n"
    body += f"  for let i=0; i<6; i=i+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += f'    {active_char} attack:4; {active_char} dash;\n'
    body += f'    {active_char} attack:4; {active_char} dash;\n'
    body += f'    {active_char} attack:4; {active_char} dash;\n'
    body += f'    {active_char} attack:4; {active_char} dash;\n'
    body += f'    {active_char} attack:1;\n'
    body += f'    {active_char} skill;\n'
    body += f'  }}\n'
    return body

def _preset_generic_spread_dps(team, active_char):
    body = f"  for let i=0; i<4; i=i+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} attack; {active_char} burst;\n'
    body += f'    {active_char} swap; wait(14);\n'
    body += f'    {active_char} attack:3; {active_char} charge;\n'
    body += f'    {active_char} attack:2; {active_char} dash;\n'
    body += f'    {active_char} attack:3; {active_char} charge;\n'
    body += f'    {active_char} attack:3; {active_char} dash;\n'
    body += f'    {active_char} attack:3; {active_char} charge;\n'
    body += f'    {active_char} attack:3;\n'
    body += f'  }}\n'
    return body

def _preset_generic_freeze(team, active_char):
    body = f"  for let i=0; i<4; i=i+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} aim;\n'
    body += f'    if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += f'    {active_char} aim;\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} aim:5;\n'
    body += f'  }}\n'
    return body

def _preset_generic_charge_loop(team, active_char):
    body = f"  for let i=0; i<4; i=i+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} attack;\n'
    body += f'    {active_char} charge; {active_char} skill; {active_char} charge; {active_char} burst;\n'
    body += f'    {active_char} charge:2;\n'
    body += f'  }}\n'
    return body

def _preset_generic_stance_dps(team, active_char):
    body = f"  for let i=0; i<4; i=i+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    while .{active_char}.status.{active_char}-stance {{\n'
    body += f'      if .{active_char}.resource >= 1 {{ {active_char} skill; }}\n'
    body += f'      else {{ {active_char} attack; }}\n'
    body += f'    }}\n'
    body += f'  }}\n'
    return body

def _preset_generic_weave(team, active_char):
    body = f"  for let i=0; i<6; i=i+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} attack;\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} attack;\n'
    body += f'    if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += f'    {active_char} attack:4; {active_char} dash;\n'
    body += f'    {active_char} attack:4; {active_char} dash;\n'
    body += f'    {active_char} attack:2;\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} attack;\n'
    body += f'    if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += f'    {active_char} attack:2;\n'
    body += f'  }}\n'
    return body

def _preset_generic_nightsoul(team, active_char):
    body = f"  {active_char} skill;\n"
    body += f"  for let c=0; c<5; c=c+1 {{\n"
    body += f"    {active_char} attack[direction=1]:2;\n"
    body += f"    while .{active_char}.nightsoul.points < 20 && .{active_char}.nightsoul.state {{\n"
    body += f"      wait(1);\n"
    body += f"    }}\n"
    body += f"    if .{active_char}.nightsoul.state {{\n"
    body += f"      {active_char} skill[hold=1];\n"
    body += f"    }}\n"
    body += f"  }}\n"
    return body

def _preset_generic_opener(team, active_char):
    body = f"  for let i=0; i<4; i=i+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    {n} dash;\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} dash;\n'
    body += f'    if .{active_char}.burst.ready {{ {active_char} burst; }}\n'
    body += f'    {active_char} attack;\n'
    body += f'  }}\n'
    return body

def _preset_generic_skirk_alt(team, active_char):
    body = f"  for let i=0; i<4; i=i+1 {{\n"
    for n in team:
        if n != active_char:
            body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
            body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'    if .{active_char}.skill.ready {{ {active_char} skill; }}\n'
    body += f'    {active_char} attack:2; {active_char} burst;\n'
    body += f'    {active_char} attack:5; {active_char} dash;\n'
    body += f'    {active_char} attack:5; {active_char} dash;\n'
    body += f'    {active_char} attack:5; {active_char} dash;\n'
    body += f'    {active_char} attack:2; {active_char} charge; {active_char} dash;\n'
    body += f'    {active_char} attack:5; {active_char} dash;\n'
    body += f'    {active_char} attack:2;\n'
    body += f'  }}\n'
    return body

# ---------- Specialised presets with fallback ----------

def _preset_mualani_surf(team, active_char):
    if "mualani" in team:
        body = "  for let i=0; i<4; i=i+1 {\n"
        for n in team:
            if n != "mualani":
                body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
                body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
        body += '    if .mualani.skill.ready { mualani skill; }\n'
        body += '    mualani charge:3;\n'
        body += '    if .mualani.burst.ready { mualani burst; }\n'
        body += "  }\n"
        return body
    else:
        return _generic_dps_fallback(team, active_char)

def _preset_wanderer_flight(team, active_char):
    if "wanderer" in team:
        body = "  for let i=0; i<4; i=i+1 {\n"
        for n in team:
            if n != "wanderer":
                body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
                body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
        body += '    if .wanderer.skill.ready { wanderer skill; }\n'
        body += '    wanderer attack:6;\n'
        body += '    wanderer charge;\n'
        body += '    if .wanderer.burst.ready { wanderer burst; }\n'
        body += "  }\n"
        return body
    else:
        return _generic_dps_fallback(team, active_char)

def _preset_skirk_weave(team, active_char):
    if "skirk" in team:
        body = "  for let i=0; i<4; i=i+1 {\n"
        for n in team:
            if n != "skirk":
                body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
                body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
        body += '    if .skirk.skill.ready { skirk skill; }\n'
        body += '    skirk attack:2; skirk charge; skirk dash;\n'
        body += '    skirk attack:5; skirk dash;\n' * 3  # repeat 3 times
        body += '    skirk attack:2; skirk charge; skirk dash;\n'
        body += '    skirk attack:5; skirk dash;\n'
        body += '    skirk attack:2;\n'
        body += '    if .skirk.burst.ready { skirk burst; }\n'
        body += "  }\n"
        return body
    else:
        return _generic_dps_fallback(team, active_char)

def _preset_kinich_dps(team, active_char):
    if "kinich" in team:
        body = """
  fn kinich_combo() {
    kinich skill;
    while .kinich.nightsoul.state {
      if .kinich.nightsoul.points == 20 {
        kinich skill[hold=1];
        continue;
      }
      kinich attack;
    }
  }
"""
        body += "  for let i=0; i<4; i=i+1 {\n"
        for n in team:
            if n != "kinich":
                body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
                body += f'    {n} dash;\n'
                body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
        body += "    kinich_combo();\n"
        body += "    if .kinich.burst.ready { kinich burst; }\n"
        for n in team:
            if n != "kinich":
                body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
                body += f'    {n} attack;\n'
        body += "  }\n"
        return body
    else:
        return _generic_dps_fallback(team, active_char)
    
def _preset_mavuika_dps(team, active_char):
    if "mavuika" in team:
        body = "  for let i=0; i<4; i=i+1 {\n"
        for n in team:
            if n != "mavuika":
                body += f'    if .{n}.skill.ready {{ {n} skill; }}\n'
                body += f'    if .{n}.burst.ready {{ {n} burst; }}\n'
        body += '    if .mavuika.skill.ready { mavuika skill; }\n'
        body += '    if .mavuika.burst.ready { mavuika burst; }\n'
        body += '    mavuika charge:8;\n'  # Optimal Mavuika combo
        body += '    mavuika charge; mavuika charge[final=1]; mavuika dash;\n'
        body += '    mavuika charge:2;\n'
        body += "  }\n"
        return body
    else:
        return _generic_dps_fallback(team, active_char)

# ---------- Full list of presets ----------

ROTATION_PRESETS = [
    # Existing generic presets
    ("standard",            _preset_standard),
    ("support_first",       _preset_support_first),
    ("quickswap",           _preset_quickswap),
    ("raiden_hyper",        _preset_raiden_hyper),
    ("ganyu_aimed",         _preset_ganyu_aimed),
    ("wriothesley_charge",  _preset_wriothesley),
    ("heavy_filler",        _preset_heavy_filler),
    ("burst_skill_weave",   _preset_burst_skill_weave),
    ("national",            _preset_national),
    ("hyperbloom_driver",   _preset_hyperbloom),
    ("battery_first",       _preset_battery_first),
    ("melt_ganyu",          _preset_melt_ganyu),
    ("tanky",               _preset_tanky),
    ("kinich_skill",        _preset_kinich),
    # New generic presets
    ("generic_support_burst",   _preset_generic_support_burst),
    ("generic_charge_dps",      _preset_generic_charge_dps),
    ("generic_bond_dps",        _preset_generic_bond_dps),
    ("generic_aim_dps",         _preset_generic_aim_dps),
    ("generic_hypercarry",      _preset_generic_hypercarry),
    ("generic_spread_dps",      _preset_generic_spread_dps),
    ("generic_freeze",          _preset_generic_freeze),
    ("generic_charge_loop",     _preset_generic_charge_loop),
    ("generic_stance_dps",      _preset_generic_stance_dps),
    ("generic_weave",           _preset_generic_weave),
    ("generic_nightsoul",       _preset_generic_nightsoul),
    ("generic_opener",          _preset_generic_opener),
    ("generic_skirk_alt",       _preset_generic_skirk_alt),
    # Specialised presets with fallback
    ("mualani_surf",        _preset_mualani_surf),
    ("wanderer_flight",     _preset_wanderer_flight),
    ("skirk_weave",         _preset_skirk_weave),
    ("kinich_dps",          _preset_kinich_dps),
    ("mavuika_dps", _preset_mavuika_dps),
]

# ── EA helpers ────────────────────────────────────────────────────────────

def _dominates(a: dict, b: dict) -> bool:
    better = False
    for key, direction in (('dps', 1), ('max_hit', 1), ('sd', -1)):
        av, bv = a[key] * direction, b[key] * direction
        if av > bv:
            better = True
        elif av < bv:
            return False
    return better


# ── Public API ────────────────────────────────────────────────────────────

def run_optimizer(
    df,
    lock_chars: list = None,
    ban_chars: list = None,
    gcsim_bin: str = GCSIM_PATH,
    sim_duration: int = 20,
    sim_iterations: int = 150,
    population_size: int = 50,
    generations: int = 30,
    mutation_rate: float = 0.15,
    crossover_rate: float = 0.8,
    tournament_size: int = 3,
    min_character_level: int = 50,
    traveler_override: dict = None,
    traveler_default: str = "anemo",
    start_energy: int = 100,
    # ✅ NEW: enemy parameters
    enemy_level: int = 100,
    enemy_resist: float = 0.1,
    pareto: bool = True,
    stop_flag: list = None,
    progress_callback: Callable = None,
):
    """
    Run the Pareto EA.
    Calls progress_callback(gen, generations, best_obj, top5, pareto_archive)
    after each generation.
    Returns (best_config_str, best_obj, pareto_summary_list).
    """
    if lock_chars is None:
        lock_chars = []
    if ban_chars is None:
        ban_chars = []
    if stop_flag is None:
        stop_flag = [False]

    configs, skipped, warnings = build_character_configs(
        df, min_character_level, traveler_override, traveler_default, start_energy
    )
    all_chars = set(configs.keys())
    lock_set = set(lock_chars)
    ban_set = set(ban_chars)
    
    # Apply bans
    all_chars -= ban_set
    
    # For locked chars filtered out by min level, rebuild without level cap
    missing_locked = lock_set - all_chars - ban_set
    if missing_locked:
        full_configs, _, _ = build_character_configs(df, 0, traveler_override, traveler_default, start_energy)
        for lc in missing_locked:
            if lc in full_configs:
                configs[lc] = full_configs[lc]
                all_chars.add(lc)
                warnings.append(f"'{lc}' is below min level but included because it's locked in.")

    if lock_set & ban_set:
        raise ValueError(f"Characters can't be both locked and banned: {lock_set & ban_set}")
    missing = lock_set - all_chars
    if missing:
        raise ValueError(f"Locked characters not found in roster: {missing}")
    if len(all_chars) < 4:
        raise RuntimeError("Need at least 4 eligible characters.")

    # ── Inner functions ───────────────────────────────────────────────────

    def build_config(team_tuple):
        preset_id, start_idx, *chars = team_tuple
        preset_func = ROTATION_PRESETS[preset_id][1]
        _, rotation_body = preset_func(chars)
        active = chars[start_idx]
        cfg = (
            f"options iteration={sim_iterations} duration={sim_duration} swap_delay=4;\n"
            f"target lvl={enemy_level} resist={enemy_resist:.2f} radius=2 pos=0,2.4 hp=999999999;\n"
            f"energy every interval=480,720 amount=1;\n\n"
        )
        for name in chars:
            cfg += configs[name] + '\n'
        cfg += f'active {active};\n\nwhile 1 {{\n{rotation_body}}}\n'
        return cfg

    # ✅ FIX: Add error handling and stop flag check
    def fitness(ind):
        if stop_flag[0]:
            return {"dps": 0.0, "max_hit": 0.0, "sd": 0.0, "stopped": True}
        try:
            result = run_gcsim(build_config(ind), gcsim_bin, sim_iterations, sim_duration)
            if "error" in result and result["error"]:
                return {"dps": 1.0, "max_hit": 1.0, "sd": 99999.0, "errored": True}
            return result
        except Exception as e:
            return {"dps": 1.0, "max_hit": 1.0, "sd": 99999.0, "errored": True, "error": str(e)}

    def random_team():
        locked = list(lock_set)
        random.shuffle(locked)
        needed = 4 - len(locked)
        others = random.sample(list(all_chars - lock_set), needed)
        chars = locked + others
        random.shuffle(chars)
        preset = random.randrange(len(ROTATION_PRESETS))
        start = random.randrange(4)
        return (preset, start) + tuple(chars)

    def crossover(p1, p2):
        child = [
            p1[0] if random.random() < 0.5 else p2[0],
            p1[1] if random.random() < 0.5 else p2[1],
        ]
        raw_chars = [p1[i] if random.random() < 0.5 else p2[i] for i in range(2, len(p1))]
        # Keep each locked char exactly once
        seen_locked = {}
        for i, c in enumerate(raw_chars):
            if c in lock_set and c not in seen_locked:
                seen_locked[c] = i
        missing_locked = [lc for lc in lock_set if lc not in seen_locked]
        free_slots = [i for i, c in enumerate(raw_chars) if c not in lock_set]
        random.shuffle(free_slots)
        for lc in missing_locked:
            if free_slots:
                raw_chars[free_slots.pop()] = lc
        # Deduplicate
        seen, available = set(), list(all_chars - set(raw_chars))
        random.shuffle(available)
        for i in range(4):
            if raw_chars[i] in seen:
                raw_chars[i] = available.pop() if available else random.choice(
                    list(all_chars - set(raw_chars)))
            seen.add(raw_chars[i])
        child.extend(raw_chars)
        return tuple(child)

    def mutate(team):
        if random.random() >= mutation_rate:
            return team
        tl = list(team)
        r = random.random()
        if r < 0.1:
            tl[0] = random.randrange(len(ROTATION_PRESETS))
        elif r < 0.2:
            tl[1] = random.randrange(4)
        else:
            mutable = [i for i in range(2, 6) if tl[i] not in lock_set]
            if mutable:
                idx = random.choice(mutable)
                available = [c for c in all_chars if c not in tl[2:]]
                if available:
                    tl[idx] = random.choice(available)
        return tuple(tl)

    def tournament(population, scores):
        sel = random.sample(list(zip(population, scores)), min(tournament_size, len(population)))
        sel.sort(key=lambda x: x[1]['dps'], reverse=True)
        return sel[0][0]

    # ── Main loop ─────────────────────────────────────────────────────────

    population = [random_team() for _ in range(population_size)]
    best_overall = (None, {'dps': 0.0, 'max_hit': 0.0, 'sd': 0.0})
    pareto_archive = []

    for gen in range(generations):
        if stop_flag[0]:
            break

        # Evaluate population in parallel — 4 GCSim processes at once
        scores = [None] * len(population)
        done_count = 0
        with ThreadPoolExecutor(max_workers=2) as pool:  # 2 keeps Streamlit Cloud stable
            fut_map = {pool.submit(fitness, ind): i for i, ind in enumerate(population)}
            for fut in as_completed(fut_map):
                scores[fut_map[fut]] = fut.result()
                done_count += 1
                if progress_callback and done_count % 5 == 0:
                    # Send lightweight per-individual update every 5 completions
                    best_so_far = max(
                        (s for s in scores if s is not None),
                        key=lambda s: s["dps"],
                        default={"dps": 0.0, "max_hit": 0.0, "sd": 0.0},
                    )
                    progress_callback(
                        gen + 1, generations, best_so_far,
                        [], [], configs,
                        {"individuals_done": done_count, "individuals_total": len(population)},
                    )
        
        # ✅ Replace errored individuals
        for i, score in enumerate(scores):
            if score.get("errored", False):
                population[i] = random_team()
                scores[i] = fitness(population[i])

        if pareto:
            for team, obj in zip(population, scores):
                dominated = any(_dominates(aobj, obj) for _, aobj in pareto_archive)
                if not dominated:
                    pareto_archive = [(t, o) for t, o in pareto_archive if not _dominates(obj, o)]
                    pareto_archive.append((team, obj))
                    # Cap archive size to keep dominance checks fast
                    if len(pareto_archive) > 100:
                        pareto_archive.sort(key=lambda x: x[1]["dps"], reverse=True)
                        pareto_archive = pareto_archive[:100]

        fitness_vals = [s['dps'] for s in scores]
        best_idx = fitness_vals.index(max(fitness_vals))
        if scores[best_idx].get("stopped", False):
            break
        if scores[best_idx]['dps'] > best_overall[1]['dps']:
            best_overall = (population[best_idx], scores[best_idx])

        top5_indices = sorted(range(len(fitness_vals)), key=lambda i: fitness_vals[i], reverse=True)[:5]
        top5 = [(population[i], scores[i]) for i in top5_indices]

        if progress_callback:
            progress_callback(
                gen + 1, generations, best_overall[1], top5, pareto_archive, configs,
                {"individuals_done": len(population), "individuals_total": len(population)},
            )

        # Evolve
        elite_count = max(1, int(population_size * 0.2))
        elites = [ind for ind, _ in sorted(zip(population, fitness_vals), key=lambda x: x[1], reverse=True)[:elite_count]]
        new_pop = elites.copy()
        while len(new_pop) < population_size:
            p1, p2 = tournament(population, scores), tournament(population, scores)
            child = crossover(p1, p2) if random.random() < crossover_rate else p1
            child = mutate(child)
            new_pop.append(child)
        population = new_pop

    # ── Build output ──────────────────────────────────────────────────────

    best_config = build_config(best_overall[0]) if best_overall[0] else ""

    pareto_archive.sort(key=lambda x: x[1]['dps'], reverse=True)
    top10 = pareto_archive[:10]

    pareto_summary = []
    pareto_configs = []
    for team, obj in top10:
        preset_id, start_idx, *chars = team
        pareto_summary.append({
            'preset': ROTATION_PRESETS[preset_id][0],
            'start_char': chars[start_idx],
            'team': chars,
            'dps': obj['dps'],
            'max_hit': obj['max_hit'],
            'sd': obj['sd'],
        })
        pareto_configs.append(build_config(team))

    return best_config, best_overall[1], pareto_summary, pareto_configs, warnings