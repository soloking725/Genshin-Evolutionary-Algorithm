"""
character_icons.py
Hardcoded mapping of every playable character's English display name
to their OFFICIAL Enka Network CDN icon key, sourced directly from:
  https://github.com/EnkaNetwork/API-docs/blob/master/store/characters.json

URL pattern:
  https://enka.network/ui/UI_AvatarIcon_{key}.png
  https://enka.network/ui/UI_AvatarIcon_{key}_Circle.png

IMPORTANT — many keys are NOT obvious from the English name:
  Heizou     → Heizo      (no 'u')
  Noelle     → Noel       (no 'le')
  Yae Miko   → Yae        (not Yaemiko)
  Skirk      → SkirkNew
  Lynette    → Linette
  Lyney      → Liney
  Amber      → Ambor
  Jean       → Qin
  Thoma      → Tohma
  Yanfei     → Feiyan
  Raiden     → Shougun
  Baizhu     → Baizhuer
  Xianyun    → Liuyun
  Ororon     → Olorun
  Kirara     → Momoka     (internal/dev name)
"""

ENKA_CDN = "https://enka.network/ui"

# All keys verified against official EnkaNetwork/API-docs/store/characters.json
ICON_MAP: dict[str, str] = {
    # ── A ─────────────────────────────────────────────────────────────────
    "Aino":                "Aino",
    "Albedo":              "Albedo",
    "Alhaitham":           "Alhatham",
    "Al-Haitham":          "Alhatham",
    "Aloy":                "Aloy",
    "Amber":               "Ambor",
    "Arlecchino":          "Arlecchino",
    "Arataki Itto":        "Itto",
    "Itto":                "Itto",
    # ── B ─────────────────────────────────────────────────────────────────
    "Baizhu":              "Baizhuer",
    "Barbara":             "Barbara",
    "Beidou":              "Beidou",
    "Bennett":             "Bennett",
    # ── C ─────────────────────────────────────────────────────────────────
    "Candace":             "Candace",
    "Charlotte":           "Charlotte",
    "Chasca":              "Chasca",
    "Chevreuse":           "Chevreuse",
    "Chiori":              "Chiori",
    "Chongyun":            "Chongyun",
    "Citlali":             "Citlali",
    "Clorinde":            "Clorinde",
    "Collei":              "Collei",
    "Columbina":           "Columbina",
    "Cyno":                "Cyno",
    # ── D ─────────────────────────────────────────────────────────────────
    "Dahlia":              "Dahlia",
    "Dehya":               "Dehya",
    "Diluc":               "Diluc",
    "Diona":               "Diona",
    "Dori":                "Dori",
    "Durin":               "Durin",
    # ── E ─────────────────────────────────────────────────────────────────
    "Emilie":              "Emilie",
    "Escoffier":           "Escoffier",
    "Eula":                "Eula",
    # ── F ─────────────────────────────────────────────────────────────────
    "Faruzan":             "Faruzan",
    "Fischl":              "Fischl",
    "Flins":               "Flins",
    "Freminet":            "Freminet",
    "Furina":              "Furina",
    # ── G ─────────────────────────────────────────────────────────────────
    "Gaming":              "Gaming",
    "Ganyu":               "Ganyu",
    "Gorou":               "Gorou",
    # ── H ─────────────────────────────────────────────────────────────────
    "Hu Tao":              "Hutao",
    "HuTao":               "Hutao",
    # ── I ─────────────────────────────────────────────────────────────────
    "Iansan":              "Iansan",
    "Ifa":                 "Ifa",
    "Ineffa":              "Ineffa",
    # ── J ─────────────────────────────────────────────────────────────────
    "Jahoda":              "Jahoda",
    "Jean":                "Qin",              # internal name is Qin
    # ── K ─────────────────────────────────────────────────────────────────
    "Kachina":             "Kachina",
    "Kaeya":               "Kaeya",
    "Kaedehara Kazuha":    "Kazuha",
    "Kamisato Ayaka":      "Ayaka",
    "Ayaka":               "Ayaka",
    "Kamisato Ayato":      "Ayato",
    "Ayato":               "Ayato",
    "Kaveh":               "Kaveh",
    "Kazuha":              "Kazuha",
    "Keqing":              "Keqing",
    "Kinich":              "Kinich",
    "Kirara":              "Momoka",           # internal name is Momoka
    "Klee":                "Klee",
    "Sangonomiya Kokomi":  "Kokomi",
    "Kokomi":              "Kokomi",
    "Kujou Sara":          "Sara",
    "Sara":                "Sara",
    "Kuki Shinobu":        "Shinobu",
    "Shinobu":             "Shinobu",
    # ── L ─────────────────────────────────────────────────────────────────
    "Lanyan":              "Lanyan",
    "Lauma":               "Lauma",
    "Layla":               "Layla",
    "Lisa":                "Lisa",
    "Lynette":             "Linette",          # internal name is Linette
    "Linette":             "Linette",
    "Lyney":               "Liney",            # internal name is Liney
    "Liney":               "Liney",
    # ── M ─────────────────────────────────────────────────────────────────
    "Mavuika":             "Mavuika",
    "Mika":                "Mika",
    "Mizuki":              "Mizuki",
    "Mona":                "Mona",
    "Mualani":             "Mualani",
    # ── N ─────────────────────────────────────────────────────────────────
    "Nahida":              "Nahida",
    "Navia":               "Navia",
    "Nefer":               "Nefer",            # new character
    "Neuvillette":         "Neuvillette",
    "Nilou":               "Nilou",
    "Ningguang":           "Ningguang",
    "Noelle":              "Noel",             # internal name is Noel (no le)
    "Noel":                "Noel",
    "Nicole":              "Noel",             # common autocorrect of Noelle
    # ── O ─────────────────────────────────────────────────────────────────
    "Ororon":              "Olorun",           # internal name is Olorun
    "Olorun":              "Olorun",
    # ── Q ─────────────────────────────────────────────────────────────────
    "Qiqi":                "Qiqi",
    # ── R ─────────────────────────────────────────────────────────────────
    "Raiden Shogun":       "Shougun",
    "Razor":               "Razor",
    "Rosaria":             "Rosaria",
    # ── S ─────────────────────────────────────────────────────────────────
    "Sayu":                "Sayu",
    "Sethos":              "Sethos",
    "Shenhe":              "Shenhe",
    "Shikanoin Heizou":    "Heizo",            # Heizo, NOT Heizou
    "Heizou":              "Heizo",
    "Heizo":               "Heizo",
    "Sigewinne":           "Sigewinne",
    "Skirk":               "SkirkNew",         # internal name is SkirkNew
    "Sucrose":             "Sucrose",
    # ── T ─────────────────────────────────────────────────────────────────
    "Tartaglia":           "Tartaglia",
    "Childe":              "Tartaglia",
    "Thoma":               "Tohma",            # internal name is Tohma
    "Tohma":               "Tohma",
    "Tighnari":            "Tighnari",
    # ── V ─────────────────────────────────────────────────────────────────
    "Varesa":              "Varesa",
    "Venti":               "Venti",
    # ── W ─────────────────────────────────────────────────────────────────
    "Wanderer":            "Wanderer",
    "Scaramouche":         "Wanderer",
    "Wriothesley":         "Wriothesley",
    # ── X ─────────────────────────────────────────────────────────────────
    "Xiangling":           "Xiangling",
    "Xianyun":             "Liuyun",           # internal name is Liuyun
    "Liuyun":              "Liuyun",
    "Xiao":                "Xiao",
    "Xilonen":             "Xilonen",
    "Xingqiu":             "Xingqiu",
    "Xinyan":              "Xinyan",
    # ── Y ─────────────────────────────────────────────────────────────────
    "Yae Miko":            "Yae",              # internal name is Yae (not Yaemiko)
    "Yaemiko":             "Yae",
    "Yanfei":              "Feiyan",           # Chinese: 费延 reversed
    "Yaoyao":              "Yaoyao",
    "Yelan":               "Yelan",
    "Yoimiya":             "Yoimiya",
    "Yun Jin":             "Yunjin",
    "Yunjin":              "Yunjin",
    # ── Z ─────────────────────────────────────────────────────────────────
    "Zhongli":             "Zhongli",
    # ── Traveler ──────────────────────────────────────────────────────────
    "Aether":              "PlayerBoy",
    "Lumine":              "PlayerGirl",
    "Traveler":            "PlayerBoy",
}


def get_icon_url(display_name: str, circle: bool = True) -> str:
    """
    Return the Enka CDN URL for a character's icon.
    Tries multiple name variations so the library's various display name
    formats all resolve correctly.
    Returns "" only if no match is found.
    """
    suffix = "_Circle" if circle else ""

    def make_url(key: str) -> str:
        return f"{ENKA_CDN}/UI_AvatarIcon_{key}{suffix}.png"

    # 1. Exact match
    key = ICON_MAP.get(display_name, "")
    if key:
        return make_url(key)

    # 2. Last word only ("Kamisato Ayaka" → "Ayaka", "Shikanoin Heizou" → "Heizou")
    parts = display_name.split()
    if len(parts) > 1:
        key = ICON_MAP.get(parts[-1], "")
        if key:
            return make_url(key)

    # 3. First word only ("Hu Tao" → "Hu")
    if len(parts) > 1:
        key = ICON_MAP.get(parts[0], "")
        if key:
            return make_url(key)

    # 4. All words joined ("Yun Jin" → "Yunjin")
    joined = "".join(parts)
    key = ICON_MAP.get(joined, "")
    if key:
        return make_url(key)

    # 5. Best-effort: use the name as-is (catches single-name chars not in map)
    if joined.isalpha() and len(joined) >= 3:
        return make_url(joined)

    return ""