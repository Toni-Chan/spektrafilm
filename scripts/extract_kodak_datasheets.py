#!/usr/bin/env python
"""Extract vector curve data from Kodak technical-data sheets (E-series, 1997-2003) into
upstream-spektrafilm-style raw CSV records (the layout read by spektrafilm_profile_builder).

Usage (needs `pip install pymupdf pillow scipy`; the PDFs are not shipped with the repository):

    mkdir -p kodak_pdfs && for f in e190-1 e4024 ...; do   # e55: https://125px.com/docs/film/kodak/e55.pdf
        curl -sL -o kodak_pdfs/$f.pdf https://125px.com/docs/unsorted/kodak/$f.pdf; done
    python scripts/extract_kodak_datasheets.py --pdfs kodak_pdfs \
        --out src/spektrafilm_profile_builder/data/raw/kodak_technical_data --checks /tmp/kodak_checks

`--catalog` additionally writes catalogue.csv describing every e*.pdf found in --pdfs.

Method: curves are vector polylines.  Plots are found from their section heading
("Characteristic Curves", "Spectral-Sensitivity Curves", ...) and the numeric tick labels under
it (a right-aligned column = y axis, a row = x axis); axes are calibrated with a robust linear (log
for MTF) fit of the label centres snapped to tick/grid lines; Kodak's bar notation for negative
logarithms (4̄.0 3̄.0 ... 0.0 1.0, printed without minus signs) is decoded from the label order.
Curve strokes (width >= 0.6 pt with diagonal segments) inside the plot are split into sub-paths,
chained, and assigned to channels by spectral position (sensitivity, dyes), by density order (C-41
negatives: B over G over R, status M), or by the nearest printed R/G/B label (status A curves).
"""
import argparse, csv, json, os, re, shutil, sys
from collections import defaultdict
import numpy as np
import pymupdf
from PIL import Image, ImageDraw
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kodak_plots as K  # noqa: E402

BASE_URL = 'https://125px.com/docs/unsorted/kodak/'
# sheets mirrored elsewhere on 125px.com (default: BASE_URL)
SOURCE_URLS = {'e55': 'https://125px.com/docs/film/kodak/'}


def source_url(stem):
    return SOURCE_URLS.get(stem, BASE_URL) + stem + '.pdf'

# ---------------------------------------------------------------------------------------------
# stock table: id, display name, type, pdf stem, plot selectors
#   type: negative | positive | paper | display (transparent/translucent print material)
#         | paper_digital | display_digital | reversal_paper | duplicating
#   selectors: list of (page, kind, column 'L'/'R'/None, nth in column or heading-regex)
#   pages=[...] alone selects every non-push plot on those pages.
# ---------------------------------------------------------------------------------------------
def P(*pages):
    return dict(pages=list(pages))


def S(*sels):
    return dict(sels=list(sels))


STOCKS = [
    # ---- colour negative films
    ('kodak_portra_160nc', 'KODAK PROFESSIONAL PORTRA 160NC', 'negative', 'e190-1', P(9)),
    ('kodak_portra_160vc', 'KODAK PROFESSIONAL PORTRA 160VC', 'negative', 'e190-1', P(10)),
    ('kodak_portra_400nc', 'KODAK PROFESSIONAL PORTRA 400NC', 'negative', 'e190-1', P(11)),
    ('kodak_portra_400vc', 'KODAK PROFESSIONAL PORTRA 400VC', 'negative', 'e190-1', P(12)),
    ('kodak_portra_400uc', 'KODAK PROFESSIONAL PORTRA 400UC', 'negative', 'e190-1', S((13, 'sens'), (13, 'dye'), (13, 'mtf'), (13, 'char', None, r'EI 400'))),
    ('kodak_portra_800', 'KODAK PROFESSIONAL PORTRA 800', 'negative', 'e190-1', S((14, 'char', None, r'EI 800$'), (15, 'sens'), (15, 'dye'), (15, 'mtf'))),
    ('kodak_portra_160nc', 'KODAK PROFESSIONAL PORTRA 160NC', 'negative', 'e190', P(8)),
    ('kodak_portra_160vc', 'KODAK PROFESSIONAL PORTRA 160VC', 'negative', 'e190', P(9)),
    ('kodak_portra_400nc', 'KODAK PROFESSIONAL PORTRA 400NC', 'negative', 'e190', P(10)),
    ('kodak_portra_400vc', 'KODAK PROFESSIONAL PORTRA 400VC', 'negative', 'e190', P(11)),
    ('kodak_portra_100t', 'KODAK PROFESSIONAL PORTRA 100T', 'negative', 'e2468', P(5)),
    ('kodak_ektapress_pj100', 'KODAK PROFESSIONAL EKTAPRESS PJ100', 'negative', 'e116-1', P(5)),
    ('kodak_ektapress_pj400', 'KODAK PROFESSIONAL EKTAPRESS PJ400', 'negative', 'e116-1', S((6, 'char', None, r'^Characteristic Curves$'), (7, 'sens'), (7, 'dye'))),
    ('kodak_ektapress_pj800', 'KODAK PROFESSIONAL EKTAPRESS PJ800', 'negative', 'e116-1', S((7, 'char', None, r'^Characteristic Curves$'), (8, 'sens'), (8, 'dye'))),
    ('kodak_ektapress_pj100', 'KODAK PROFESSIONAL EKTAPRESS PJ100', 'negative', 'e116', P(5)),
    ('kodak_ektapress_pj400', 'KODAK PROFESSIONAL EKTAPRESS PJ400', 'negative', 'e116', S((6, 'char', None, r'^Characteristic Curves$'), (7, 'sens'), (7, 'dye'))),
    ('kodak_ektapress_pj800', 'KODAK PROFESSIONAL EKTAPRESS PJ800', 'negative', 'e116', S((7, 'char', None, r'^Characteristic Curves$'), (8, 'sens'), (8, 'dye'))),
    ('kodak_pro_100', 'KODAK Pro 100 [PRN]', 'negative', 'e182', P(8)),
    ('kodak_pro_100t', 'KODAK Pro 100T [PRT]', 'negative', 'e182', P(9)),
    ('kodak_pro_400', 'KODAK Pro 400 [PPF]', 'negative', 'e182', P(10)),
    ('kodak_pro_400mc', 'KODAK Pro 400 MC [PMC]', 'negative', 'e182', P(11)),
    ('kodak_pro_1000', 'KODAK Pro 1000 [PMZ]', 'negative', 'e182', P(12)),
    ('kodak_pro_100t', 'KODAK Pro 100T [PRT]', 'negative', 'e29', P(4)),
    ('kodak_pro_image_100', 'KODAK PROFESSIONAL PRO IMAGE 100', 'negative', 'e4L', P(3)),
    ('kodak_vericolor_iii', 'KODAK VERICOLOR III Professional [VPS]', 'negative', 'e26', P(4)),
    ('kodak_royal_gold_400', 'KODAK ROYAL GOLD 400 [RC]', 'negative', 'e7007', P(5)),
    ('kodak_max_versatility_400', 'KODAK MAX Versatility (400)', 'negative', 'e2330', P(3, 4)),
    ('kodak_max_versatility_plus_800', 'KODAK MAX Versatility Plus (800)', 'negative', 'e2452', P(5)),
    ('kodak_bright_sun_flash_200', 'KODAK Bright Sun & Flash [GB] (200)', 'negative', 'e2329', P(3, 4)),
    ('kodak_advantix_100', 'KODAK ADVANTIX 100 (APS)', 'negative', 'e46', P(5)),
    ('kodak_advantix_200', 'KODAK ADVANTIX 200 (APS)', 'negative', 'e46', P(6)),
    ('kodak_advantix_400', 'KODAK ADVANTIX 400 (APS)', 'negative', 'e46', P(7)),
    ('kodak_advantix_100', 'KODAK ADVANTiX 100 (APS)', 'negative', 'e7003', S((6, 'char', 'L', 0), (6, 'sens', 'L', 0), (6, 'dye', 'R', 0))),
    ('kodak_advantix_bright_sun_flash_hd200', 'KODAK ADVANTiX Bright Sun & Flash / High Definition 200 (APS)', 'negative', 'e7003',
     S((6, 'char', 'R', 0), (7, 'sens', 'L', 0), (7, 'dye', 'L', 0))),
    ('kodak_advantix_versatility', 'KODAK ADVANTiX Versatility (APS)', 'negative', 'e7003', S((7, 'char', 'R', 0), (7, 'sens', 'R', 0), (8, 'dye'))),
    # ---- colour reversal films
    ('kodak_ektachrome_64', 'KODAK EKTACHROME 64 Professional [EPR]', 'positive', 'e8', P(5)),
    ('kodak_ektachrome_100', 'KODAK EKTACHROME 100 Professional [EPN]', 'positive', 'e27-1', P(5)),
    ('kodak_ektachrome_100', 'KODAK EKTACHROME 100 Professional [EPN]', 'positive', 'e27', P(5)),
    ('kodak_ektachrome_100_plus', 'KODAK EKTACHROME 100 PLUS Professional [EPP]', 'positive', 'e113-1', P(5)),
    ('kodak_ektachrome_100_plus', 'KODAK EKTACHROME 100 PLUS Professional [EPP]', 'positive', 'e113', P(5)),
    ('kodak_ektachrome_64t', 'KODAK EKTACHROME 64T Professional [EPY]', 'positive', 'e130-1', P(5)),
    ('kodak_ektachrome_64t', 'KODAK EKTACHROME 64T Professional [EPY]', 'positive', 'e130', P(3)),
    ('kodak_ektachrome_160t', 'KODAK EKTACHROME 160T Professional [EPT]', 'positive', 'e144', P(4, 5)),
    ('kodak_ektachrome_320t', 'KODAK EKTACHROME 320T Professional [EPJ]', 'positive', 'e145', P(5)),
    ('kodak_ektachrome_p1600', 'KODAK EKTACHROME P1600 Professional [EPH]', 'positive', 'e147', P(5)),
    ('kodak_ektachrome_400x', 'KODAK EKTACHROME 400X Professional [EPL]', 'positive', 'e161', P(5)),
    ('kodak_ektachrome_e100vs', 'KODAK PROFESSIONAL EKTACHROME E100VS', 'positive', 'e163-1', P(5)),
    ('kodak_ektachrome_e100vs', 'KODAK PROFESSIONAL EKTACHROME E100VS', 'positive', 'e163', P(5)),
    ('kodak_ektachrome_e100s', 'KODAK PROFESSIONAL EKTACHROME E100S', 'positive', 'e164', S((5, 'char', 'L', 0), (5, 'mtf'), (6, 'sens'), (6, 'dye'))),
    ('kodak_ektachrome_e100sw', 'KODAK PROFESSIONAL EKTACHROME E100SW', 'positive', 'e164', S((5, 'char', 'R', 0), (5, 'mtf'), (6, 'sens'), (6, 'dye'))),
    ('kodak_ektachrome_e200', 'KODAK PROFESSIONAL EKTACHROME E200', 'positive', 'e28-1', P(5)),
    ('kodak_ektachrome_e200', 'KODAK PROFESSIONAL EKTACHROME E200', 'positive', 'e28', P(5)),
    ('kodak_ektachrome_e100g', 'KODAK PROFESSIONAL EKTACHROME E100G', 'positive', 'e4024', S((5, 'char', 'L', 0), (5, 'sens'), (5, 'dye'), (6, 'mtf'))),
    ('kodak_ektachrome_e100gx', 'KODAK PROFESSIONAL EKTACHROME E100GX', 'positive', 'e4024', S((5, 'char', 'L', 1), (5, 'sens'), (5, 'dye'), (6, 'mtf'))),
    ('kodak_elite_chrome_100', 'KODAK ELITE Chrome 100', 'positive', 'e7014', P(3, 4)),
    ('kodak_elite_chrome_extra_color_100', 'KODAK ELITE Chrome Extra Color 100', 'positive', 'e126', P(5)),
    ('kodak_elite_chrome_200', 'KODAK ELITE Chrome 200', 'positive', 'e148', P(4)),
    ('kodak_elite_chrome_160t', 'KODAK ELITE Chrome 160T', 'positive', 'e154', P(3, 4)),
    ('kodak_kodachrome_25', 'KODAK KODACHROME 25 Professional [PKM]', 'positive', 'e55', dict(P(3), frame_top=('dye',))),
    ('kodak_kodachrome_64', 'KODAK KODACHROME 64 Professional [PKR]', 'positive', 'e55', dict(P(4), frame_top=('dye',))),
    ('kodak_kodachrome_200', 'KODAK KODACHROME 200 Professional [PKL]', 'positive', 'e55', dict(P(5), frame_top=('dye',))),
    ('kodak_ektachrome_duplicating_edupe', 'KODAK PROFESSIONAL EKTACHROME Duplicating Film EDUPE', 'duplicating', 'e2529',
     S((6, 'char', None, 'Roll'), (7, 'sens'), (7, 'dye'), (7, 'mtf'))),
    # ---- colour negative papers (optical printing, RA-4)
    ('kodak_portra_iii', 'KODAK PROFESSIONAL PORTRA III Paper', 'paper', 'e140', P(5)),
    ('kodak_supra_iii', 'KODAK PROFESSIONAL SUPRA III Paper', 'paper', 'e141', P(6)),
    ('kodak_ultra_iii', 'KODAK PROFESSIONAL ULTRA III Paper', 'paper', 'e142', P(6)),
    ('kodak_ektacolor_edge_7', 'KODAK EKTACOLOR Edge 7 Paper', 'paper', 'e19', P(5)),
    ('kodak_ektacolor_royal_vii', 'KODAK EKTACOLOR ROYAL VII Paper', 'paper', 'e23', P(5)),
    ('kodak_color_metallic', 'KODAK PROFESSIONAL Color Metallic Paper', 'paper', 'e4005', P(5, 6)),
    ('kodak_ultra_endura', 'KODAK PROFESSIONAL ULTRA ENDURA Paper', 'paper', 'e4020', P(7)),
    ('kodak_portra_endura', 'KODAK PROFESSIONAL PORTRA ENDURA Paper', 'paper', 'e4021', S((9, 'char', None, r'PROFESSIONAL$'), (10, 'sens'), (10, 'dye'))),
    ('kodak_supra_endura', 'KODAK PROFESSIONAL SUPRA ENDURA Paper', 'paper', 'e4021', S((9, 'char', None, r'SUPRA'), (10, 'sens'), (10, 'dye'))),
    ('kodak_endura_metallic', 'KODAK PROFESSIONAL ENDURA Metallic Paper', 'paper', 'e4028', P(7, 8)),
    ('kodak_royal_generations', 'KODAK ROYAL Generations Paper', 'paper', 'e7009', P(5)),
    ('kodak_edge_generations', 'KODAK EDGE Generations Paper', 'paper', 'e7010', P(5)),
    # ---- display / print materials for optical printing from negatives (RA-4)
    ('kodak_duraclear', 'KODAK PROFESSIONAL DURACLEAR Display Material', 'display', 'e143', P(4)),
    ('kodak_duratrans', 'KODAK PROFESSIONAL DURATRANS Display Material', 'display', 'e143', P(5)),
    ('kodak_duraflex', 'KODAK PROFESSIONAL DURAFLEX Print Material', 'paper', 'e143', P(6)),
    ('kodak_endura_transparency', 'KODAK PROFESSIONAL ENDURA Transparency Optical Display Material', 'display', 'e4030',
     S((5, 'char', 'L', 0), (5, 'sens'), (5, 'dye'))),
    ('kodak_endura_clear', 'KODAK PROFESSIONAL ENDURA Clear Optical Display Material', 'display', 'e4030',
     S((5, 'char', 'L', 1), (5, 'sens'), (5, 'dye'))),
    # ---- digital (laser / LED exposure) materials: records only
    ('kodak_digital_paper_2976', 'KODAK PROFESSIONAL Digital Paper, Type 2976', 'paper_digital', 'e118', P(3)),
    ('kodak_digital_iii', 'KODAK PROFESSIONAL Digital III Color Paper', 'paper_digital', 'e2446', P(4)),
    ('kodak_duraflex_plus_digital', 'KODAK PROFESSIONAL DURAFLEX Plus Digital Display Material', 'paper_digital', 'e4014', P(4)),
    ('kodak_endura_transparency_digital', 'KODAK PROFESSIONAL ENDURA Transparency Digital Display Material', 'display_digital', 'e4031',
     S((5, 'char', 'L', 0), (5, 'sens'), (5, 'dye'))),
    ('kodak_endura_clear_digital', 'KODAK PROFESSIONAL ENDURA Clear Digital Display Material', 'display_digital', 'e4031',
     S((5, 'char', 'L', 1), (5, 'sens'), (5, 'dye'))),
    # ---- colour reversal (positive-to-positive) papers and materials: records only
    ('kodak_radiance_iii', 'KODAK EKTACHROME RADIANCE III Paper', 'reversal_paper', 'e1766', P(5)),
    ('kodak_radiance_iii_copy', 'KODAK EKTACHROME RADIANCE III Copy Paper', 'reversal_paper', 'e2410', P(3, 4)),
    ('kodak_radiance_iii_hc_copy', 'KODAK EKTACHROME RADIANCE III HC Copy Paper', 'reversal_paper', 'e2411', P(4)),
    ('kodak_radiance_iii_overhead', 'KODAK EKTACHROME RADIANCE III Overhead Material', 'reversal_paper', 'e2412a', P(3)),
    ('kodak_radiance_iii_clear_display', 'KODAK EKTACHROME RADIANCE III Clear Display Material', 'reversal_paper', 'e2412b', P(4)),
    ('kodak_radiance_iii_translucent_display', 'KODAK EKTACHROME RADIANCE III Translucent Display Material', 'reversal_paper', 'e2413', P(4)),
]

STATUS_A_TYPES = ('positive', 'paper', 'display', 'paper_digital', 'display_digital', 'reversal_paper', 'duplicating')
MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'


# ---------------------------------------------------------------------------------------------
def pub_info(doc):
    t = doc[0].get_text()
    m = re.search(rf'({MONTHS})\s+(\d{{4}})\s*•\s*(E-?\s?\w+)', t)
    if not m:  # e163-1 has an obfuscated date font
        m2 = re.search(r'©Eastman Kodak Company,\s*(\d{4})', t)
        code = re.search(r'•\s*(E-?\s?\d+\w*)', t)
        return (m2.group(1) if m2 else '', code.group(1).replace(' ', '') if code else '')
    return f'{m.group(1)} {m.group(2)}', m.group(3).replace(' ', '').replace('E', 'E-', 1).replace('E--', 'E-')


def column(plot, page):
    r = plot['head']['rect']
    return 'L' if (r.x0 + r.x1) / 2 < page.rect.width / 2 else 'R'


def select_plots(doc, spec, cache):
    chosen = []
    if 'pages' in spec:
        for pn in spec['pages']:
            plots = cache[pn][0]
            seen = set()
            for pl in plots:
                if not pl['ok'] or re.search(r'push', pl['head']['text'] + ' ' + pl['head']['sub'], re.I):
                    continue
                k = pl['head']['kind']
                if k in seen:  # first plot of each kind on the page (reading order)
                    continue
                seen.add(k); chosen.append((pn, pl))
    else:
        for sel in spec['sels']:
            pn, kind = sel[0], sel[1]
            plots = [pl for pl in cache[pn][0] if pl['ok'] and pl['head']['kind'] == kind]
            if len(sel) > 2 and sel[2]:
                plots = [pl for pl in plots if column(pl, doc[pn - 1]) == sel[2]]
            if len(sel) > 3:
                if isinstance(sel[3], int):
                    plots = sorted(plots, key=lambda pl: pl['head']['rect'].y0)[sel[3]:sel[3] + 1]
                else:
                    plots = [pl for pl in plots if re.search(sel[3], pl['head']['text'].strip())]
            if not plots:
                raise ValueError(f'selector {sel} matched nothing')
            chosen.append((pn, plots[0]))
    return chosen


# ---------------------------------------------------------------------------------------------
def _tangent(a, end):
    k = min(len(a) - 1, 4)
    v = (a[-1] - a[-1 - k]) if end else (a[k] - a[0])
    n = np.hypot(*v)
    return v / n if n > 0 else v


def chain(pieces, tol=1.6, max_turn_deg=60):
    """Join sub-paths whose end points touch into continuous curves (pt space, x increasing).
    Two pieces are joined only if the curve direction is continuous at the junction (turn <
    max_turn_deg), so that two different curves that merely touch are not merged."""
    segs = []
    for p in pieces:
        a = p['pts'] if isinstance(p, dict) else p
        if a[0, 0] > a[-1, 0]:
            a = a[::-1]
        segs.append(a)
    segs.sort(key=lambda a: a[0, 0])
    used = [False] * len(segs)
    cos_lim = np.cos(np.radians(max_turn_deg))
    out = []
    for i in range(len(segs)):
        if used[i]:
            continue
        cur = segs[i]; used[i] = True
        grown = True
        while grown:
            grown = False
            best = None
            for j in range(len(segs)):
                if used[j]:
                    continue
                dj = np.hypot(*(segs[j][0] - cur[-1]))
                if dj < tol and np.dot(_tangent(cur, True), _tangent(segs[j], False)) > cos_lim:
                    if best is None or dj < best[0]:
                        best = (dj, j, 'end')
                dj = np.hypot(*(segs[j][-1] - cur[0]))
                if dj < tol and np.dot(_tangent(segs[j], True), _tangent(cur, False)) > cos_lim:
                    if best is None or dj < best[0]:
                        best = (dj, j, 'start')
            if best:
                _, j, where = best
                cur = np.vstack([cur, segs[j][1:]]) if where == 'end' else np.vstack([segs[j][:-1], cur])
                used[j] = True; grown = True
        out.append(cur)
    return out


def simplify(xy, X, Y, tol_pt=0.02):
    """Ramer-Douglas-Peucker in page units (points): drops vertices that lie
    within ``tol_pt`` (0.02 pt, about 0.001 density) of the polyline through the kept ones, far below the
    drawing accuracy, so the CSVs stay small without changing the curves."""
    if len(xy) < 3:
        return xy
    P = np.column_stack([X.inv(xy[:, 0]), Y.inv(xy[:, 1])])
    keep = np.zeros(len(P), bool); keep[[0, -1]] = True
    stack = [(0, len(P) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = P[i], P[j]
        d = b - a
        L = np.hypot(*d)
        seg = P[i + 1:j] - a
        dist = np.abs(seg[:, 0] * d[1] - seg[:, 1] * d[0]) / L if L > 0 else np.hypot(seg[:, 0], seg[:, 1])
        k = int(np.argmax(dist))
        if dist[k] > tol_pt:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return xy[keep]


def to_xy(pts, X, Y):
    xy = np.column_stack([X(pts[:, 0]), Y(pts[:, 1])])
    if xy[0, 0] > xy[-1, 0]:
        xy = xy[::-1]
    return K.monotone(xy)


def labels_in(plot, toks, words, pad=(30, 12)):
    B = plot['box']
    out = []
    for t in toks:
        w = t['t'].strip('-–,.:;()')
        if w in words and B.x0 - 6 < t['x0'] < B.x1 + pad[0] and B.y0 - pad[1] < t['y0'] < B.y1 + 4:
            out.append(dict(w=w, x=(t['x0'] + t['x1']) / 2, y=(t['y0'] + t['y1']) / 2))
    return out


def assign_by_labels(curves_pt, labels):
    if not labels or not curves_pt:
        return None
    D = np.zeros((len(labels), len(curves_pt)))
    for i, L in enumerate(labels):
        for j, c in enumerate(curves_pt):
            D[i, j] = np.min(np.hypot(c[:, 0] - L['x'], c[:, 1] - L['y']))
    ri, ci = linear_sum_assignment(D)
    res = {labels[i]['w']: ci_ for i, ci_ in zip(ri, ci)}
    for i, L in enumerate(labels):  # coincident curves: a label left over shares its nearest curve
        if L['w'] not in res:
            res[L['w']] = int(np.argmin(D[i]))
    return res, D


def span_frac(xy, X0, X1):
    return (xy[-1, 0] - xy[0, 0]) / (X1 - X0)


def assign(kind, stype, plot, curves_pt, X, Y, toks, notes):
    xys = [to_xy(c, X, Y) for c in curves_pt]
    keep = [i for i, a in enumerate(xys) if len(a) >= 4]
    curves_pt = [curves_pt[i] for i in keep]; xys = [xys[i] for i in keep]
    res = {}
    xmin = X(plot['box'].x0); xmax = X(plot['box'].x1)
    if kind == 'sens':
        groups = defaultdict(list)
        for xy in xys:
            if xy[-1, 0] - xy[0, 0] < 1.5:
                continue
            pk = xy[np.argmax(xy[:, 1]), 0]
            ch = 'b' if pk < 500 else 'g' if pk < 600 else 'r'
            groups[ch].append(xy)
        for ch, parts in groups.items():
            if len(parts) > 1:
                notes.append(f'sensitivity {ch}: merged {len(parts)} sub-paths')
            res[f'log_sensitivity_{ch}'] = K.merge(parts)
    elif kind == 'char':
        labs = labels_in(plot, toks, {'R', 'G', 'B'})
        if stype == 'negative':
            order = sorted(range(len(xys)), key=lambda i: -np.mean(xys[i][:, 1]))
            if len(order) != 3:
                notes.append(f'characteristic plot had {len(order)} curves (expected 3)')
            for ch, i in zip('bgr', order[:3]):
                res[f'density_curve_{ch}'] = xys[i]
        else:
            extra_pt = []
            if len(xys) > 3:
                # the three longest strokes are the curves; shorter ones are broken-off pieces of a
                # curve (joined below to the curve whose end they continue) or marks (dropped)
                order = sorted(range(len(xys)), key=lambda i: -(np.ptp(curves_pt[i][:, 0])))
                extra_pt = [curves_pt[i] for i in order[3:]]
                curves_pt = [curves_pt[i] for i in order[:3]]; xys = [xys[i] for i in order[:3]]
            lab = assign_by_labels(curves_pt, labs)
            if lab and set(lab[0]) >= {'R', 'G', 'B'}:
                m = lab[0]
                if len(set(m.values())) < 3:
                    notes.append('characteristic: fewer distinct curves than R/G/B labels; coincident channels share a trace')
                joined = {i: [xys[i]] for i in range(len(xys))}
                for e in extra_pt:
                    dmin, best = 1e9, None
                    for i, c in enumerate(curves_pt):
                        for a in (e[0], e[-1]):
                            for b in (c[0], c[-1]):
                                dd = np.hypot(*(a - b))
                                if dd < dmin:
                                    dmin, best = dd, i
                    if dmin < 8:
                        joined[best].append(to_xy(e, X, Y))
                        notes.append(f'characteristic: a {np.ptp(e[:, 0]):.0f}-pt piece joined to a curve (gap {dmin:.1f} pt)')
                    else:
                        notes.append(f'characteristic: a {np.ptp(e[:, 0]):.0f}-pt stroke not continuing any curve dropped')
                for ch in 'RGB':
                    res[f'density_curve_{ch.lower()}'] = K.merge(joined[m[ch]])
            else:
                notes.append(f'characteristic: R/G/B labels not found ({[l["w"] for l in labs]}); channels by Dmax order')
                order = sorted(range(len(xys)), key=lambda i: -xys[i][:, 1].max())
                for ch, i in zip('bgr', order):
                    res[f'density_curve_{ch}'] = xys[i]
    elif kind == 'dye':
        words = labels_in(plot, toks, {'Midscale', 'Minimum', 'Yellow', 'Magenta', 'Cyan', 'Neutral'}, pad=(10, 40))
        wset = {w['w'] for w in words}
        xys = [a for a in xys if a[-1, 0] - a[0, 0] > 1.5]
        full = [a for a in xys if span_frac(a, xmin, xmax) > 0.6]
        if ('Midscale' in wset or 'Minimum' in wset) and stype == 'negative':
            if len(full) < 2:
                notes.append(f'dye plot: only {len(full)} full-range curves for mid/min')
            full = sorted(full, key=lambda a: -np.mean(a[:, 1]))
            if full:
                res['dye_density_mid'] = full[0]
            if len(full) > 1:
                res['dye_density_min'] = full[-1]
            rest = [a for a in xys if not any(a is f for f in full[:1] + full[-1:])]
            if not ({'Yellow', 'Magenta', 'Cyan'} & wset) and len(full) >= 2:
                # no separate dyes printed: leftover pieces are broken-off parts of mid / min
                for a in rest:
                    def gap(f):
                        return min(np.hypot(a[0, 0] - f[-1, 0], (a[0, 1] - f[-1, 1]) * 100),
                                   np.hypot(a[-1, 0] - f[0, 0], (a[-1, 1] - f[0, 1]) * 100),
                                   abs(np.interp(a[:, 0], f[:, 0], f[:, 1], left=np.nan, right=np.nan) - a[:, 1]).mean() * 100
                                   if (a[:, 0] > f[0, 0]).any() and (a[:, 0] < f[-1, 0]).any() else 1e9)
                    tgt = 'dye_density_mid' if gap(res['dye_density_mid']) <= gap(res['dye_density_min']) else 'dye_density_min'
                    res[tgt] = K.merge([res[tgt], a])
                    notes.append(f'dye plot: piece {a[0,0]:.0f}-{a[-1,0]:.0f} nm joined to {tgt[12:]}')
                rest = []
        else:
            rest = list(xys)
        if 'dye_density_mid' not in res and len(rest) >= 4:
            # visual-neutral sum curve drawn over the three dyes
            def dominates(a):
                grid = np.linspace(max(a[0, 0], 410), min(a[-1, 0], 690), 40)
                ya = np.interp(grid, a[:, 0], a[:, 1])
                for b in rest:
                    if b is a:
                        continue
                    sel = (grid > b[0, 0]) & (grid < b[-1, 0])
                    if sel.any() and np.mean(ya[sel] >= np.interp(grid[sel], b[:, 0], b[:, 1]) - 0.02) < 0.9:
                        return False
                return True
            dom = [a for a in rest if dominates(a) and a[-1, 0] - a[0, 0] > 10]
            cover = sum(a[-1, 0] - a[0, 0] for a in dom) / (xmax - xmin)
            if dom and cover > 0.6:
                res['dye_density_neutral'] = K.merge(dom)
                rest = [a for a in rest if not any(a is d for d in dom)]
                notes.append(f'dye plot: visual-neutral (sum) curve kept as dye_density_neutral.csv ({len(dom)} piece(s))')
        groups = defaultdict(list)
        for a in rest:
            inner = a[(a[:, 0] > 415) & (a[:, 0] < 690)]
            inner = inner if len(inner) else a
            pk = inner[np.argmax(inner[:, 1]), 0]
            ch = 'y' if pk < 500 else 'm' if pk < 600 else 'c'
            groups[ch].append(a)
        for ch, parts in groups.items():
            if len(parts) > 1:
                notes.append(f'dye {ch}: {len(parts)} pieces merged (max where they overlap)')
                lo = min(p[0, 0] for p in parts); hi = max(p[-1, 0] for p in parts)
                g = np.linspace(lo, hi, 400)
                vals = np.full((len(parts), g.size), np.nan)
                for k, p in enumerate(parts):
                    sel = (g >= p[0, 0]) & (g <= p[-1, 0])
                    vals[k, sel] = np.interp(g[sel], p[:, 0], p[:, 1])
                ok = np.isfinite(vals).any(0)
                res[f'dye_density_{ch}'] = np.column_stack([g[ok], np.nanmax(vals[:, ok], 0)])
            else:
                res[f'dye_density_{ch}'] = parts[0]
        if stype == 'negative' and any(k in res for k in ('dye_density_c', 'dye_density_m', 'dye_density_y')) and \
                not all(f'dye_density_{c}' in res for c in 'cmy'):
            notes.append(f'dye plot: partial C/M/Y set {sorted(k for k in res if k[-2:] in ("_c","_m","_y"))} ignored')
            for c in 'cmy':
                res.pop(f'dye_density_{c}', None)
    elif kind == 'mtf':
        labs = labels_in(plot, toks, {'R', 'G', 'B', 'Red', 'Green', 'Blue'})
        labs = [dict(l, w=l['w'][0]) for l in labs]
        if len(xys) >= 2 and labs:
            m = assign_by_labels(curves_pt, labs)[0]
            for ch, i in m.items():
                res[f'mtf_{ch.lower()}'] = xys[i]
        else:
            res['mtf'] = K.merge(xys) if xys else None
            if res['mtf'] is None:
                res.pop('mtf')
    return res


def plot_meta(page, plot):
    """Process / densitometry / exposure / sensitivity density printed in the
    plot's caption box. Labels ("Process:") and values are separate text lines
    placed side by side, so values are matched by position (same baseline,
    right of the label)."""
    B = plot['box']
    E = pymupdf.Rect(B.x0 - 30, B.y0 - 30, B.x1 + 40, B.y1 + 40)
    items = [(t.strip(), r) for t, r in K.lines_text(page) if E.intersects(r) and t.strip()]
    keys = {'process:': 'process', 'densitometry:': 'densitometry', 'exposure:': 'exposure',
            'effective exposure:': 'effective_exposure', 'density:': 'sensitivity_density'}
    out = {}
    for t, r in items:
        m = re.match(r'^(Effective Exposure:|Exposure:|Process:|Densitometry:|Density:)\s*(.*)$', t, re.I)
        if not m:
            continue
        key = keys[m.group(1).lower()]
        val = m.group(2).strip()
        if not val:
            cands = [(r2.x0, t2) for t2, r2 in items
                     if abs((r2.y0 + r2.y1) / 2 - (r.y0 + r.y1) / 2) < 3 and r2.x0 > r.x1 - 1
                     and r2.x0 - r.x1 < 120 and not re.search(r':\s*$', t2)]
            if cands:
                val = min(cands)[1]
        if val and key not in out:
            out[key] = val
    return out


COLORS = {'r': (220, 0, 0), 'g': (0, 160, 0), 'b': (0, 60, 255), 'mid': (255, 120, 0), 'min': (160, 0, 200),
          'c': (0, 190, 210), 'm': (220, 0, 180), 'y': (210, 170, 0), 'neutral': (90, 90, 90), 'mtf': (255, 0, 120)}


def render_check(doc, used, path, dpi=110, strip_path=None):
    ims, crops = [], []
    for pn in sorted({u[0] for u in used}):
        page = doc[pn - 1]
        s = dpi / 72
        pix = page.get_pixmap(dpi=dpi)
        im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        dr = ImageDraw.Draw(im)
        for (p2, plot, X, Y, out, (xs, ys)) in used:
            if p2 != pn:
                continue
            B = plot['box']
            dr.rectangle([B.x0 * s, B.y0 * s, B.x1 * s, B.y1 * s], outline=(255, 200, 0))
            for p, v in xs:
                px = float(X.inv(v)) if (not X.log or v > 0) else None
                if px is not None:
                    dr.line([(px * s, (B.y1 + 1) * s), (px * s, (B.y1 + 6) * s)], fill=(255, 0, 255), width=2)
            for p, v in ys:
                py = float(Y.inv(v)) if (not Y.log or v > 0) else None
                if py is not None:
                    dr.line([((B.x0 - 6) * s, py * s), ((B.x0 - 1) * s, py * s)], fill=(255, 0, 255), width=2)
            for fn, xy in out.items():
                key = fn.split('_')[-1]
                col = COLORS.get(key, (255, 0, 0))
                px = X.inv(xy[:, 0]); py = Y.inv(xy[:, 1])
                for i in range(0, len(px), 2):
                    cx, cy = px[i] * s, py[i] * s
                    dr.ellipse([cx - 1.3, cy - 1.3, cx + 1.3, cy + 1.3], fill=col)
        ims.append(im)
        for (p2, plot, *_r) in used:
            if p2 == pn:
                B = plot['box']
                crops.append(im.crop((int((B.x0 - 45) * s), int((B.y0 - 25) * s), int((B.x1 + 25) * s), int((B.y1 + 25) * s))))
    if strip_path and crops:
        h = 260
        crops = [c.resize((int(c.width * h / c.height), h)) for c in crops]
        st = Image.new('RGB', (sum(c.width for c in crops), h), 'white'); x = 0
        for c in crops:
            st.paste(c, (x, 0)); x += c.width
        st.save(strip_path)
    W = sum(i.width for i in ims); H = max(i.height for i in ims)
    out = Image.new('RGB', (W, H), 'white'); x = 0
    for i in ims:
        out.paste(i, (x, 0)); x += i.width
    out.save(path)


def sens_density(stype, meta):
    """Density at which the sheet defines spectral sensitivity, as printed
    (e.g. '0.2 above D-min', 'E.N.D. 1.0'); blank if the sheet does not say."""
    m = meta.get('sens', {})
    d = m.get('sensitivity_density', '')
    dm = m.get('densitometry', '')
    if d and re.fullmatch(r'[\d.]+', d) and re.search(r'E\.?N\.?D', dm):
        return f'E.N.D. {d}'
    if re.fullmatch(r'E\.?N\.?D\.?', d):
        return f'E.N.D. 1.0' if '1.0' in json.dumps(m) else d
    return d


def write_info(folder, sid, name, stype, pdf, date, pub, used_pages, meta, files, calib, notes, superseded):
    L = [name,
         f'Datasheet: Kodak technical data {pub} ({date}), {pdf}.pdf, PDF page(s) {", ".join(map(str, used_pages))}',
         f'Source URL: {source_url(pdf)}',
         f'Publication: {pub}', f'Publication date: {date}']
    if superseded:
        L.append(f'Revision: {superseded}')
    btype = {'negative': 'negative', 'positive': 'positive', 'duplicating': 'positive'}.get(stype, 'paper')
    L += [f'Type: {btype}', f'Material class: {stype}']
    dens = sorted({m.get('densitometry', '') for m in meta.values() if m.get('densitometry')})
    L += [f'Densitometry: {", ".join(dens) or ("Status A" if stype in STATUS_A_TYPES else "Status M")} (as printed on the sheet)',
          f'Process: {", ".join(sorted({m.get("process", "") for m in meta.values() if m.get("process")}))}',
          f'Exposure (characteristic curves): {meta.get("char", {}).get("exposure", "")}',
          f'Sensitivity defined at: {sens_density(stype, meta)}',
          f'Sensitivity effective exposure: {meta.get("sens", {}).get("effective_exposure", "")}',
          '', 'Files (x range, y range, n points):']
    for fn, d in sorted(files.items()):
        L.append(f'  {fn}.csv  x {d["x"][0]}..{d["x"][1]}  y {d["y"][0]}..{d["y"][1]}  n={d["n"]}')
    L += ['',
          'Units: log_sensitivity_* = wavelength nm, log10 sensitivity (sensitivity = 1/exposure in erg/cm2',
          '  giving the specified density, see "Sensitivity defined at"). density_curve_* = log10 H (lux-seconds),',
          '  total density as printed (base+fog included). dye_density_* = wavelength nm, diffuse spectral density',
          '  (c/m/y: individual dyes, normalised as printed; mid: midscale neutral; min: D-min; neutral: the printed',
          '  visual-neutral sum of the dyes). mtf* = cycles/mm, response %.',
          'Extraction: vector strokes read directly from the PDF (pymupdf), axes calibrated from tick labels snapped',
          '  to tick/grid lines (script: scripts/extract_kodak_datasheets.py). Typical accuracy ~0.1-0.3 pt on the',
          '  page (about 0.5-1.5 nm, 0.005-0.015 log H or density) plus the original drawing accuracy.',
          'Calibration:']
    for k, v in calib.items():
        L.append(f'  {k}: {json.dumps(v)}')
    L += ['Caveats:'] + ([f'  {n}' for n in notes] or ['  none'])
    with open(os.path.join(folder, 'info.txt'), 'w') as f:
        f.write('\n'.join(L) + '\n')


def extract_all(pdf_dir, out, chk, only=None):
    for sub in ('negative', 'positive', 'paper', 'other'):
        if os.path.isdir(os.path.join(out, sub)):
            shutil.rmtree(os.path.join(out, sub))
    os.makedirs(os.path.join(chk, 'strips'), exist_ok=True)
    docs, caches = {}, {}
    index, summary = [], {}
    # revision handling: e190-1 supersedes e190 etc.
    stems = {s[3] for s in STOCKS}
    for sid, name, stype, pdf, spec in STOCKS:
        if only and sid not in only and pdf not in only:
            continue
        if pdf not in docs:
            docs[pdf] = pymupdf.open(os.path.join(pdf_dir, pdf + '.pdf'))
            caches[pdf] = {}
        doc = docs[pdf]
        pages = spec.get('pages') or sorted({s[0] for s in spec['sels']})
        for pn in pages:
            if pn not in caches[pdf]:
                pg = doc[pn - 1]
                caches[pdf][pn] = (*K.find_plots(pg), K.curve_drawings(pg), K.axis_lines(pg))
        date, pub = pub_info(doc)
        pub = 'E-' + pdf[1:].split('-')[0].upper()  # the stem is the publication code; -1 = site's revision suffix
        newer = pdf + '-1' in stems
        older = pdf.endswith('-1') and pdf[:-2] in stems
        rev = ''
        if newer:
            rev = f'superseded by {pdf}-1.pdf (newer revision of {pub}); kept for reference'
        elif older:
            rev = f'current revision; supersedes {pdf[:-2]}.pdf'
        bucket = {'negative': 'negative', 'positive': 'positive', 'duplicating': 'other'}.get(stype, 'paper')
        folder_id = f'{sid}_{pub.lower().replace("-", "")}' + ('_' + date.split()[-1] if newer else '')
        folder = os.path.join(out, bucket, folder_id)
        os.makedirs(folder, exist_ok=True)
        notes, files, calib, meta, used = [], {}, {}, {}, []
        for pn, plot in select_plots(doc, spec, caches[pdf]):
            plots, toks, drs, (hl, vl) = caches[pdf][pn]
            kind = plot['head']['kind']
            try:
                X, Y, cinfo, labs = K.calibrate(plot, hl, vl, logx=kind == 'mtf', logy=kind == 'mtf')
            except Exception as e:
                notes.append(f'{kind} p{pn}: calibration failed ({e})'); continue
            for ax_ in 'xy':
                if cinfo.get(f'{ax_}_labels_dropped'):
                    notes.append(f'{kind} p{pn}: {ax_}-axis label(s) {cinfo[f"{ax_}_labels_dropped"]} inconsistent with the scale, ignored')
            # E-55 draws dye curves (cyan, visual neutral) above the top y label, up to the frame top
            top = K.frame_top(plot, vl) if kind in spec.get('frame_top', ()) else None
            if top is not None:
                notes.append(f'{kind} p{pn}: curves read up to the plot frame top (above the highest y label)')
            pcs = K.pieces_in(plot, drs, top=top)
            # sensitivity curves of neighbouring layers touch each other: do not chain them
            curves = chain(pcs)
            res = assign(kind, 'negative' if stype == 'negative' else stype, plot, curves, X, Y, toks, notes)
            calib[f'{kind}_p{pn}'] = cinfo
            meta[kind] = plot_meta(doc[pn - 1], plot)
            for fn, xy in res.items():
                xy = simplify(xy, X, Y)
                K.write_csv(os.path.join(folder, fn + '.csv'), xy, 4, 5) if not fn.startswith('mtf') else \
                    K.write_csv(os.path.join(folder, fn + '.csv'), xy, 3, 3)
                files[fn] = dict(n=len(xy), x=(round(float(xy[0, 0]), 3), round(float(xy[-1, 0]), 3)),
                                 y=(round(float(xy[:, 1].min()), 3), round(float(xy[:, 1].max()), 3)))
            used.append((pn, plot, X, Y, res, labs))
        missing = [f for f in ('log_sensitivity_r', 'log_sensitivity_g', 'log_sensitivity_b',
                               'density_curve_r', 'density_curve_g', 'density_curve_b') if f not in files]
        if missing:
            notes.append(f'MISSING: {missing}')
        write_info(folder, sid, name, stype, pdf, date, pub, sorted({u[0] for u in used}), meta, files, calib, notes, rev)
        render_check(doc, used, os.path.join(chk, f'{folder_id}.png'), strip_path=os.path.join(chk, 'strips', f'{folder_id}.png'))
        row = dict(id=folder_id, stock=sid, name=name, type=stype, folder=os.path.relpath(folder, out), pdf=pdf + '.pdf',
                   publication=pub, date=date, pages=';'.join(map(str, sorted({u[0] for u in used}))),
                   revision=('superseded' if newer else 'current'), files=';'.join(sorted(f + '.csv' for f in files)))
        index.append(row)
        summary[folder_id] = dict(files=files, notes=notes, calib=calib, meta=meta)
        print(folder_id, stype, sorted(files), '|', '; '.join(notes))
    with open(os.path.join(out, 'records.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(index[0].keys()))
        w.writeheader(); w.writerows(index)
    with open(os.path.join(out, 'extraction_summary.json'), 'w') as f:
        json.dump(summary, f, indent=1, default=str)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pdfs', required=True, help='folder holding the downloaded e*.pdf files')
    ap.add_argument('--out', required=True, help='output folder for the raw records')
    ap.add_argument('--checks', default=None, help='overlay check PNG folder (default <out>/_checks)')
    ap.add_argument('--only', default='', help='comma-separated stock ids or pdf stems')
    a = ap.parse_args()
    extract_all(a.pdfs, a.out, a.checks or os.path.join(a.out, '_checks'), {s for s in a.only.split(',') if s})


if __name__ == '__main__':
    main()
