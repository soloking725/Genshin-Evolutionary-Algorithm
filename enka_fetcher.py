"""
enka_fetcher.py
Fetches character data from Enka Network and converts it to a pandas DataFrame.
No account credentials are needed — Enka Network only reads data from public
Genshin Impact showcases (characters the player has opted to display).
"""
import asyncio
import os
import ssl
from collections import Counter

import pandas as pd

# On Mac, Python doesn't use the system certificate store by default.
# Point aiohttp (used by the enka library) at certifi's bundle instead.
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE",      certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

try:
    from character_icons import get_icon_url as _get_icon_url
except ImportError:
    def _get_icon_url(name: str, circle: bool = True) -> str:
        return ""


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def fetch_characters(uid: int) -> tuple[pd.DataFrame, dict]:
    """
    Fetch the public showcase for *uid* and return
    (DataFrame matching genshin_data_export.csv schema, player_info dict).

    Raises on network / UID errors.
    """
    return asyncio.run(_async_fetch(uid))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _get_constellation_count(character) -> int:
    if hasattr(character, "constellations") and character.constellations:
        try:
            if hasattr(character.constellations[0], "activated"):
                return sum(1 for c in character.constellations if c.activated)
            elif hasattr(character.constellations[0], "unlocked"):
                return sum(1 for c in character.constellations if c.unlocked)
        except Exception:
            pass
    if hasattr(character, "constellations_unlocked"):
        try:
            return int(character.constellations_unlocked)
        except Exception:
            pass
    return 0


def _artifact_set_bonus(names: list) -> str:
    sets = [n for n in names if n]
    if not sets:
        return "None"
    counter = Counter(sets)
    bonuses = []
    for set_name, count in counter.items():
        if count >= 4:
            bonuses.append(f"{set_name} x4")
        elif count >= 2:
            bonuses.append(f"{set_name} x2")
    return " + ".join(bonuses) if bonuses else "None"


async def _async_fetch(uid: int) -> tuple[pd.DataFrame, dict]:
    import enka

    # Fight-prop → column name mapping
    STAT_MAP = {
        enka.gi.FightPropType.FIGHT_PROP_HP:               "HP",
        enka.gi.FightPropType.FIGHT_PROP_ATTACK:           "ATK",
        enka.gi.FightPropType.FIGHT_PROP_DEFENSE:          "DEF",
        enka.gi.FightPropType.FIGHT_PROP_CRITICAL:         "Crit Rate",
        enka.gi.FightPropType.FIGHT_PROP_CRITICAL_HURT:    "Crit DMG",
        enka.gi.FightPropType.FIGHT_PROP_CHARGE_EFFICIENCY:"Energy Recharge",
        enka.gi.FightPropType.FIGHT_PROP_ELEMENT_MASTERY:  "Elemental Mastery",
        enka.gi.FightPropType.FIGHT_PROP_HEAL_ADD:         "Healing Bonus",
        enka.gi.FightPropType.FIGHT_PROP_PHYSICAL_ADD_HURT:"Physical DMG Bonus",
        enka.gi.FightPropType.FIGHT_PROP_FIRE_ADD_HURT:    "Pyro DMG Bonus",
        enka.gi.FightPropType.FIGHT_PROP_WATER_ADD_HURT:   "Hydro DMG Bonus",
        enka.gi.FightPropType.FIGHT_PROP_WIND_ADD_HURT:    "Anemo DMG Bonus",
        enka.gi.FightPropType.FIGHT_PROP_ICE_ADD_HURT:     "Cryo DMG Bonus",
        enka.gi.FightPropType.FIGHT_PROP_ELEC_ADD_HURT:    "Electro DMG Bonus",
        enka.gi.FightPropType.FIGHT_PROP_GRASS_ADD_HURT:   "Dendro DMG Bonus",
    }
    FINAL_STAT_KEYS = {
        enka.gi.FightPropType.FIGHT_PROP_HP:      2000,
        enka.gi.FightPropType.FIGHT_PROP_ATTACK:  2001,
        enka.gi.FightPropType.FIGHT_PROP_DEFENSE: 2002,
    }

    # ✅ Header includes "Icon URL"
    header = [
        "UID", "Player Nickname", "Player Level", "Player Signature",
        "Character Name", "Character Level", "Character Ascension",
        "Character Friendship", "Character Constellations",
        "Weapon Name", "Weapon Level", "Weapon Ascension",
        "Weapon Refinement", "Weapon Stars",
        "Talent NA Level", "Talent Skill Level", "Talent Burst Level",
        *STAT_MAP.values(),
        "Icon URL",          # <-- This column will store the image URL
        "Artifact Set Bonus",
    ]
    for i in range(1, 6):
        header.extend([
            f"Artifact {i} Set", f"Artifact {i} Name",
            f"Artifact {i} Main Stat Type", f"Artifact {i} Main Stat Value",
            f"Artifact {i} Sub 1", f"Artifact {i} Sub 2",
            f"Artifact {i} Sub 3", f"Artifact {i} Sub 4",
        ])

    async with enka.GenshinClient(enka.gi.Language.ENGLISH) as client:
        # update_assets() is REQUIRED — the library cannot map character IDs to
        # names or stats without it. Retry once on failure before giving up.
        import asyncio as _asyncio
        try:
            await client.update_assets()
        except Exception as _e1:
            try:
                await _asyncio.sleep(1)
                await client.update_assets()
            except Exception as _e2:
                raise RuntimeError(
                    f"Could not load Enka asset data: {_e2}. "
                    "Check your internet connection. "
                    "On Mac this is often an SSL certificate issue — "
                    "try running: pip install certifi"
                ) from _e2
        response = await client.fetch_showcase(uid)

        player_info = {
            "nickname": response.player.nickname,
            "level": response.player.level,
            "signature": response.player.signature,
            "uid": uid,
        }

        rows = []
        for character in response.characters:
            char_name = character.name
            weapon = character.weapon
            talents = character.talents

            # ── Get the icon URL ─────────────────────────────────────────
            # Primary: hardcoded mapping (instant, no network, works everywhere)
            # Fallback: enka library's Icon object (requires update_assets())
            icon_url = _get_icon_url(char_name, circle=True)
            if not icon_url:
                # fallback: try the enka Icon object after update_assets()
                try:
                    icon = character.icon
                    for candidate in (icon.circle, icon.front, icon.side):
                        if candidate and "UI_" in candidate:
                            icon_url = candidate
                            break
                except Exception:
                    pass

            # ── Build the row ─────────────────────────────────────────────
            row = [
                str(uid),
                response.player.nickname,
                response.player.level,
                response.player.signature,
                char_name,
                character.level,
                character.ascension,
                character.friendship_level,
                _get_constellation_count(character),
                weapon.name if weapon else "",
                weapon.level if weapon else "",
                weapon.ascension if weapon else "",
                weapon.refinement if weapon else "",
                weapon.rarity if weapon else "",
                talents[0].level if len(talents) > 0 else "",
                talents[1].level if len(talents) > 1 else "",
                talents[2].level if len(talents) > 2 else "",
            ]

            # Stats
            for prop_type in STAT_MAP.keys():
                if prop_type in FINAL_STAT_KEYS:
                    special_key = FINAL_STAT_KEYS[prop_type]
                    stat_obj = character.stats.get(special_key)
                    if stat_obj:
                        val = stat_obj.value
                    else:
                        stat_obj = character.stats.get(prop_type)
                        val = stat_obj.value if stat_obj else 0.0
                    row.append(str(val))
                else:
                    stat_obj = character.stats.get(prop_type)
                    row.append(stat_obj.formatted_value if stat_obj else "")

            # Artifacts
            artifacts = list(character.artifacts) + [None] * (5 - len(character.artifacts))
            artifact_set_names = []
            artifact_details = []
            for artifact in artifacts:
                if artifact:
                    subs = []
                    for sub in artifact.sub_stats[:4]:
                        subs.append(f"{sub.type.name}+{sub.value}")
                    subs += [""] * (4 - len(subs))
                    artifact_set_names.append(artifact.set_name)
                    artifact_details.append([
                        artifact.set_name, artifact.name,
                        artifact.main_stat.type.name, artifact.main_stat.value,
                        *subs,
                    ])
                else:
                    artifact_set_names.append("")
                    artifact_details.append(["", "", "", "", "", "", "", ""])

            # ✅ Append Icon URL and Set Bonus (in correct order)
            row.append(icon_url)
            row.append(_artifact_set_bonus(artifact_set_names))

            # Append artifact details
            for details in artifact_details:
                row.extend(details)

            # Pad / trim to header length
            row = (row + [""] * len(header))[:len(header)]
            rows.append(row)

    df = pd.DataFrame(rows, columns=header)
    return df, player_info