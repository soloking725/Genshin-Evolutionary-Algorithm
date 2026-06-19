"""
config_builder.py
Converts a pandas DataFrame (from enka_fetcher or a CSV export) into
GCSim character-config strings ready for simulation.
"""
import re
from collections import Counter

import pandas as pd


# ── GCSim key sets ──────────────────────────────────────────────────────────

GCSIM_CHARACTER_KEYS = {
    'aino', 'albedo', 'alhaitham', 'aloy', 'amber', 'arlecchino', 'ayaka', 'ayato',
    'baizhu', 'barbara', 'beidou', 'bennett', 'candace', 'charlotte', 'chasca',
    'chevreuse', 'chiori', 'chongyun', 'citlali', 'clorinde', 'collei', 'columbina',
    'cyno', 'dahlia', 'dehya', 'diluc', 'diona', 'dori', 'emilie', 'escoffier', 'eula',
    'faruzan', 'fischl', 'flins', 'freminet', 'furina', 'gaming', 'ganyu', 'gorou',
    'heizou', 'hutao', 'ineffa', 'itto', 'jean', 'kaeya', 'kaveh', 'kazuha', 'keqing',
    'kinich', 'kirara', 'klee', 'kokomi', 'kuki', 'lanyan', 'lauma', 'layla', 'lisa',
    'lynette', 'lyney', 'mavuika', 'mika', 'mizuki', 'mona', 'mualani', 'nahida',
    'navia', 'neuvillette', 'nilou', 'ningguang', 'noelle', 'ororon', 'qiqi', 'raiden',
    'razor', 'rosaria', 'sara', 'sayu', 'sethos', 'shenhe', 'sigewinne', 'skirk',
    'sucrose', 'tartaglia', 'thoma', 'tighnari', 'varesa', 'venti', 'wanderer',
    'wriothesley', 'xiangling', 'xianyun', 'xiao', 'xilonen', 'xingqiu', 'xinyan',
    'yaemiko', 'yanfei', 'yaoyao', 'yelan', 'yoimiya', 'yunjin', 'zhongli',
}
TRAVELER_ELEMENTS = ('anemo', 'geo', 'electro', 'dendro', 'hydro', 'pyro', 'cryo')
for _e in TRAVELER_ELEMENTS:
    GCSIM_CHARACTER_KEYS.add(f'aether{_e}')
    GCSIM_CHARACTER_KEYS.add(f'lumine{_e}')

CHARACTER_NAME_OVERRIDES = {
    'kamisatoayaka': 'ayaka', 'kamisatoayato': 'ayato', 'raidenshogun': 'raiden',
    'sangonomiyakokomi': 'kokomi', 'kujousara': 'sara', 'kukishinobu': 'kuki',
    'shikanoinheizou': 'heizou', 'aratakiitto': 'itto', 'kaedeharakazuha': 'kazuha',
    'childe': 'tartaglia', 'scaramouche': 'wanderer', 'kusanali': 'nahida',
    'lesserlordkusanali': 'nahida',
}

GCSIM_WEAPON_KEYS = {
    'absolution', 'akuoumaru', 'alleyhunter', 'amenomakageuchi', 'amosbow', 'apprenticesnotes',
    'aquasimulacra', 'aquilafavonia', 'ashgravendrinkinghorn', 'astralvulturescrimsonplumage',
    'athousandblazingsuns', 'athousandfloatingdreams', 'azurelight', 'balladoftheboundlessblue',
    'balladofthefjords', 'beaconofthereedsea', 'beginnersprotector', 'blackcliffagate',
    'blackclifflongsword', 'blackcliffpole', 'blackcliffslasher', 'blackcliffwarbow',
    'blackmarrowlantern', 'blacktassel', 'bloodsoakedruins', 'bloodtaintedgreatsword',
    'calamityofeshu', 'calamityqueller', 'cashflowsupervision', 'chainbreaker', 'cinnabarspindle',
    'cloudforged', 'compoundbow', 'coolsteel', 'cranesechoingcall', 'crescentpike',
    'crimsonmoonssemblance', 'darkironsword', 'dawningfrost', 'deathmatch', 'debateclub',
    'dialoguesofthedesertsages', 'dodocotales', 'dragonsbane', 'dragonspinespear', 'dullblade',
    'earthshaker', 'elegyfortheend', 'emeraldorb', 'endoftheline', 'engulfinglightning',
    'etherlightspindlelute', 'everlastingmoonglow', 'eyeofperception', 'fadingtwilight',
    'fangofthemountainking', 'favoniuscodex', 'favoniusgreatsword', 'favoniuslance',
    'favoniussword', 'favoniuswarbow', 'ferrousshadow', 'festeringdesire', 'filletblade',
    'finaleofthedeep', 'fleuvecendreferryman', 'flowerwreathedfeathers', 'flowingpurity',
    'fluteofezpitzal', 'footprintoftherainbow', 'forestregalia', 'fracturedhalo', 'freedomsworn',
    'frostbearer', 'fruitfulhook', 'fruitoffulfillment', 'hakushinring', 'halberd', 'hamayumi',
    'harangeppakufutsu', 'harbingerofdawn', 'huntersbow', 'hunterspath', 'ibispiercer',
    'ironpoint', 'ironsting', 'jadefallssplendor', 'kagotsurubeisshin', 'kagurasverity',
    'katsuragikirinagamasa', 'keyofkhajnisut', 'kingssquire', 'kitaincrossspear',
    'lightoffoliarincision', 'lionsroar', 'lithicblade', 'lithicspear',
    'lostprayertothesacredwinds', 'lumidouceelegy', 'luxurioussealord', 'magicguide',
    'mailedflower', 'makhairaaquamarine', 'mappamare', 'masterkey', 'memoryofdust', 'messenger',
    'missivewindspear', 'mistsplitterreforged', 'mitternachtswaltz', 'moonpiercer',
    'moonweaversdawn', 'mountainbracingbolt', 'mouunsmoon', 'nightweaverslookingglass',
    'nocturnescurtaincall', 'oathsworneye', 'oldmercspal', 'otherworldlystory', 'peakpatrolsong',
    'pocketgrimoire', 'polarstar', 'portablepowersaw', 'predator', 'primordialjadecutter',
    'primordialjadewingedspear', 'prospectorsdrill', 'prospectorsshovel', 'prototypeamber',
    'prototypearchaic', 'prototypecrescent', 'prototyperancour', 'prototypestarglitter',
    'rainbowserpentbow', 'rainslasher', 'rangegauge', 'ravenbow', 'recurvebow',
    'redhornstonethresher', 'reliquaryoftruth', 'rightfulreward', 'ringofyaxche', 'royalbow',
    'royalgreatsword', 'royalgrimoire', 'royallongsword', 'royalspear', 'rust', 'sacrificersstaff',
    'sacrificialbow', 'sacrificialfragments', 'sacrificialgreatsword', 'sacrificialjade',
    'sacrificialsword', 'sapwoodblade', 'scionoftheblazingsun', 'seasonedhuntersbow',
    'sequenceofsolitude', 'serenityscall', 'serpentspine', 'sharpshootersoath',
    'silvershowerheartstrings', 'silversword', 'skyridergreatsword', 'skyridersword',
    'skywardatlas', 'skywardblade', 'skywardharp', 'skywardpride', 'skywardspine', 'slingshot',
    'snarehook', 'snowtombedstarsilver', 'solarpearl', 'songofbrokenpines', 'songofstillness',
    'splendoroftranquilwaters', 'staffofhoma', 'staffofthescarletsands', 'starcallerswatch',
    'sturdybone', 'summitshaper', 'sunnymorningsleepin', 'surfsup', 'swordofdescension',
    'swordofnarzissenkreuz', 'symphonistofscents', 'talkingstick', 'tamayurateinoohanashi',
    'thealleyflash', 'thebell', 'theblacksword', 'thecatch', 'thedockhandsassistant',
    'thefirstgreatmagic', 'theflute', 'thestringless', 'theunforged', 'theviridescenthunt',
    'thewidsith', 'thrillingtalesofdragonslayers', 'thunderingpulse', 'tidalshadow',
    'tomeoftheeternalflow', 'toukaboushigure', 'travelershandysword', 'tulaytullahsremembrance',
    'twinnephrite', 'ultimateoverlordsmegamagicsword', 'urakumisugiri', 'verdict', 'vividnotions',
    'vortexvanquisher', 'wanderingevenstar', 'wastergreatsword', 'wavebreakersfin',
    'waveridingwhirl', 'whiteblind', 'whiteirongreatsword', 'whitetassel', 'windblumeode',
    'wineandsong', 'wolffang', 'wolfsgravestone', 'xiphosmoonlight',
}

GCSIM_SET_KEYS = {
    'adventurer', 'archaicpetra', 'aubadeofmorningstarandmoon', 'berserker', 'blizzardstrayer',
    'bloodstainedchivalry', 'braveheart', 'crimsonwitchofflames', 'deepwoodmemories',
    'defenderswill', 'desertpavilionchronicle', 'echoesofanoffering', 'emblemofseveredfate',
    'finaleofthedeepgalleries', 'flowerofparadiselost', 'fragmentofharmonicwhimsy', 'gambler',
    'gildeddreams', 'gladiatorsfinale', 'goldentroupe', 'heartofdepth', 'huskofopulentdreams',
    'instructor', 'lavawalker', 'longnightsoath', 'luckydog', 'maidenbeloved',
    'marechausseehunter', 'martialartist', 'nightoftheskysunveiling',
    'nighttimewhispersintheechoingwoods', 'noblesseoblige', 'nymphsdream', 'obsidiancodex',
    'oceanhuedclam', 'paleflame', 'prayersfordestiny', 'prayersforillumination',
    'prayersforwisdom', 'prayerstospringtime', 'resolutionofsojourner', 'retracingbolide',
    'scholar', 'scrolloftheheroofcindercity', 'shimenawasreminiscence', 'silkenmoonsserenade',
    'songofdayspast', 'tenacityofthemillelith', 'theexile', 'thunderingfury', 'thundersoother',
    'tinymiracle', 'travelingdoctor', 'unfinishedreverie', 'vermillionhereafter',
    'viridescentvenerer', 'vourukashasglow', 'wandererstroupe',
}

FIGHT_PROP_TO_GCSIM = {
    'FIGHT_PROP_HP':                ('hp',       False),
    'FIGHT_PROP_HP_PERCENT':        ('hp%',      True),
    'FIGHT_PROP_ATTACK':            ('atk',      False),
    'FIGHT_PROP_ATTACK_PERCENT':    ('atk%',     True),
    'FIGHT_PROP_DEFENSE':           ('def',      False),
    'FIGHT_PROP_DEFENSE_PERCENT':   ('def%',     True),
    'FIGHT_PROP_CRITICAL':          ('cr',       True),
    'FIGHT_PROP_CRITICAL_HURT':     ('cd',       True),
    'FIGHT_PROP_CHARGE_EFFICIENCY': ('er',       True),
    'FIGHT_PROP_ELEMENT_MASTERY':   ('em',       False),
    'FIGHT_PROP_HEAL_ADD':          ('heal',     True),
    'FIGHT_PROP_FIRE_ADD_HURT':     ('pyro%',    True),
    'FIGHT_PROP_WATER_ADD_HURT':    ('hydro%',   True),
    'FIGHT_PROP_WIND_ADD_HURT':     ('anemo%',   True),
    'FIGHT_PROP_ICE_ADD_HURT':      ('cryo%',    True),
    'FIGHT_PROP_ELEC_ADD_HURT':     ('electro%', True),
    'FIGHT_PROP_GRASS_ADD_HURT':    ('dendro%',  True),
    'FIGHT_PROP_ROCK_ADD_HURT':     ('geo%',     True),
    'FIGHT_PROP_PHYSICAL_ADD_HURT': ('phys%',    True),
}

ELEMENT_DMG_PROP_TO_ELEMENT = {
    'FIGHT_PROP_FIRE_ADD_HURT':  'pyro',
    'FIGHT_PROP_WATER_ADD_HURT': 'hydro',
    'FIGHT_PROP_WIND_ADD_HURT':  'anemo',
    'FIGHT_PROP_ICE_ADD_HURT':   'cryo',
    'FIGHT_PROP_ELEC_ADD_HURT':  'electro',
    'FIGHT_PROP_GRASS_ADD_HURT': 'dendro',
    'FIGHT_PROP_ROCK_ADD_HURT':  'geo',
}

SUBSTAT_RE = re.compile(r'^([A-Z_]+)\+(-?[\d.]+)$')


# ── Name helpers ─────────────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    return re.sub(r"""[\s'".\\-]""", "", str(name)).lower()


def _resolve_traveler(label: str, row: pd.Series, warnings: list,
                      traveler_override: dict, traveler_default: str) -> str:
    base = 'aether' if label.strip().lower() == 'aether' else 'lumine'
    if label in traveler_override:
        elem = traveler_override[label]
        warnings.append(f"{label}: using override element '{elem}'.")
        return f'{base}{elem}'
    for i in range(1, 6):
        main_type = row.get(f'Artifact {i} Main Stat Type')
        if pd.notna(main_type) and main_type in ELEMENT_DMG_PROP_TO_ELEMENT:
            elem = ELEMENT_DMG_PROP_TO_ELEMENT[main_type]
            warnings.append(f"{label}: auto-detected '{elem}' from goblet.")
            return f'{base}{elem}'
    for i in range(1, 6):
        for j in range(1, 5):
            sub = row.get(f'Artifact {i} Sub {j}')
            if pd.notna(sub):
                for prop, elem in ELEMENT_DMG_PROP_TO_ELEMENT.items():
                    if str(sub).startswith(prop + '+'):
                        warnings.append(f"{label}: weak detection '{elem}' from substat.")
                        return f'{base}{elem}'
    warnings.append(f"{label}: defaulting to '{traveler_default}'.")
    return f'{base}{traveler_default}'


def to_gcsim_name(csv_name: str, row: pd.Series, warnings: list,
                  traveler_override: dict, traveler_default: str) -> str | None:
    label = str(csv_name).strip()
    norm = _normalize(label)
    if norm in ('aether', 'lumine'):
        return _resolve_traveler(label, row, warnings, traveler_override, traveler_default)
    if norm in CHARACTER_NAME_OVERRIDES:
        return CHARACTER_NAME_OVERRIDES[norm]
    if norm in GCSIM_CHARACTER_KEYS:
        return norm
    warnings.append(f"SKIPPED character '{label}': not in gcsim.")
    return None


# ── Artifact stat accumulator ─────────────────────────────────────────────

def _accumulate_artifact_stats(row: pd.Series, char_label: str, warnings: list) -> dict:
    totals: dict = {}
    unknown_types: set = set()

    def add(prop_type, raw_value):
        if prop_type not in FIGHT_PROP_TO_GCSIM:
            unknown_types.add(prop_type)
            return
        key, is_percent = FIGHT_PROP_TO_GCSIM[prop_type]
        v = raw_value / 100.0 if is_percent else raw_value
        totals[key] = totals.get(key, 0.0) + v

    for i in range(1, 6):
        main_type = row.get(f'Artifact {i} Main Stat Type')
        main_val = row.get(f'Artifact {i} Main Stat Value')
        if pd.notna(main_type) and pd.notna(main_val):
            # ✅ Skip empty strings
            if str(main_val).strip() != "":
                add(str(main_type), float(main_val))
        for j in range(1, 5):
            sub = row.get(f'Artifact {i} Sub {j}')
            if pd.notna(sub):
                m = SUBSTAT_RE.match(str(sub).strip())
                if m:
                    add(m.group(1), float(m.group(2)))
                else:
                    unknown_types.add(f"unparsable {sub!r}")

    if unknown_types:
        warnings.append(f"{char_label}: ignored unrecognized stat entries {sorted(unknown_types)}")
    return totals

# ── Main public function ──────────────────────────────────────────────────

def build_character_configs(
    df: pd.DataFrame,
    min_character_level: int = 50,
    traveler_override: dict | None = None,
    traveler_default: str = "anemo",
    start_energy: int = 100,
) -> tuple[dict, list, list]:
    """
    Build GCSim character configs from a DataFrame.

    Returns:
        configs          – dict mapping gcsim_name → config string
        skipped          – list of character names that couldn't be mapped
        warnings         – list of warning strings
    """
    if traveler_override is None:
        traveler_override = {}

    df = df[df['Character Level'] >= min_character_level].copy()
    configs: dict = {}
    skipped: list = []
    warnings: list = []

    for _, row in df.iterrows():
        csv_name = row['Character Name']
        gcsim_name = to_gcsim_name(
            csv_name, row, warnings, traveler_override, traveler_default
        )
        if gcsim_name is None:
            skipped.append(str(csv_name))
            continue

        char_label = f"{csv_name} → {gcsim_name}"
        level = int(row['Character Level'])
        cons = int(row.get('Character Constellations', 0) or 0)

        na_raw    = int(row.get('Talent NA Level', 1)    or 1)
        skill_raw = int(row.get('Talent Skill Level', 1) or 1)
        burst_raw = int(row.get('Talent Burst Level', 1) or 1)

        na, skill, burst = na_raw, skill_raw, burst_raw
        if cons >= 3 and skill > 10:
            skill = max(1, skill - 3)
        if cons >= 5 and burst > 10:
            burst = max(1, burst - 3)
        na    = max(1, min(10, na))
        skill = max(1, min(10, skill))
        burst = max(1, min(10, burst))

        lines = [
            f"{gcsim_name} char lvl={level}/90 cons={cons} "
            f"talent={na},{skill},{burst} +params=[start_energy={start_energy}];"
        ]

        # Weapon
        weapon_name = row.get('Weapon Name')
        if pd.notna(weapon_name):
            norm_w = _normalize(weapon_name)
            if norm_w in GCSIM_WEAPON_KEYS:
                wlvl   = int(row.get('Weapon Level', 90) or 90)
                refine = int(row.get('Weapon Refinement', 1) or 1)
                lines.append(
                    f'{gcsim_name} add weapon="{norm_w}" refine={refine} lvl={wlvl}/90;'
                )
            else:
                warnings.append(f"{char_label}: weapon '{weapon_name}' not recognized.")

        # Artifact sets
        set_counts: dict = {}
        for i in range(1, 6):
            set_name = row.get(f'Artifact {i} Set')
            if pd.notna(set_name):
                set_counts[set_name] = set_counts.get(set_name, 0) + 1
        for set_name, count in set_counts.items():
            if count < 2:
                continue
            norm_s = _normalize(set_name)
            if norm_s in GCSIM_SET_KEYS:
                lines.append(f'{gcsim_name} add set="{norm_s}" count={count};')
            else:
                warnings.append(f"{char_label}: set '{set_name}' not recognized.")

        # Artifact stats
        stat_totals = _accumulate_artifact_stats(row, char_label, warnings)
        if stat_totals:
            stat_parts = [f'{k}={v:.4f}' for k, v in sorted(stat_totals.items())]
            lines.append(f'{gcsim_name} add stats {" ".join(stat_parts)};')

        if gcsim_name in configs:
            warnings.append(f"'{csv_name}' overwrote existing entry for '{gcsim_name}'.")
        configs[gcsim_name] = '\n'.join(lines)

    return configs, skipped, warnings