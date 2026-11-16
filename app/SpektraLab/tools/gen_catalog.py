#!/usr/bin/env python3
"""gen_catalog.py -- write Resources/StockCatalog.json from the engine's profiles.

    app/SpektraLab/tools/gen_catalog.py

The desktop's `Tools/gen-catalog.py`, with two differences:

  * **The names are this script's** (`NAMES`): each stock's name, the desktop's (the
    profiles' `info.name`), and a short name for the cards, the maker dropped. A
    profile with no row fails this script instead of shipping without a name.
  * **A swatch per stock**, for the film cards, the paper cards and the library's
    stock dot. The five films and five papers drawn in `design/` keep the
    drawing's colours; the rest are this script's, chosen in the same key.

The order is the picker's: the drawing's first, then by family.

**The product's own profiles** (`engine/resources_product/profiles`, black and
white; `tools/build_engine_mac.sh` lays them into the app's engine resources beside
spektrafilm's) are listed with the rest since 2026-10-09, under the same rule: a
profile with no row in `NAMES` fails this script. What they carry that
the others do not, each absent on a colour stock so that no row of the 28 moved:

  * `monochrome`: the profile's `channel_model` is `bw`, a film with one silver
    emulsion or a silver paper. A silver film prints on a silver paper and a
    colour film on a colour one (`Model/Stock.swift`).
  * `grain`, a film's: what the Grain strength's 1 is on it, the `grain_amount`
    at which the engine renders the granularity its maker publishes (`OWN_GRAIN`,
    `COLOUR_GRAIN`; a colour film with no comparable figure, its speed's).
  * `neutralPack`, a paper's: the enlarger's C, M, Y for it, which the host has
    to send because the engine's own table has no row for a silver paper. Read
    from the paper's grade table, Multigrade filter 2.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
PROFILES = REPO / "engine/resources/profiles"
PRODUCT_PROFILES = REPO / "engine/resources_product/profiles"
OUT = HERE / "Resources/StockCatalog.json"

# id -> (name, short name, kind). The name is the desktop's; the short name drops the maker.
NAMES = {
    "kodak_portra_400": ("Kodak Portra 400", "Portra 400", "colour negative"),
    "kodak_gold_200": ("Kodak Gold 200", "Gold 200", "colour negative"),
    "kodak_ektar_100": ("Kodak Ektar 100", "Ektar 100", "colour negative"),
    "kodak_vision3_500t": ("Kodak Vision3 500T", "Vision3 500T", "cine negative"),
    "cinestill_800t": ("CineStill 800T", "800T", "colour negative"),
    "fujifilm_pro_400h": ("Fujifilm Pro 400H", "Pro 400H", "colour negative"),
    "kodak_portra_160": ("Kodak Portra 160", "Portra 160", "colour negative"),
    "kodak_portra_800": ("Kodak Portra 800", "Portra 800", "colour negative"),
    "kodak_portra_800_push1": ("Kodak Portra 800 (Push 1)", "Portra 800 +1", "colour negative"),
    "kodak_portra_800_push2": ("Kodak Portra 800 (Push 2)", "Portra 800 +2", "colour negative"),
    "kodak_ultramax_400": ("Kodak Ultramax 400", "Ultramax 400", "colour negative"),
    "fujifilm_c200": ("Fujifilm C200", "C200", "colour negative"),
    "fujifilm_xtra_400": ("Fujifilm X-Tra 400", "X-Tra 400", "colour negative"),
    "kodak_ektachrome_100": ("Kodak Ektachrome 100", "Ektachrome 100", "slide (positive)"),
    "kodak_kodachrome_64": ("Kodak Kodachrome 64", "Kodachrome 64", "slide (positive)"),
    "fujifilm_provia_100f": ("Fujifilm Provia 100F", "Provia 100F", "slide (positive)"),
    "fujifilm_velvia_100": ("Fujifilm Velvia 100", "Velvia 100", "slide (positive)"),
    "kodak_vision3_50d": ("Kodak Vision3 50D", "Vision3 50D", "cine negative"),
    "kodak_vision3_200t": ("Kodak Vision3 200T", "Vision3 200T", "cine negative"),
    "kodak_vision3_250d": ("Kodak Vision3 250D", "Vision3 250D", "cine negative"),
    "kodak_verita_200d": ("Kodak Verita 200D", "Verita 200D", "cine negative"),
    "kodak_tri_x_400": ("Kodak Tri-X 400", "Tri-X 400", "b&w negative"),
    "kodak_tmax_100": ("Kodak T-Max 100", "T-Max 100", "b&w negative"),
    "fujifilm_neopan_acros_100_ii": ("Fujifilm Neopan 100 Acros II", "Acros 100 II", "b&w negative"),
    "ilford_hp5_plus_400": ("Ilford HP5 Plus 400", "HP5 Plus 400", "b&w negative"),
    "kodak_portra_endura": ("Kodak Professional Portra Endura", "Portra Endura", "colour paper"),
    "kodak_supra_endura": ("Kodak Professional Supra Endura", "Supra Endura", "colour paper"),
    "kodak_ultra_endura": ("Kodak Professional Ultra Endura", "Ultra Endura", "colour paper"),
    "fujifilm_crystal_archive_typeii": ("Fujifilm Crystal Archive Type II", "Crystal Archive II", "colour paper"),
    "kodak_2383": ("Kodak Vision 2383", "Vision 2383", "cine print film"),
    "kodak_endura_premier": ("Kodak Professional Endura Premier", "Endura Premier", "colour paper"),
    "kodak_ektacolor_edge": ("Kodak Ektacolor Edge", "Ektacolor Edge", "colour paper"),
    "kodak_2393": ("Kodak Vision Premier 2393", "Vision Premier 2393", "cine print film"),
    "ilford_multigrade_iv_rc": ("Ilford Multigrade IV RC", "Multigrade IV RC", "b&w paper"),
}
# What a profile's `info` does not say. CineStill 800T is Vision3 500T's emulsion with its
# remjet off, declared a still colour negative printed on 2383 (the desktop's catalogue).
INFO = {
    "cinestill_800t": {"stage": "filming", "type": "negative", "target_print": "kodak_2383"},
}

# design/src/gen.py (film cards, STOCK_DOT) and gen_flow.py (PAPERS) name these.
DRAWN = {
    "kodak_portra_400": "#d8a27a", "kodak_gold_200": "#e0b54a", "kodak_ektar_100": "#c4503f",
    "kodak_vision3_500t": "#46637f", "fujifilm_pro_400h": "#7fa38c",
    "fujifilm_provia_100f": "#5d8fd8", "kodak_kodachrome_64": "#c9a13c",
    "kodak_portra_endura": "#f3ede3", "kodak_supra_endura": "#f1ece4", "kodak_ultra_endura": "#f4efe6",
    "fujifilm_crystal_archive_typeii": "#eef0ee", "kodak_2383": "#151312",
}
# Not drawn: chosen beside the drawn ones, one hue per family.
CHOSEN = {
    "kodak_portra_160": "#e3b997", "kodak_portra_800": "#c98c62",
    "kodak_portra_800_push1": "#b97a52", "kodak_portra_800_push2": "#a66944",
    "kodak_ultramax_400": "#d98a3d", "kodak_ektachrome_100": "#4f7fc0",
    "kodak_vision3_50d": "#6d8fa3", "kodak_vision3_200t": "#57799a", "kodak_vision3_250d": "#5f8a92",
    "kodak_verita_200d": "#7a6c9c", "cinestill_800t": "#5b5f86",
    "fujifilm_c200": "#6fae7a", "fujifilm_xtra_400": "#5c9a69", "fujifilm_velvia_100": "#b4558a",
    "kodak_endura_premier": "#f2ede5", "kodak_ektacolor_edge": "#f0ece6", "kodak_2393": "#181513",
}
ORDER = [
    # camera films: the drawing's five, then the families
    "kodak_portra_400", "kodak_gold_200", "kodak_ektar_100", "kodak_vision3_500t", "cinestill_800t", "fujifilm_pro_400h",
    "kodak_portra_160", "kodak_portra_800", "kodak_portra_800_push1", "kodak_portra_800_push2",
    "kodak_ultramax_400", "fujifilm_c200", "fujifilm_xtra_400",
    "kodak_ektachrome_100", "kodak_kodachrome_64", "fujifilm_provia_100f", "fujifilm_velvia_100",
    "kodak_vision3_50d", "kodak_vision3_200t", "kodak_vision3_250d", "kodak_verita_200d",
    # print stocks: the drawing's five, then the rest
    "kodak_portra_endura", "kodak_supra_endura", "kodak_ultra_endura", "fujifilm_crystal_archive_typeii",
    "kodak_2383", "kodak_endura_premier", "kodak_ektacolor_edge", "kodak_2393",
]
# The product's own stocks: the black-and-white films after every colour film,
# their paper after every colour one, so no card that was there has moved.
ORDER[ORDER.index("kodak_portra_endura"):ORDER.index("kodak_portra_endura")] = [
    "kodak_tri_x_400", "kodak_tmax_100", "fujifilm_neopan_acros_100_ii", "ilford_hp5_plus_400"]
ORDER.append("ilford_multigrade_iv_rc")
# One family, so one hue: none. Four greys apart enough to tell on a card and
# as a library dot; the paper's base a neutral white beside the colour papers' creams.
CHOSEN.update({
    "kodak_tri_x_400": "#8c8a87", "kodak_tmax_100": "#a9a8a6", "fujifilm_neopan_acros_100_ii": "#c1c3c5",
    "ilford_hp5_plus_400": "#73716e", "ilford_multigrade_iv_rc": "#f1f1ef",
})
# What the Grain strength's 1 is on a black-and-white film: the desktop app's
# `FilmParams.ownGrain` (its 0bca29da), measured there on engine renders with
# the grain as one layer against each maker's published RMS granularity. The
# wire stops at 2, so Tri-X's ruler is at its end from 1.18 and HP5's from 1.34.
OWN_GRAIN = {"kodak_tri_x_400": 1.70, "ilford_hp5_plus_400": 1.49, "kodak_tmax_100": 0.74,
             "fujifilm_neopan_acros_100_ii": 0.64}
# What the Grain strength's 1 is on a colour film (2026-11-11, the owner: "each colour film, negative and
# positive, has its own default grain"): the `grain_amount` at which the engine renders the film's granularity,
# with the sub-layers on (the app's default), at 6 µm pixels. Two sources, never mixed in one row:
# - SHEET: the maker's diffuse RMS granularity (48 µm, D 1.0) over what the engine renders at 1, measured
#   2026-10-07 (research/colour-film-granularity.md §4, commit ccbfadde). Slides on the visual figure;
#   Vision3 and Verita on the green record of their H-1 sheets' curves.
# - ISO: no comparable figure is published. Kodak's still negatives carry only Print Grain Index, which Kodak
#   says cannot be compared with RMS (E-58); Fujifilm's negative "4" is footnoted as not comparable with its
#   reversal scale. Searched again 2026-11-11 (Kodak and Fujifilm sheets, JP editions, pre-1996 predecessors):
#   nothing. So the target is the green record a Vision3 stock of that speed has, fitted on the four Vision3
#   sheets, G = 4.498 × (ISO/50)^0.212, over what the engine renders in green at 1.
# The pushed Portra 800 profiles take Portra 800's: the push is already in their profiles, which render grainier.
COLOUR_GRAIN = {
    # SHEET
    "kodak_kodachrome_64": 1.15, "fujifilm_provia_100f": 0.96, "fujifilm_velvia_100": 0.99,
    "kodak_ektachrome_100": 0.88, "kodak_vision3_500t": 1.01, "kodak_vision3_200t": 1.01,
    "kodak_vision3_250d": 0.83, "kodak_vision3_50d": 0.69, "kodak_verita_200d": 1.06,
    # CineStill 800T is Vision3 500T's emulsion (its profile is an alias of 500T's data) and publishes no sheet.
    "cinestill_800t": 1.01,
    # ISO
    "kodak_portra_160": 0.92, "kodak_portra_400": 1.06, "kodak_portra_800": 1.23,
    "kodak_portra_800_push1": 1.23, "kodak_portra_800_push2": 1.23,
    "kodak_ektar_100": 0.79, "kodak_gold_200": 0.97, "kodak_ultramax_400": 1.09,
    "fujifilm_c200": 0.70, "fujifilm_xtra_400": 0.74, "fujifilm_pro_400h": 1.20,
}
# --- The filmcolors.org / KODAK E-55 data-sheet stocks (2026-11-15) ----------
# Built with spektrafilm_profile_builder from published data sheets in the
# Toni-Chan/spektrafilm draft PRs #6-#12 (KODACHROME E-55, FUJIFILM reversal and
# negative, KODAK negative and reversal, FUJIFILM and KODAK motion picture).
# The name is the profile's (codes in parentheses, so the edge print stops
# before them); the short name drops the maker and the code.
#
# FILMCOLORS_GRAIN: ESTIMATE placeholders, not measured. None of these stocks
# has had its engine granularity measured against a sheet (COLOUR_GRAIN's
# SHEET rule), so each takes the ISO rule's shape fitted on this script's own
# ISO rows (the six Kodak still negatives: 0.82 x (ISO/100)^0.200, the same
# exponent as the Vision3 fit above), times 1.2 for a slide (the existing slides'
# SHEET rows sit about that far above the fit), and Kodachrome scaled from
# Kodachrome 64's SHEET 1.15 by the same exponent. EIR takes ISO 200 (its usual
# EI behind a #12 filter); MS 100/1000 its EI 100.
FILMCOLORS = [
    ('kodak_ultra_color_100uc_e4035', 'Kodak Ultra Color 100UC (E-4035, 2007)', 'Ultra Color 100UC', 'colour negative', '#cf6a45', 0.82),
    ('kodak_ultra_color_400uc_e4035', 'Kodak Ultra Color 400UC (E-4035, 2007)', 'Ultra Color 400UC', 'colour negative', '#c25d3c', 1.08),
    ('kodak_supra_100_e2519', 'Kodak Supra 100 (E-2519, 2003)', 'Supra 100', 'colour negative', '#e6c3a2', 0.82),
    ('kodak_supra_200_e4029', 'Kodak Supra 200 (E-4029, 2003)', 'Supra 200', 'colour negative', '#dcb592', 0.94),
    ('kodak_supra_400_e2519', 'Kodak Supra 400 (E-2519, 2003)', 'Supra 400', 'colour negative', '#d2a782', 1.08),
    ('kodak_supra_800_e2519', 'Kodak Supra 800 (E-2519, 2003)', 'Supra 800', 'colour negative', '#c79973', 1.24),
    ('kodak_royal_supra_200_e4026', 'Kodak Royal Supra 200 (E-4026, 2002)', 'Royal Supra 200', 'colour negative', '#d9a35f', 0.94),
    ('kodak_royal_supra_400_e4026', 'Kodak Royal Supra 400 (E-4026, 2002)', 'Royal Supra 400', 'colour negative', '#cd9552', 1.08),
    ('kodak_royal_supra_800_e4026', 'Kodak Royal Supra 800 (E-4026, 2002)', 'Royal Supra 800', 'colour negative', '#c08746', 1.24),
    ('kodak_profoto_100_e2e', 'Kodak Profoto 100 (E-2E, 1997)', 'Profoto 100', 'colour negative', '#e0a988', 0.82),
    ('kodak_le100_le1', 'Kodak Law Enforcement LE100 (LE-1, 1998)', 'LE100', 'colour negative', '#b8a48c', 0.82),
    ('kodak_le400_le1', 'Kodak Law Enforcement LE400 (LE-1, 1998)', 'LE400', 'colour negative', '#ab967d', 1.08),
    ('kodak_le800_le1', 'Kodak Law Enforcement LE800 (LE-1, 1998)', 'LE800', 'colour negative', '#9e886f', 1.24),
    ('fujifilm_pro_160ns_af30232e', 'Fujifilm Pro 160NS (AF3-0232E)', 'Pro 160NS', 'colour negative', '#8fb79a', 0.9),
    ('fujifilm_nps_160_af3809e', 'Fujifilm NPS 160 (AF3-809E)', 'NPS 160', 'colour negative', '#84ad8f', 0.9),
    ('fujifilm_npc_160_af3065e', 'Fujifilm NPC 160 (AF3-065E)', 'NPC 160', 'colour negative', '#6fa37f', 0.9),
    ('fujifilm_nph_400_af3121e', 'Fujifilm NPH 400 (AF3-121E, 2002)', 'NPH 400', 'colour negative', '#79a184', 1.08),
    ('fujifilm_npz_800_af3100e', 'Fujifilm NPZ 800 (AF3-100E)', 'NPZ 800', 'colour negative', '#6b9476', 1.24),
    ('fujifilm_super_hg_1600_af3659en', 'Fujifilm Super HG 1600 (AF3-659EN)', 'Super HG 1600', 'colour negative', '#5e8869', 1.43),
    ('fujifilm_nexia_h400_af3013e', 'Fujifilm Nexia H400 (AF3-013E)', 'Nexia H400', 'colour negative', '#88a86e', 1.08),
    ('kodak_kodachrome_25_e55', 'Kodak Kodachrome 25 (PKM, E-55 2009)', 'Kodachrome 25', 'slide (positive)', '#d4b04e', 0.95),
    ('kodak_kodachrome_64_e55', 'Kodak Kodachrome 64 (PKR, E-55 2009)', 'Kodachrome 64 E-55', 'slide (positive)', '#bf9632', 1.15),
    ('kodak_kodachrome_200_e55', 'Kodak Kodachrome 200 (PKL, E-55 2009)', 'Kodachrome 200', 'slide (positive)', '#ad8528', 1.44),
    ('kodak_ektachrome_100d_h15294', 'Kodak Ektachrome 100D 5294/7294 (H-1-5294, 2024)', 'Ektachrome 100D', 'slide (positive)', '#4a78b5', 0.98),
    ('kodak_ektachrome_eir_ti2323', 'Kodak Ektachrome Infrared EIR (TI-2323, 2005)', 'Ektachrome EIR', 'slide (positive)', '#b0485a', 1.13),
    ('fujifilm_provia_100_rdp2_af3796e', 'Fujifilm Provia 100 RDP II (AF3-796E)', 'Provia 100 RDP II', 'slide (positive)', '#6996d6', 0.98),
    ('fujifilm_provia_400x_rxp_af30213e', 'Fujifilm Provia 400X RXP (AF3-0213E)', 'Provia 400X', 'slide (positive)', '#557fc0', 1.3),
    ('fujifilm_provia_1600_rsp_af3798e', 'Fujifilm Provia 1600 RSP (AF3-798E)', 'Provia 1600', 'slide (positive)', '#476fad', 1.71),
    ('fujifilm_ms_100_1000_rms_af3989e', 'Fujifilm MS 100/1000 RMS (EI 100, AF3-989E)', 'MS 100/1000', 'slide (positive)', '#7a8fc4', 0.98),
    ('fujifilm_t64_rtp_af3178e', 'Fujifilm T64 RTP (AF3-178E)', 'T64', 'slide (positive)', '#5a86c9', 0.9),
    ('fujifilm_velvia_50_rvp50_af30221e2', 'Fujifilm Velvia 50 RVP50 (2007, AF3-0221E2)', 'Velvia 50', 'slide (positive)', '#a84a7e', 0.86),
    ('kodak_exr_50d_5245', 'Kodak EXR 50D 5245 (H-1-5245t)', 'EXR 50D 5245', 'cine negative', '#7591a1', 0.71),
    ('kodak_exr_100t_5248', 'Kodak EXR 100T 5248 (H-1-7248)', 'EXR 100T 5248', 'cine negative', '#6a8698', 0.82),
    ('kodak_exr_200t_5293', 'Kodak EXR 200T 5293 (H-1-5293t)', 'EXR 200T 5293', 'cine negative', '#5f7b8f', 0.94),
    ('kodak_exr_500t_5298', 'Kodak EXR 500T 5298 (TI2082)', 'EXR 500T 5298', 'cine negative', '#547086', 1.13),
    ('kodak_vision_250d_5246', 'Kodak Vision 250D 5246 (H-1-5246t)', 'Vision 250D 5246', 'cine negative', '#638c95', 0.98),
    ('kodak_vision_320t_5277', 'Kodak Vision 320T 5277 (H-1-5277t)', 'Vision 320T 5277', 'cine negative', '#58808f', 1.03),
    ('kodak_vision_500t_5279', 'Kodak Vision 500T 5279 (H-1-5279)', 'Vision 500T 5279', 'cine negative', '#4d7589', 1.13),
    ('kodak_vision_500t_5263', 'Kodak Vision 500T 5263 (H-1-5263tx)', 'Vision 500T 5263', 'cine negative', '#436a80', 1.13),
    ('fujifilm_f64d_kb1101e', 'Fujifilm F-64D (KB-1101E)', 'F-64D', 'cine negative', '#7a9a92', 0.75),
    ('fujifilm_f125_kb913e', 'Fujifilm F-125 (KB-913E)', 'F-125', 'cine negative', '#6f9089', 0.86),
    ('fujifilm_f250_kb914e', 'Fujifilm F-250 (KB-914E)', 'F-250', 'cine negative', '#648680', 0.98),
    ('fujifilm_eterna_250d_kb0507er', 'Fujifilm Eterna 250D (KB-0507ER)', 'Eterna 250D', 'cine negative', '#6e9a8a', 0.98),
    ('fujifilm_eterna_250_kb1101e', 'Fujifilm Eterna 250 (KB-1101E)', 'Eterna 250', 'cine negative', '#638f80', 0.98),
    ('fujifilm_eterna_400_kb1101e', 'Fujifilm Eterna 400 (KB-1101E)', 'Eterna 400', 'cine negative', '#588576', 1.08),
    ('fujifilm_eterna_vivid_160_kb0701e', 'Fujifilm Eterna Vivid 160 (KB-0701E)', 'Eterna Vivid 160', 'cine negative', '#4f9a7c', 0.9),
    ('fujifilm_eterna_vivid_500_kb0901e', 'Fujifilm Eterna Vivid 500 (KB-0901E)', 'Eterna Vivid 500', 'cine negative', '#45886d', 1.13),
    ('fujifilm_reala_500d_kb1101e', 'Fujifilm Reala 500D (KB-1101E)', 'Reala 500D', 'cine negative', '#5a7f71', 1.13),
]
for _sid, _name, _short, _kind, _swatch, _grain in FILMCOLORS:
    NAMES[_sid] = (_name, _short, _kind)
    CHOSEN[_sid] = _swatch
    COLOUR_GRAIN[_sid] = _grain
# After every colour film already in the picker and before the black-and-white
# films (the product's colour-then-silver rule above), so the 34 that were there keep their order.
ORDER[ORDER.index("kodak_tri_x_400"):ORDER.index("kodak_tri_x_400")] = [r[0] for r in FILMCOLORS]

# A silver paper's grades as packs (`engine/resources_product/paper_grades.json`),
# and the filter new prints are made through.
PAPER_GRADES = REPO / "engine/resources_product/paper_grades.json"
GRADE = "2"


def iso_of(short: str):
    m = re.search(r"(\d{2,4})", short)
    return int(m.group(1)) if m else None


def main() -> None:
    paths = {p.stem: p for d in (PROFILES, PRODUCT_PROFILES) for p in sorted(d.glob("*.json"))}
    ids = sorted(paths)
    missing = [i for i in ids if i not in NAMES]
    if missing:
        raise SystemExit(f"no name in NAMES for: {', '.join(missing)}")
    unordered = [i for i in ids if i not in ORDER]
    if unordered:
        raise SystemExit(f"no place in the picker's order for: {', '.join(unordered)}")
    grades = json.loads(PAPER_GRADES.read_text()) if PAPER_GRADES.exists() else {}
    stocks = []
    for sid in [i for i in ORDER if i in ids]:
        info = {**json.loads(paths[sid].read_text())["info"], **INFO.get(sid, {})}
        name, short, kind = NAMES[sid]
        film = info.get("stage") == "filming"
        stock = {
            "id": sid,
            "name": name,
            "shortName": short,
            "kind": kind,
            "stage": info.get("stage"),            # filming | printing
            "use": info.get("use", "still"),       # still | cine
            "type": info.get("type"),              # negative | positive
            "targetPrint": info.get("target_print"),
            "iso": iso_of(short) if film else None,
            "swatch": DRAWN.get(sid) or CHOSEN[sid],
        }
        if info.get("channel_model") == "bw":
            stock["monochrome"] = True
            if film:
                if sid not in OWN_GRAIN:
                    raise SystemExit(f"no grain amount of its own for the black-and-white film {sid}")
                stock["grain"] = OWN_GRAIN[sid]
            else:
                if grades.get("paper") != sid or GRADE not in grades.get("grades", {}):
                    raise SystemExit(f"no filter {GRADE} pack for the silver paper {sid} in {PAPER_GRADES.name}")
                g = grades["grades"][GRADE]
                stock["neutralPack"] = [0.0, g["m_filter_neutral"], g["y_filter_neutral"]]
        if film and info.get("channel_model") != "bw":
            if sid not in COLOUR_GRAIN:
                raise SystemExit(f"no grain amount of its own for the colour film {sid}")
            stock["grain"] = COLOUR_GRAIN[sid]
        stocks.append(stock)
    OUT.write_text(json.dumps({"stocks": stocks}, indent=1, ensure_ascii=False) + "\n")
    mono = [s["shortName"] for s in stocks if s.get("monochrome")]
    print(f"wrote {len(stocks)} stocks -> {OUT.relative_to(REPO)} ({len(mono)} black and white: {', '.join(mono)})")


if __name__ == "__main__":
    main()
