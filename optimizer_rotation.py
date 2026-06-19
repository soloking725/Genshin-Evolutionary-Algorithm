"""
optimizer_rotation.py
Evolutionary algorithm that co-evolves TEAM COMPOSITION + ROTATION SEQUENCE.
The rotation is encoded as a token array; the EA can mutate and crossover
both genes simultaneously.
"""
import random
import math
from collections import Counter
from typing import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from config_builder import build_character_configs
from gcsim_manager import run_gcsim, GCSIM_PATH

# ── Token encoding ────────────────────────────────────────────────────────

SIMPLE_ACTIONS = [
    "skill", "burst",
    "attack:1", "attack:2", "attack:3", "attack:4", "attack:5",
    "charge", "aim",
]
NUM_SIMPLE = len(SIMPLE_ACTIONS)

COMPLEX_COMMANDS = [
    ("energy_burst",    5, lambda slot, var: f"if .{slot}.energy >= {50 + var*10} {{ {slot} burst; }}"),
    ("energy_skill_low",5, lambda slot, var: f"if .{slot}.energy < {50 + var*10} {{ {slot} skill; }}"),
    ("skill_ready",     1, lambda slot, var: f"if .{slot}.skill.ready {{ {slot} skill; }}"),
]

TOTAL_COMMANDS = NUM_SIMPLE + sum(num for _, num, _ in COMPLEX_COMMANDS)
NOOP_TOKEN     = TOTAL_COMMANDS * 4
MAX_ROT_LEN    = 80

COMPLEX_OFFSET = NUM_SIMPLE
COMPLEX_INFO   = []
_offset = 0
for _name, _num, _ in COMPLEX_COMMANDS:
    COMPLEX_INFO.append((_name, _num, COMPLEX_OFFSET + _offset))
    _offset += _num

FILLER_ACTION = {'ganyu': 'aim', 'neuvillette': 'charge'}


# ── Rotation preset to tokens ─────────────────────────────────────────────

def _filler(active):
    return FILLER_ACTION.get(active, 'attack:1')


def _preset_standard(team):
    active = team[0]
    seq = []
    for slot, name in enumerate(team):
        seq.append((slot, "burst"))
        seq.append((slot, "skill"))
    seq.append((0, _filler(active)))
    return active, seq


def _preset_support_first(team):
    active = team[0]
    seq = []
    for slot in range(1, 4):
        seq.append((slot, "burst"))
    seq.append((3, "burst"))
    for slot in range(4):
        seq.append((slot, "skill"))
    seq.append((0, _filler(active)))
    return active, seq


def _preset_quickswap(team):
    active = team[0]
    seq = []
    for slot in range(4):
        seq.append((slot, "skill"))
    for slot in range(4):
        seq.append((slot, "burst"))
    seq.append((0, _filler(active)))
    return active, seq


ROTATION_PRESETS = [
    ("standard",      _preset_standard),
    ("support_first", _preset_support_first),
    ("quickswap",     _preset_quickswap),
]


def preset_to_tokens(preset_func, team) -> list:
    _, seq = preset_func(team)
    tokens = []
    for slot, cmd in seq:
        if cmd in SIMPLE_ACTIONS:
            tokens.append(slot * TOTAL_COMMANDS + SIMPLE_ACTIONS.index(cmd))
    if len(tokens) > MAX_ROT_LEN:
        tokens = tokens[:MAX_ROT_LEN]
    tokens += [NOOP_TOKEN] * (MAX_ROT_LEN - len(tokens))
    return tokens


def decode_rotation(tokens: list, team: list) -> str:
    """Decode token list → GCSim rotation body string.

    Guarantees the rotation is safe to execute:
    - At least one unconditional attack so GCSim never infinite-loops
    - All skill/burst actions are wrapped in .ready checks
    - Stripped of leading/trailing whitespace
    """
    actions = []
    has_unconditional = False

    for t in tokens:
        if t >= NOOP_TOKEN:
            break
        slot  = t // TOTAL_COMMANDS
        cmd_i = t % TOTAL_COMMANDS
        name  = team[slot] if slot < len(team) else team[0]

        if cmd_i < NUM_SIMPLE:
            cmd = SIMPLE_ACTIONS[cmd_i]
            if cmd in ("skill", "burst"):
                # conditional — safe
                actions.append(f"  if .{name}.{cmd}.ready {{ {name} {cmd}; }}")
            else:
                # unconditional attack / charge / aim
                actions.append(f"  {name} {cmd};")
                has_unconditional = True
        else:
            for cname, num, base in COMPLEX_INFO:
                if base <= cmd_i < base + num:
                    var = cmd_fn = cmd_i - base
                    gen_fn = next(g for n, c, g in COMPLEX_COMMANDS if n == cname)
                    actions.append(f"  {gen_fn(name, var)}")
                    break

    # If every action is conditional, the while-loop may never advance.
    # Append one unconditional attack on the active character as a safety valve.
    if not has_unconditional or not actions:
        active = team[0] if team else "unknown"
        actions.append(f"  {active} attack;")

    return "\n".join(actions) + "\n"


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


def _repair_team(team_list, lock_set, all_chars):
    """Build a valid 4-character team from team_list, deduplicating as needed."""
    result = [None, None, None, None]
    indices = list(range(4))
    random.shuffle(indices)
    # Place locked characters first
    for lc in lock_set:
        if indices:
            result[indices.pop()] = lc
    # Build candidate list — deduplicated, excluding locked chars already placed
    seen = set(c for c in result if c is not None)
    candidates = []
    for c in team_list:
        if c not in lock_set and c not in seen and c not in candidates:
            candidates.append(c)
            seen.add(c)
    random.shuffle(candidates)
    # Fill remaining slots, tracking seen to guarantee uniqueness
    used = set(c for c in result if c is not None)
    for i in range(4):
        if result[i] is None:
            if candidates:
                c = candidates.pop(0)
            else:
                pool = list(all_chars - used - lock_set)
                random.shuffle(pool)
                c = pool[0] if pool else random.choice(list(all_chars - used or all_chars))
            result[i] = c
            used.add(c)
    return tuple(result)


def _random_token():
    if random.random() < 0.5:
        return random.randrange(4) * TOTAL_COMMANDS + random.randrange(NUM_SIMPLE)
    cname, num_var, _ = random.choice(COMPLEX_COMMANDS)
    base = COMPLEX_OFFSET + sum(cnt for n, cnt, g in COMPLEX_COMMANDS if n < cname)
    return random.randrange(4) * TOTAL_COMMANDS + base + random.randrange(num_var)


def _population_diversity(population):
    teams = [team for team, _ in population]
    unique = len(set(teams))
    team_uniq = unique / len(population)

    rot_tokens = [tuple(rot) for _, rot in population]
    n = len(rot_tokens)
    total_dist = sum(
        sum(1 for a, b in zip(rot_tokens[i], rot_tokens[j]) if a != b)
        for i in range(n) for j in range(i+1, n)
    )
    max_pairs = n * (n-1) / 2
    rot_div = (total_dist / max_pairs) / MAX_ROT_LEN if max_pairs > 0 else 0.0

    counter = Counter()
    total = 0
    for _, rot in population:
        for t in rot:
            if t < NOOP_TOKEN:
                counter[t] += 1
                total += 1
    entropy = 0.0
    if total:
        for cnt in counter.values():
            p = cnt / total
            entropy -= p * math.log2(p)

    return {'team_uniqueness': team_uniq, 'rotation_diversity': rot_div, 'action_entropy': entropy}


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
    enemy_level: int = 100,
    enemy_resist: float = 0.1,
    pareto: bool = True,
    stop_flag: list = None,
    progress_callback: Callable = None,
):
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
    ban_set  = set(ban_chars)

    # Bypass min level for locked chars that got filtered out
    missing_locked = lock_set - all_chars - ban_set
    if missing_locked:
        full_configs, _, _ = build_character_configs(df, 0, traveler_override, traveler_default, start_energy)
        for lc in missing_locked:
            if lc in full_configs:
                configs[lc] = full_configs[lc]
                all_chars.add(lc)
                warnings.append(f"'{lc}' is below min level but included because it's locked in.")

    all_chars -= ban_set
    if lock_set & ban_set:
        raise ValueError(f"Characters can't be both locked and banned: {lock_set & ban_set}")
    missing = lock_set - all_chars
    if missing:
        raise ValueError(f"Locked characters not found in roster or CSV: {missing}")
    if len(all_chars) < 4:
        raise RuntimeError("Need at least 4 eligible characters after applying ban list.")

    # ── Inner functions ───────────────────────────────────────────────────

    def build_config(individual):
        team, rot = individual
        rot_body = decode_rotation(rot, list(team))
        active = team[0]
        cfg = (
            f"options iteration={sim_iterations} duration={sim_duration} swap_delay=4;\n"
            f"target lvl={enemy_level} resist={enemy_resist:.2f} particle_threshold=250000 particle_drop_count=1;\n\n"
        )
        for name in team:
            cfg += configs[name] + '\n'
        cfg += f'active {active};\n\nwhile 1 {{\n{rot_body}}}\n'
        return cfg

    # ✅ Robust fitness with stop flag and error handling
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

    def create_individual():
        locked = list(lock_set)
        random.shuffle(locked)
        needed = 4 - len(locked)
        # ✅ Ensure unique characters
        available = list(all_chars - lock_set)
        random.shuffle(available)
        others = available[:needed] if len(available) >= needed else random.choices(available, k=needed)
        team = locked + others
        team = list(dict.fromkeys(team))  # Deduplicate
        while len(team) < 4:
            extra = random.choice(list(all_chars - set(team)))
            team.append(extra)
        random.shuffle(team)
        team = tuple(team)

        if random.random() < 0.8:
            preset_func = random.choice(ROTATION_PRESETS)[1]
            rot = preset_to_tokens(preset_func, list(team))
        else:
            length = random.randint(5, MAX_ROT_LEN)
            rot = [_random_token() for _ in range(length)]
            rot += [NOOP_TOKEN] * (MAX_ROT_LEN - length)
        return (team, rot)

    def tournament(population, scores):
        sel = random.sample(list(zip(population, scores)), min(tournament_size, len(population)))
        sel.sort(key=lambda x: x[1]['dps'], reverse=True)
        return sel[0][0]

    def crossover(ind1, ind2):
        t1, r1 = ind1
        t2, r2 = ind2
        child_team = _repair_team(
            [t1[i] if random.random() < 0.5 else t2[i] for i in range(4)],
            lock_set, all_chars
        )
        point = random.randint(1, MAX_ROT_LEN - 1)
        child_rot = r1[:point] + r2[point:]
        return (child_team, child_rot)

    def mutate(ind):
        team, rot = ind
        # Mutate team
        if random.random() < mutation_rate:
            mutable = [i for i in range(4) if team[i] not in lock_set]
            if mutable:
                idx = random.choice(mutable)
                available = [c for c in all_chars if c not in team]
                if available:
                    tl = list(team)
                    tl[idx] = random.choice(available)
                    team = _repair_team(tl, lock_set, all_chars)
        # Mutate rotation
        rot = list(rot)
        for i in range(MAX_ROT_LEN):
            if random.random() < 0.05:
                rot[i] = _random_token()
            elif random.random() < 0.02:
                rot.insert(i, _random_token())
                rot.pop()
        if random.random() < 0.1:
            i = random.randint(0, MAX_ROT_LEN - 2)
            rot[i], rot[i+1] = rot[i+1], rot[i]
        return (team, rot)

    # ── Main loop ─────────────────────────────────────────────────────────

    population = [create_individual() for _ in range(population_size)]
    best_overall = (None, {'dps': 0.0, 'max_hit': 0.0, 'sd': 0.0})
    pareto_archive = []

    for gen in range(generations):
        if stop_flag[0]:
            break

        scores = [None] * len(population)
        done_count = 0
        with ThreadPoolExecutor(max_workers=2) as pool:  # 2 keeps Streamlit Cloud stable
            fut_map = {pool.submit(fitness, ind): i for i, ind in enumerate(population)}
            for fut in as_completed(fut_map):
                scores[fut_map[fut]] = fut.result()
                done_count += 1
                if progress_callback and done_count % 5 == 0:
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
                population[i] = create_individual()
                scores[i] = fitness(population[i])

        if pareto:
            for ind, obj in zip(population, scores):
                dominated = any(_dominates(aobj, obj) for _, aobj in pareto_archive)
                if not dominated:
                    pareto_archive = [(t, o) for t, o in pareto_archive if not _dominates(obj, o)]
                    pareto_archive.append((ind, obj))
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

        div = _population_diversity(population)

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
    for ind, obj in top10:
        team, rot = ind
        pareto_summary.append({
            'team': list(team),
            'dps': obj['dps'],
            'max_hit': obj['max_hit'],
            'sd': obj['sd'],
        })
        pareto_configs.append(build_config(ind))

    return best_config, best_overall[1], pareto_summary, pareto_configs, warnings