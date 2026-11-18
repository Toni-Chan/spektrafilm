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
    "kodak_portra_160nc": ("Kodak Portra 160NC", "Portra 160NC", "colour negative"),
    "kodak_portra_160vc": ("Kodak Portra 160VC", "Portra 160VC", "colour negative"),
    "kodak_portra_400nc": ("Kodak Portra 400NC", "Portra 400NC", "colour negative"),
    "kodak_portra_400vc": ("Kodak Portra 400VC", "Portra 400VC", "colour negative"),
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
    # the 2006-2011 line: NC softer, VC deeper, beside their successors' hues
    "kodak_portra_160nc": "#e8c8ad", "kodak_portra_160vc": "#e0a47f",
    "kodak_portra_400nc": "#ddb390", "kodak_portra_400vc": "#d08c63",
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
    # the product's own colour films (E-190), with their family
    "kodak_portra_160nc", "kodak_portra_160vc", "kodak_portra_400nc", "kodak_portra_400vc",
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
    # ISO, the product's own profiles (2026-11-15; the same probe re-measured Portra 160 / 400 at 0.915 / 1.062):
    # green 7.29 / 8.34 / 7.46 / 8.61 at 1. VC's steeper curves render grainier, so it takes less to reach its speed's.
    "kodak_portra_160nc": 0.79, "kodak_portra_160vc": 0.69, "kodak_portra_400nc": 0.94, "kodak_portra_400vc": 0.81,
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

# The first catalogues (Toni-Chan/spektrafilm main: PR #2's 25 *_fdg profiles
# from the Fujifilm Professional Data Guide, PR #4's 63 KODAK E-series
# technical-data profiles, PR #5's DIR scale overrides baked into the profiles).
# Same rules as FILMCOLORS: the profile's name, a short name without maker or
# code, except where it would match another card's, which then takes the
# source's code ("PDG" for the Pro Data Guide, the KODAK publication number).
# Grain: the same ESTIMATE placeholder rule as FILMCOLORS_GRAIN; Superia Reala
# takes ISO 100 and Vericolor III (no speed in its short name) ISO 160.
FILMCOLORS_LEGACY = [
    ('fujifilm_nexia_400_fdg', 'Fujifilm Nexia 400 (Pro Data Guide)', 'Nexia 400', 'colour negative', '#75c782', 1.08),
    ('fujifilm_nexia_800_fdg', 'Fujifilm Nexia 800 (Pro Data Guide)', 'Nexia 800', 'colour negative', '#4eb761', 1.24),
    ('fujifilm_nexia_a200_fdg', 'Fujifilm Nexia A200 (Pro Data Guide)', 'Nexia A200', 'colour negative', '#3b914d', 0.94),
    ('fujifilm_npl_160_fdg', 'Fujifilm NPL 160 (Pro Data Guide)', 'NPL 160', 'colour negative', '#53b96b', 0.9),
    ('fujifilm_pro_160c_fdg', 'Fujifilm Pro 160C (Pro Data Guide)', 'Pro 160C', 'colour negative', '#3d9755', 0.9),
    ('fujifilm_pro_160s_fdg', 'Fujifilm Pro 160S (Pro Data Guide)', 'Pro 160S', 'colour negative', '#59bb75', 0.9),
    ('fujifilm_pro_400h_fdg', 'Fujifilm Pro 400H (Pro Data Guide)', 'Pro 400H PDG', 'colour negative', '#409c5d', 1.08),
    ('fujifilm_pro_800z_fdg', 'Fujifilm Pro 800Z (Pro Data Guide)', 'Pro 800Z', 'colour negative', '#5fbe7f', 1.24),
    ('fujifilm_superia_100_fdg', 'Fujifilm Superia 100 (Pro Data Guide)', 'Superia 100', 'colour negative', '#42a265', 0.82),
    ('fujifilm_superia_1600_fdg', 'Fujifilm Superia 1600 (Pro Data Guide)', 'Superia 1600', 'colour negative', '#64c088', 1.43),
    ('fujifilm_superia_200_fdg', 'Fujifilm Superia 200 (Pro Data Guide)', 'Superia 200', 'colour negative', '#44a86e', 0.94),
    ('fujifilm_superia_reala_fdg', 'Fujifilm Superia Reala (Pro Data Guide)', 'Superia Reala 100', 'colour negative', '#6ac291', 0.82),
    ('fujifilm_superia_xtra_400_fdg', 'Fujifilm Superia X-Tra 400 (Pro Data Guide)', 'Superia X-Tra 400', 'colour negative', '#47ad77', 1.08),
    ('fujifilm_superia_xtra_800_fdg', 'Fujifilm Superia X-Tra 800 (Pro Data Guide)', 'Superia X-Tra 800', 'colour negative', '#70c49a', 1.24),
    ('fujifilm_true_definition_400_fdg', 'Fujifilm True Definition 400 (Pro Data Guide)', 'True Definition 400', 'colour negative', '#49b380', 1.08),
    ('fujifilm_64t_type_ii_fdg', 'Fujifilm 64T Type II (Pro Data Guide)', '64T Type II', 'slide (positive)', '#7596c7', 0.9),
    ('fujifilm_astia_100f_fdg', 'Fujifilm Astia 100F (Pro Data Guide)', 'Astia 100F', 'slide (positive)', '#4563a8', 0.98),
    ('fujifilm_provia_100f_fdg', 'Fujifilm Provia 100F (Pro Data Guide)', 'Provia 100F PDG', 'slide (positive)', '#5569ba', 0.98),
    ('fujifilm_provia_400f_fdg', 'Fujifilm Provia 400F (Pro Data Guide)', 'Provia 400F', 'slide (positive)', '#6d76c4', 1.3),
    ('fujifilm_sensia_100_fdg', 'Fujifilm Sensia 100 (Pro Data Guide)', 'Sensia 100', 'slide (positive)', '#4141a0', 0.98),
    ('fujifilm_sensia_200_fdg', 'Fujifilm Sensia 200 (Pro Data Guide)', 'Sensia 200', 'slide (positive)', '#584db6', 1.13),
    ('fujifilm_sensia_400_fdg', 'Fujifilm Sensia 400 (Pro Data Guide)', 'Sensia 400', 'slide (positive)', '#7765c0', 1.3),
    ('fujifilm_velvia_100_fdg', 'Fujifilm Velvia 100 (Pro Data Guide)', 'Velvia 100 PDG', 'slide (positive)', '#593e98', 0.98),
    ('fujifilm_velvia_100f_fdg', 'Fujifilm Velvia 100F (Pro Data Guide)', 'Velvia 100F', 'slide (positive)', '#7248b0', 0.98),
    ('fujifilm_velvia_50_fdg', 'Fujifilm Velvia 50 (Pro Data Guide)', 'Velvia 50 PDG', 'slide (positive)', '#8d5dbd', 0.86),
    ('kodak_advantix_100_e46', 'Kodak Advantix 100 (E-46, 1998)', 'Advantix 100 E-46', 'colour negative', '#cd9584', 0.82),
    ('kodak_advantix_100_e7003', 'Kodak Advantix 100 (E-7003, 2002)', 'Advantix 100 E-7003', 'colour negative', '#c58670', 0.82),
    ('kodak_advantix_200_e46', 'Kodak Advantix 200 (E-46, 1998)', 'Advantix 200', 'colour negative', '#bd775c', 0.94),
    ('kodak_advantix_400_e46', 'Kodak Advantix 400 (E-46, 1998)', 'Advantix 400', 'colour negative', '#b46949', 1.08),
    ('kodak_advantix_bright_sun_flash_hd200_e7003', 'Kodak Advantix Bright Sun & Flash 200 (E-7003, 2002)', 'Advantix Bright Sun & Flash 200', 'colour negative', '#cd9b84', 0.94),
    ('kodak_advantix_versatility_e7003', 'Kodak Advantix Versatility 400 (E-7003, 2002)', 'Advantix Versatility 400', 'colour negative', '#c58c70', 1.08),
    ('kodak_bright_sun_flash_200_e2329', 'Kodak Bright Sun & Flash 200 (E-2329, 2003)', 'Bright Sun & Flash 200', 'colour negative', '#bd7e5c', 0.94),
    ('kodak_ektapress_pj100_e116', 'Kodak Ektapress PJ100 (E-116, 2003)', 'Ektapress PJ100', 'colour negative', '#b47049', 0.82),
    ('kodak_ektapress_pj400_e116', 'Kodak Ektapress PJ400 (E-116, 2003)', 'Ektapress PJ400', 'colour negative', '#cda084', 1.08),
    ('kodak_ektapress_pj800_e116', 'Kodak Ektapress PJ800 (E-116, 2003)', 'Ektapress PJ800', 'colour negative', '#c59270', 1.24),
    ('kodak_max_versatility_400_e2330', 'Kodak Max Versatility 400 (E-2330, 2001)', 'Max Versatility 400', 'colour negative', '#bd855c', 1.08),
    ('kodak_max_versatility_plus_800_e2452', 'Kodak Max Versatility Plus 800 (E-2452, 2001)', 'Max Versatility Plus 800', 'colour negative', '#b47849', 1.24),
    ('kodak_portra_100t_e2468', 'Kodak Portra 100T (E-2468, 2003)', 'Portra 100T', 'colour negative', '#cda584', 0.82),
    ('kodak_portra_160nc_e190', 'Kodak Portra 160NC (E-190, 2003)', 'Portra 160NC E-190', 'colour negative', '#c59870', 0.9),
    ('kodak_portra_160vc_e190', 'Kodak Portra 160VC (E-190, 2003)', 'Portra 160VC E-190', 'colour negative', '#bd8b5c', 0.9),
    ('kodak_portra_400nc_e190', 'Kodak Portra 400NC (E-190, 2003)', 'Portra 400NC E-190', 'colour negative', '#b47f49', 1.08),
    ('kodak_portra_400uc_e190', 'Kodak Portra 400UC (E-190, 2003)', 'Portra 400UC', 'colour negative', '#cdaa84', 1.08),
    ('kodak_portra_400vc_e190', 'Kodak Portra 400VC (E-190, 2003)', 'Portra 400VC E-190', 'colour negative', '#c59e70', 1.08),
    ('kodak_portra_800_e190', 'Kodak Portra 800 (E-190, 2003)', 'Portra 800 E-190', 'colour negative', '#bd925c', 1.24),
    ('kodak_pro_1000_e182', 'Kodak Pro 1000 (E-182, 1997)', 'Pro 1000', 'colour negative', '#b48749', 1.3),
    ('kodak_pro_100_e182', 'Kodak Pro 100 (E-182, 1997)', 'Pro 100', 'colour negative', '#cdaf84', 0.82),
    ('kodak_pro_100t_e182', 'Kodak Pro 100T (E-182, 1997)', 'Pro 100T E-182', 'colour negative', '#c5a470', 0.82),
    ('kodak_pro_100t_e29', 'Kodak Pro 100T (E-29, 1999)', 'Pro 100T E-29', 'colour negative', '#bd995c', 0.82),
    ('kodak_pro_400_e182', 'Kodak Pro 400 (E-182, 1997)', 'Pro 400', 'colour negative', '#b48e49', 1.08),
    ('kodak_pro_400mc_e182', 'Kodak Pro 400 MC (E-182, 1997)', 'Pro 400 MC', 'colour negative', '#cdb484', 1.08),
    ('kodak_pro_image_100_e4l', 'Kodak Pro Image 100 (E-4L, 1997)', 'Pro Image 100', 'colour negative', '#c5aa70', 0.82),
    ('kodak_royal_gold_400_e7007', 'Kodak Royal Gold 400 (E-7007, 2002)', 'Royal Gold 400', 'colour negative', '#bda05c', 1.08),
    ('kodak_vericolor_iii_e26', 'Kodak Vericolor III (E-26, 1997)', 'Vericolor III', 'colour negative', '#b49649', 0.9),
    ('kodak_ektachrome_100_e27', 'Kodak Ektachrome 100 (EPN) (E-27, 2003)', 'Ektachrome 100 E-27', 'slide (positive)', '#6ec4c4', 0.98),
    ('kodak_ektachrome_100_plus_e113', 'Kodak Ektachrome 100 Plus (EPP) (E-113, 2003)', 'Ektachrome 100 Plus', 'slide (positive)', '#4db3b6', 0.98),
    ('kodak_ektachrome_160t_e144', 'Kodak Ektachrome 160T (EPT) (E-144, 2003)', 'Ektachrome 160T', 'slide (positive)', '#3e9398', 1.08),
    ('kodak_ektachrome_320t_e145', 'Kodak Ektachrome 320T (EPJ) (E-145, 2003)', 'Ektachrome 320T', 'slide (positive)', '#60b6be', 1.24),
    ('kodak_ektachrome_400x_e161', 'Kodak Ektachrome 400X (EPL) (E-161, 2003)', 'Ektachrome 400X', 'slide (positive)', '#469faa', 1.3),
    ('kodak_ektachrome_64_e8', 'Kodak Ektachrome 64 (EPR) (E-8, 2003)', 'Ektachrome 64', 'slide (positive)', '#387e8a', 0.9),
    ('kodak_ektachrome_64t_e130', 'Kodak Ektachrome 64T (EPY) (E-130, 2003)', 'Ektachrome 64T', 'slide (positive)', '#52a7b8', 0.9),
    ('kodak_ektachrome_e100g_e4024', 'Kodak Ektachrome E100G (E-4024, 2003)', 'Ektachrome E100G', 'slide (positive)', '#408a9c', 0.98),
    ('kodak_ektachrome_e100gx_e4024', 'Kodak Ektachrome E100GX (E-4024, 2003)', 'Ektachrome E100GX', 'slide (positive)', '#65abc0', 0.98),
    ('kodak_ektachrome_e100s_e164', 'Kodak Ektachrome E100S (E-164, 2003)', 'Ektachrome E100S', 'slide (positive)', '#4895af', 0.98),
    ('kodak_ektachrome_e100sw_e164', 'Kodak Ektachrome E100SW (E-164, 2003)', 'Ektachrome E100SW', 'slide (positive)', '#3a778e', 0.98),
    ('kodak_ektachrome_e100vs_e163', 'Kodak Ektachrome E100VS (E-163, 2001)', 'Ektachrome E100VS', 'slide (positive)', '#579bba', 0.98),
    ('kodak_ektachrome_e200_e28', 'Kodak Ektachrome E200 (E-28, 2002)', 'Ektachrome E200', 'slide (positive)', '#4281a1', 1.13),
    ('kodak_ektachrome_p1600_e147', 'Kodak Ektachrome P1600 (EPH) (E-147, 2003)', 'Ektachrome P1600', 'slide (positive)', '#69a1c2', 1.71),
    ('kodak_elite_chrome_100_e7014', 'Kodak Elite Chrome 100 (E-7014, 2003)', 'Elite Chrome 100', 'slide (positive)', '#498ab4', 0.98),
    ('kodak_elite_chrome_160t_e154', 'Kodak Elite Chrome 160T (E-154, 1998)', 'Elite Chrome 160T', 'slide (positive)', '#3c6e93', 1.08),
    ('kodak_elite_chrome_200_e148', 'Kodak Elite Chrome 200 (E-148, 1998)', 'Elite Chrome 200', 'slide (positive)', '#5b90bc', 1.13),
    ('kodak_elite_chrome_extra_color_100_e126', 'Kodak Elite Chrome Extra Color 100 (E-126, 1998)', 'Elite Chrome Extra Color 100', 'slide (positive)', '#4477a6', 0.98),
]
PAPERS_LEGACY = [
    ('kodak_color_metallic_e4005', 'Kodak Professional Color Metallic Paper (E-4005, 2003)', 'Color Metallic', 'colour paper', '#f5f1ea'),
    ('kodak_duraflex_e143', 'Kodak Professional Duraflex Print Material (E-143, 2003)', 'Duraflex', 'colour paper', '#f1ebe2'),
    ('kodak_edge_generations_e7010', 'Kodak Edge Generations Paper (E-7010, 2002)', 'Edge Generations', 'colour paper', '#f5f0e9'),
    ('kodak_ektacolor_edge_7_e19', 'Kodak Ektacolor Edge 7 Paper (E-19, 2003)', 'Ektacolor Edge 7', 'colour paper', '#f1ebe1'),
    ('kodak_ektacolor_royal_vii_e23', 'Kodak Ektacolor Royal VII Paper (E-23, 2003)', 'Ektacolor Royal VII', 'colour paper', '#f4f0e8'),
    ('kodak_endura_metallic_e4028', 'Kodak Professional Endura Metallic Paper (E-4028, 2003)', 'Endura Metallic', 'colour paper', '#f0ebe0'),
    ('kodak_portra_endura_e4021', 'Kodak Professional Portra Endura Paper (E-4021, 2003)', 'Portra Endura E-4021', 'colour paper', '#f3f0e7'),
    ('kodak_portra_iii_e140', 'Kodak Professional Portra III Paper (E-140, 2002)', 'Portra III', 'colour paper', '#f0ebdf'),
    ('kodak_royal_generations_e7009', 'Kodak Royal Generations Paper (E-7009, 2002)', 'Royal Generations', 'colour paper', '#f3efe6'),
    ('kodak_supra_endura_e4021', 'Kodak Professional Supra Endura Paper (E-4021, 2003)', 'Supra Endura E-4021', 'colour paper', '#efeade'),
    ('kodak_supra_iii_e141', 'Kodak Professional Supra III Paper (E-141, 2002)', 'Supra III', 'colour paper', '#f2efe5'),
    ('kodak_ultra_endura_e4020', 'Kodak Professional Ultra Endura Paper (E-4020, 2003)', 'Ultra Endura E-4020', 'colour paper', '#eeeadd'),
    ('kodak_ultra_iii_e142', 'Kodak Professional Ultra III Paper (E-142, 2003)', 'Ultra III', 'colour paper', '#f2efe3'),
    ('kodak_duraclear_e143', 'Kodak Professional Duraclear Display Material (E-143, 2003)', 'Duraclear', 'display film', '#e7ecee'),
    ('kodak_duratrans_e143', 'Kodak Professional Duratrans Display Material (E-143, 2003)', 'Duratrans', 'display film', '#d5dde2'),
    ('kodak_endura_clear_e4030', 'Kodak Professional Endura Clear Display Material (E-4030, 2002)', 'Endura Clear', 'display film', '#dbe0e6'),
    ('kodak_endura_transparency_e4030', 'Kodak Professional Endura Transparency Display Material (E-4030, 2002)', 'Endura Transparency', 'display film', '#e1e5ea'),
]
for _sid, _name, _short, _kind, _swatch, _grain in FILMCOLORS_LEGACY:
    NAMES[_sid] = (_name, _short, _kind)
    CHOSEN[_sid] = _swatch
    COLOUR_GRAIN[_sid] = _grain
# After the colour films above, still before the black-and-white films.
ORDER[ORDER.index("kodak_tri_x_400"):ORDER.index("kodak_tri_x_400")] = [r[0] for r in FILMCOLORS_LEGACY]
# The 13 reflective papers and the 4 backlit display transparencies (film
# support, printed and read like a cine print film: the engine treats a print
# stock the same whatever its support) go after every colour paper already
# there and before the silver paper.
for _sid, _name, _short, _kind, _swatch in PAPERS_LEGACY:
    NAMES[_sid] = (_name, _short, _kind)
    CHOSEN[_sid] = _swatch
ORDER[ORDER.index("ilford_multigrade_iv_rc"):ORDER.index("ilford_multigrade_iv_rc")] = [r[0] for r in PAPERS_LEGACY]

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
