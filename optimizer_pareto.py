"""
optimizer_pareto.py
Evolutionary algorithm that optimises TEAM COMPOSITION.
Rotation is chosen from a bank of hand-crafted presets.
Objectives: maximise DPS + max single hit, minimise SD (Pareto-mode).
"""
import random
from typing import Callable, Optional

from config_builder import build_character_configs
from gcsim_manager import run_gcsim, GCSIM_PATH

# ── Rotation presets ──────────────────────────────────────────────────────

FILLER_ACTION = {'ganyu': 'aim', 'neuvillette': 'charge'}


def _filler(active):
    return FILLER_ACTION.get(active, 'attack')


def _preset_standard(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body


def _preset_support_first(team):
    main_dps, others, active = team[-1], team[:-1], team[0]
    body = ""
    for n in others:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  if .{main_dps}.burst.ready {{ {main_dps} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body


def _preset_quickswap(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body


def _preset_raiden_hyper(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  if .{active}.name == "raiden" {{ {active} attack:15; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body


def _preset_ganyu_aimed(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  if .{active}.name == "ganyu" {{ {active} aim; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body


def _preset_wriothesley(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  if .{active}.name == "wriothesley" {{ {active} charge; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body


def _preset_heavy_filler(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)},{_filler(active)},{_filler(active)};\n'
    return active, body


def _preset_burst_skill_weave(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body


def _preset_national(team):
    main_dps, others, active = team[-1], team[:-1], team[0]
    body = ""
    for n in others:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  if .{main_dps}.burst.ready {{ {main_dps} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body


def _preset_hyperbloom(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)}:6;\n'
    return active, body


def _preset_battery_first(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  {active} {_filler(active)};\n'
    return active, body


def _preset_melt_ganyu(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    body += f'  if .{active}.name == "ganyu" {{ {active} aim; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body


def _preset_tanky(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  {active} {_filler(active)},{_filler(active)};\n'
    return active, body


def _preset_kinich(team):
    active, body = team[0], ""
    for n in team:
        body += f'  if .{n}.burst.ready {{ {n} burst; }}\n'
    for n in team:
        body += f'  if .{n}.skill.ready {{ {n} skill; }}\n'
    body += f'  if .{active}.name == "kinich" {{ {active} attack:4; }}\n'
    body += f'  else {{ {active} attack; }}\n'
    return active, body


ROTATION_PRESETS = [
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
    pareto: bool = True,
    stop_flag: list = None,      # stop_flag[0] = True to abort
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
    if stop_flag is None:
        stop_flag = [False]

    configs, skipped, warnings = build_character_configs(
        df, min_character_level, traveler_override, traveler_default
    )
    all_chars = set(configs.keys())
    lock_set = set(lock_chars)
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
            f"target lvl=100 resist=0.1 particle_threshold=250000 particle_drop_count=1;\n\n"
        )
        for name in chars:
            cfg += configs[name] + '\n'
        cfg += f'active {active};\n\nwhile 1 {{\n{rotation_body}}}\n'
        return cfg

    def fitness(team):
        return run_gcsim(build_config(team), gcsim_bin, sim_iterations, sim_duration)

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

        scores = [fitness(ind) for ind in population]

        if pareto:
            for team, obj in zip(population, scores):
                dominated = any(_dominates(aobj, obj) for _, aobj in pareto_archive)
                if not dominated:
                    pareto_archive = [(t, o) for t, o in pareto_archive if not _dominates(obj, o)]
                    pareto_archive.append((team, obj))

        fitness_vals = [s['dps'] for s in scores]
        best_idx = fitness_vals.index(max(fitness_vals))
        if scores[best_idx]['dps'] > best_overall[1]['dps']:
            best_overall = (population[best_idx], scores[best_idx])

        top5_indices = sorted(range(len(fitness_vals)), key=lambda i: fitness_vals[i], reverse=True)[:5]
        top5 = [(population[i], scores[i]) for i in top5_indices]

        if progress_callback:
            progress_callback(gen + 1, generations, best_overall[1], top5, pareto_archive, configs)

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
