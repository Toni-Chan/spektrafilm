#!/usr/bin/env python
"""Extract vector curve data from the Fujifilm Professional Data Guide (AF3-207U, 2005)
into upstream-spektrafilm-style raw CSV records.

Usage (needs `pip install pymupdf pillow`; the PDF is not shipped with the repository):

    curl -L -o ProfessionalFilmDataGuide.pdf \
        https://asset.fujifilm.com/www/us/files/2020-03/3ab271f46f8d71c7e4c91bcedb7de050/ProfessionalFilmDataGuide.pdf
    python scripts/extract_fujifilm_data_guide.py --pdf ProfessionalFilmDataGuide.pdf \
        --out src/spektrafilm_profile_builder/data/raw/fujifilm_professional_data_guide --checks /tmp/fdg_checks

Output is the record layout read by `spektrafilm_profile_builder` (see its README).

Method: curves are vector strokes in the PDF.  For every plot (grey filled rectangle)
we (1) classify it from the section heading above it, (2) calibrate its axes from the
horizontal tick-label text, snapped to the nearest grid line, with a robust linear fit
(log10 fit for MTF axes), (3) take thick strokes (width >= 0.64 pt) inside the plot,
split them into sub-paths, sample Beziers densely, (4) assign channels by spectral
position / density order / dash style, and (5) write headerless 'x, y' CSVs.
"""
import csv, json, math, os, re, shutil, sys
from collections import defaultdict
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(ROOT, 'guide.pdf')
OUT = os.path.join(ROOT, 'records')
CHK = os.path.join(OUT, '_checks')
REF = 'Fujifilm Professional Data Guide AF3-207U (2005)'
SRC_URL = 'https://asset.fujifilm.com/www/us/files/2020-03/3ab271f46f8d71c7e4c91bcedb7de050/ProfessionalFilmDataGuide.pdf'

# (page, side, type, id, full name, aliases[(id, name)])
STOCKS = [
    (24, 'L', 'positive', 'fujifilm_velvia_50', 'FUJICHROME Velvia for Professionals [RVP] (Velvia 50)', []),
    (24, 'R', 'positive', 'fujifilm_velvia_100', 'FUJICHROME Velvia 100 Professional [RVP100]', []),
    (25, 'L', 'positive', 'fujifilm_velvia_100f', 'FUJICHROME Velvia 100F Professional [RVP100F]', []),
    (25, 'R', 'positive', 'fujifilm_provia_100f', 'FUJICHROME PROVIA 100F Professional [RDPIII]', []),
    (26, 'L', 'positive', 'fujifilm_astia_100f', 'FUJICHROME ASTIA 100F Professional [RAP100F]', []),
    (26, 'R', 'positive', 'fujifilm_provia_400f', 'FUJICHROME PROVIA 400F Professional [RHPIII]', []),
    (27, 'L', 'positive', 'fujifilm_64t_type_ii', 'FUJICHROME 64T TYPE II Professional [RTPII]', []),
    (27, 'R', 'positive', 'fujifilm_sensia_100', 'FUJICHROME Sensia 100 [RA]', []),
    (28, 'L', 'positive', 'fujifilm_sensia_200', 'FUJICHROME Sensia 200 [RM]', []),
    (28, 'R', 'positive', 'fujifilm_sensia_400', 'FUJICHROME Sensia 400 [RH]', []),
    (29, 'L', 'negative', 'fujifilm_pro_160s', 'FUJICOLOR PRO 160S PROFESSIONAL [PRO 160S]', []),
    (29, 'R', 'negative', 'fujifilm_pro_160c', 'FUJICOLOR PRO 160C PROFESSIONAL [PRO 160C]', []),
    (30, 'L', 'negative', 'fujifilm_npl_160', 'FUJICOLOR NPL 160 PROFESSIONAL [NPL]', []),
    (30, 'R', 'negative', 'fujifilm_pro_400h', 'FUJICOLOR PRO 400H PROFESSIONAL [PRO 400H]', []),
    (31, 'L', 'negative', 'fujifilm_pro_800z', 'FUJICOLOR PRO 800Z PROFESSIONAL [PRO 800Z]', []),
    (31, 'R', 'negative', 'fujifilm_superia_reala', 'FUJICOLOR SUPERIA REALA [CS]', []),
    (32, 'L', 'negative', 'fujifilm_superia_100', 'FUJICOLOR SUPERIA 100 [CN]', []),
    (32, 'R', 'negative', 'fujifilm_superia_200', 'FUJICOLOR SUPERIA 200 [CA]', []),
    (33, 'L', 'negative', 'fujifilm_superia_xtra_400', 'FUJICOLOR SUPERIA X-TRA 400 [CH]',
     [('fujifilm_press_400', 'FUJICOLOR PRESS 400 [CH]')]),
    (33, 'R', 'negative', 'fujifilm_true_definition_400', 'FUJICOLOR TRUE DEFINITION 400 [CH]', []),
    (34, 'L', 'negative', 'fujifilm_superia_xtra_800', 'FUJICOLOR SUPERIA X-TRA 800 [CZ]',
     [('fujifilm_press_800', 'FUJICOLOR PRESS 800 [CZ]')]),
    (34, 'R', 'negative', 'fujifilm_superia_1600', 'FUJICOLOR SUPERIA 1600 [CU]', []),
    (40, 'A', 'bw', 'fujifilm_neopan_acros_100', 'NEOPAN 100 ACROS', []),
    (41, 'A', 'bw', 'fujifilm_neopan_400', 'NEOPAN 400 Professional', []),
    (42, 'A', 'bw', 'fujifilm_neopan_1600', 'NEOPAN 1600 Professional', []),
    (53, 'L', 'negative', 'fujifilm_nexia_a200', 'FUJICOLOR nexia A200 [DA] (APS)', []),
    (53, 'R', 'negative', 'fujifilm_nexia_400', 'FUJICOLOR nexia 400 [DH] (APS)', []),
    (54, 'L', 'negative', 'fujifilm_nexia_800', 'FUJICOLOR nexia 800 [DZ] (APS)', []),
]

MID_X = 296.0
CURVE_MIN_W = 0.64
NUM_RE = re.compile(r'^[-\u2212\u2013\u2014]?\d+(\.\d+)?$')
MINUS = '-\u2212\u2013\u2014'


# ---------------------------------------------------------------- text
def page_tokens(page):
    """Horizontal text tokens with bboxes (character-accurate, split on spaces)."""
    toks = []
    raw = page.get_text('rawdict')
    for b in raw['blocks']:
        for l in b.get('lines', []):
            if abs(l['dir'][0] - 1) > 1e-3 or abs(l['dir'][1]) > 1e-3:
                continue
            for s in l['spans']:
                cur = []
                for ch in s['chars'] + [None]:
                    if ch is None or ch['c'].isspace():
                        if cur:
                            t = ''.join(c['c'] for c in cur)
                            x0 = min(c['bbox'][0] for c in cur); x1 = max(c['bbox'][2] for c in cur)
                            y0 = min(c['bbox'][1] for c in cur); y1 = max(c['bbox'][3] for c in cur)
                            toks.append(dict(t=t, x0=x0, x1=x1, y0=y0, y1=y1, size=s['size']))
                        cur = []
                    else:
                        cur.append(ch)
    # glue touching fragments split across spans (e.g. '2.' + '0')
    toks.sort(key=lambda d: (round(d['y0']), d['x0']))
    glued = []
    for t in toks:
        if glued:
            g = glued[-1]
            if abs(g['y0'] - t['y0']) < 1 and -0.3 < t['x0'] - g['x1'] < 0.8 and NUM_RE.match(g['t'] + t['t']):
                g['t'] += t['t']; g['x1'] = t['x1']; g['y1'] = max(g['y1'], t['y1']); continue
        glued.append(dict(t))
    toks = glued
    # merge a lone minus with a following number on the same baseline
    merged, skip = [], set()
    for i, a in enumerate(toks):
        if i in skip:
            continue
        if a['t'] in tuple(MINUS):
            for j, b in enumerate(toks):
                if j != i and j not in skip and abs(b['y0'] - a['y0']) < 2 and 0 <= b['x0'] - a['x1'] < 8 \
                        and NUM_RE.match(b['t']):
                    c = dict(b); c['t'] = '-' + b['t']; c['x0'] = a['x0']
                    merged.append(c); skip.add(j); break
            else:
                merged.append(a)
        else:
            merged.append(a)
    return merged


def num(t):
    t = t.replace('\u2212', '-').replace('\u2013', '-').replace('\u2014', '-')
    return float(t)


def lines_text(page):
    out = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            if l['dir'] != (1.0, 0.0):
                continue
            t = ''.join(s['text'] for s in l['spans']).strip()
            if t:
                out.append((t, pymupdf.Rect(l['bbox'])))
    return out


# ---------------------------------------------------------------- geometry
def bez(p0, p1, p2, p3, n=24):
    t = np.linspace(0, 1, n)[:, None]
    P = [np.array([p.x, p.y]) for p in (p0, p1, p2, p3)]
    return ((1 - t) ** 3) * P[0] + 3 * ((1 - t) ** 2) * t * P[1] + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3]


def subpaths(drawing):
    paths, cur, last = [], [], None
    for it in drawing['items']:
        if it[0] == 'c':
            seg = bez(*it[1:5]); start = it[1]
        elif it[0] == 'l':
            seg = np.linspace([it[1].x, it[1].y], [it[2].x, it[2].y], 6); start = it[1]
        else:
            continue
        cusp = False
        if cur and last is not None:
            prev = cur[-1]
            t0 = prev[-1] - prev[-3]; t1 = seg[2] - seg[0]
            n0, n1 = np.linalg.norm(t0), np.linalg.norm(t1)
            if n0 > 1e-6 and n1 > 1e-6 and np.dot(t0, t1) / (n0 * n1) < -0.5:
                cusp = True  # path doubles back on itself: a new curve drawn from the end of the last
        if last is not None and (math.hypot(start.x - last[0], start.y - last[1]) > 0.3 or cusp):
            paths.append(np.vstack(cur)); cur = []
        cur.append(seg if not cur else seg[1:])
        last = seg[-1]
    if cur:
        paths.append(np.vstack(cur))
    return paths


def is_grey(fill):
    return fill is not None and all(0.75 < c < 0.86 for c in fill) and max(fill) - min(fill) < 0.03


# ---------------------------------------------------------------- calibration
def robust_fit(pos, val, log=False, tol=1.0, weight=None):
    """Consensus fit: try every label pair, keep the line with the most labels within `tol` pt
    (ties -> smaller summed residual), then least-squares refit on those inliers."""
    pos = np.asarray(pos, float); val = np.asarray(val, float)
    weight = np.ones(len(pos)) if weight is None else np.asarray(weight, float)
    if log:
        keep = val > 0; pos, val, weight = pos[keep], np.log10(val[keep]), weight[keep]
    n = len(pos)
    if n < 2:
        raise ValueError('not enough labels')
    best = None
    for i in range(n):
        for j in range(i + 1, n):
            if val[i] == val[j] or abs(pos[i] - pos[j]) < 1:
                continue
            a = (val[j] - val[i]) / (pos[j] - pos[i]); b = val[i] - a * pos[i]
            res = np.abs((val - b) / a - pos)
            inl = np.where(res < tol)[0]
            key = (len(inl), round(weight[inl].sum(), 3), -res[inl].sum())
            if best is None or key > best[0]:
                best = (key, inl)
    idx = best[1]
    A = np.vstack([pos[idx], np.ones(len(idx))]).T
    (a, b), *_ = np.linalg.lstsq(A, val[idx], rcond=None)
    res = np.abs((val[idx] - b) / a - pos[idx])
    return a, b, idx, float(res.max())


class Axis:
    def __init__(self, a, b, log=False, desc=''):
        self.a, self.b, self.log, self.desc = a, b, log, desc

    def __call__(self, p):
        v = self.a * np.asarray(p) + self.b
        return 10 ** v if self.log else v

    def inv(self, v):
        v = np.log10(v) if self.log else np.asarray(v)
        return (v - self.b) / self.a


# ---------------------------------------------------------------- plot discovery
def find_plots(page):
    drs = page.get_drawings()
    texts = lines_text(page)
    heads = [(t, r) for t, r in texts if re.search(r'SENSITIVITY CURVE|DYE DENSITY|CHARACTERISTIC|MTF CURVE|TIME-', t)]
    sizes = [(t, r) for t, r in texts if re.search(r'\[(135|120) Size\]', t)]
    plots = []
    for d in drs:
        if d['type'] in ('f', 'fs') and is_grey(d.get('fill')) and d['rect'].width > 50 and d['rect'].height > 40:
            G = d['rect']
            best = None
            for t, r in heads:
                dy = G.y0 - r.y1
                if -2 < dy < 60 and abs(r.x0 - G.x0) < 60:
                    if best is None or dy < best[0]:
                        best = (dy, t)
            kind = None
            if best:
                t = best[1]
                kind = ('sens' if 'SENSITIVITY' in t else 'dye' if 'DYE' in t else 'char' if 'CHARACTERISTIC' in t
                        else 'mtf' if 'MTF' in t else 'timeg')
            size = None
            for t, r in sizes:
                dy = G.y0 - r.y1
                if 0 < dy < 40 and abs(r.x0 - G.x0) < 60:
                    size = re.search(r'(135|120)', t).group(1)
            plots.append(dict(G=G, kind=kind, size=size))
    # plots without a heading directly above (e.g. B&W '[120 Size]' second plot) inherit the kind
    # of the nearest classified plot above them in the same column
    for p in plots:
        if p['kind'] is None and p['size']:
            above = [q for q in plots if q['kind'] and q['G'].y1 < p['G'].y0 and abs(q['G'].x0 - p['G'].x0) < 20]
            if above:
                p['kind'] = max(above, key=lambda q: q['G'].y1)['kind']
    # grid lines and curve strokes
    hl, vl, strokes = [], [], []
    for d in drs:
        if d['type'] not in ('s', 'fs'):
            continue
        w = d.get('width') or 0
        kinds = {it[0] for it in d['items']}
        if 're' in kinds:
            for it in d['items']:
                if it[0] == 're':
                    R = it[1]; hl += [(R.y0, R.x0, R.x1), (R.y1, R.x0, R.x1)]; vl += [(R.x0, R.y0, R.y1), (R.x1, R.y0, R.y1)]
        if w < CURVE_MIN_W or not d.get('dashes') and False:
            pass
        if w < CURVE_MIN_W:
            for it in d['items']:
                if it[0] == 'l':
                    a, b = it[1], it[2]
                    if abs(a.y - b.y) < 0.2:
                        hl.append((a.y, min(a.x, b.x), max(a.x, b.x)))
                    elif abs(a.x - b.x) < 0.2:
                        vl.append((a.x, min(a.y, b.y), max(a.y, b.y)))
        elif 're' not in kinds:
            strokes.append(d)
    return plots, hl, vl, strokes, drs


def bracket_unit(page_drs, G, hl):
    """Negative/B&W sensitivity plots have no y labels, only a '1.0' bracket (a vertical line
    with arrowheads) left of the plot spanning exactly one grid interval.  Return the two grid
    y positions it spans (lower, upper)."""
    # arrowheads: small filled shapes just left of the plot
    heads = []
    for d in page_drs:
        r = d['rect']
        if d['type'] in ('f', 'fs') and r.width < 4 and r.height < 5 and G.x0 - 16 < (r.x0 + r.x1) / 2 < G.x0 + 1 \
                and G.y0 - 3 < r.y0 and r.y1 < G.y1 + 3 and d.get('fill') and max(d['fill']) < 0.3:
            heads.append(r)
    if len(heads) >= 2:
        y0 = min(r.y0 for r in heads) + 2.5; y1 = max(r.y1 for r in heads) - 2.5
    else:
        cands = []
        for d in page_drs:
            if d['type'] not in ('s', 'fs'):
                continue
            its = d['items']
            if len(its) == 1 and its[0][0] == 'l':
                a, b = its[0][1], its[0][2]
                if abs(a.x - b.x) < 0.2 and G.x0 - 15 < a.x < G.x0 + 1 and 12 < abs(a.y - b.y) < 40:
                    cands.append((min(a.y, b.y), max(a.y, b.y)))
        if not cands:
            return None
        y0, y1 = cands[0]
    hs = sorted({round(y, 2) for y, xa, xb in hl if xa < G.x0 + 10 and xb > G.x1 - 10 and G.y0 - 1 <= y <= G.y1 + 1})
    up = min(hs, key=lambda h: abs(h - (y0 - 2.5)))
    lo = min(hs, key=lambda h: abs(h - (y1 + 2.5)))
    if not (abs(up - y0) < 5 and abs(lo - y1) < 5 and lo > up):
        return None
    return lo, up


def calibrate(plot, toks, hl, vl, drs):
    G = plot['G']; kind = plot['kind']
    log = kind == 'mtf'
    xs, ys = [], []
    for t in toks:
        if not NUM_RE.match(t['t']):
            continue
        cx = (t['x0'] + t['x1']) / 2; cy = (t['y0'] + t['y1']) / 2
        if G.x0 - 24 < t['x1'] < G.x0 + 1 and G.y0 - 7 < cy < G.y1 + 7:
            ys.append((cy, num(t['t'])))
        elif G.y1 - 3 < t['y0'] < G.y1 + 14 and G.x0 - 14 < cx < G.x1 + 14:
            xs.append((cx, num(t['t'])))
    vgrid = sorted({round(x, 2) for x, ya, yb in vl if G.x0 - 1 <= x <= G.x1 + 1 and yb - ya > 0.5 * G.height
                    and ya > G.y0 - 3 and yb < G.y1 + 3})
    hgrid = sorted({round(y, 2) for y, xa, xb in hl if G.y0 - 1 <= y <= G.y1 + 1 and xb - xa > 0.5 * G.width
                    and xa > G.x0 - 12 and xb < G.x1 + 3})
    vgrid = sorted(set(vgrid) | {round(G.x0, 2), round(G.x1, 2)})
    hgrid = sorted(set(hgrid) | {round(G.y0, 2), round(G.y1, 2)})

    frame_x = (round(G.x0, 2), round(G.x1, 2)); frame_y = (round(G.y0, 2), round(G.y1, 2))

    def wt(p, grid, frame):
        g, ok = snap(p, grid)
        return 0.0 if not ok else (0.5 if any(abs(g - f) < 0.6 for f in frame) else 1.0)

    def snap(p, grid):
        if not grid:
            return p, False
        d = np.diff(grid); d = d[d > 1.0]
        tol = float(np.clip(0.45 * np.median(d), 2.0, 8.0)) if len(d) else 3.5
        g = min(grid, key=lambda q: abs(q - p))
        return (g, True) if abs(g - p) < tol else (p, False)

    info = {}
    xp = [snap(p, vgrid)[0] for p, v in xs]
    ax, bx, idx, rx = robust_fit(xp, [v for p, v in xs], log, weight=[wt(p, vgrid, frame_x) for p, v in xs])
    info['x_labels_used'] = [xs[i][1] for i in idx]
    info['x_labels_dropped'] = [xs[i][1] for i in range(len(xs)) if i not in idx]
    info['x_fit_max_resid_pt'] = round(rx, 3)
    X = Axis(ax, bx, log)
    ylog = log
    if kind == 'sens' and len(ys) < 2:
        br = bracket_unit(drs, G, hl)
        if br is None:
            raise ValueError('no y labels and no 1.0 bracket')
        lo, up = br
        ay = 1.0 / (up - lo); by = -ay * lo
        Y = Axis(ay, by)
        info['y_calibration'] = ('relative: one log unit = the grid interval marked by the "1.0" bracket '
                                 f'(y_pt {up:.2f}..{lo:.2f}); zero set at the lower bracket grid line')
    else:
        yp = [snap(p, hgrid)[0] for p, v in ys]
        ay, by, idx, ry = robust_fit(yp, [v for p, v in ys], ylog, weight=[wt(p, hgrid, frame_y) for p, v in ys])
        Y = Axis(ay, by, ylog)
        info['y_labels_used'] = [ys[i][1] for i in idx]
        info['y_labels_dropped'] = [ys[i][1] for i in range(len(ys)) if i not in idx]
        info['y_fit_max_resid_pt'] = round(ry, 3)
        info['y_calibration'] = 'from printed axis labels'
    return X, Y, info, (xs, ys)


# ---------------------------------------------------------------- curve pieces
def dash_style(d):
    ds = d.get('dashes') or ''
    m = re.search(r'\[(.*)\]', ds)
    arr = [float(v) for v in m.group(1).split()] if m else []
    if not arr:
        return 'solid'
    return 'dashdot' if len(arr) >= 4 else 'dashed'


def pieces_in(plot, strokes):
    G = plot['G']
    out = []
    for d in strokes:
        r = d['rect']
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        if not (G.x0 - 3 < cx < G.x1 + 3 and G.y0 - 3 < cy < G.y1 + 3):
            continue
        st = dash_style(d)
        for sp in subpaths(d):
            # clip to the plot frame (with tolerance)
            if np.ptp(sp[:, 0]) < 6 and np.ptp(sp[:, 1]) < 6:
                continue
            out.append(dict(pts=sp, style=st))
    return out


def to_data(pts, X, Y):
    x = X(pts[:, 0]); y = Y(pts[:, 1])
    if x[0] > x[-1]:
        x, y = x[::-1], y[::-1]
    return np.column_stack([x, y])


def monotone(xy):
    keep = [0]
    for i in range(1, len(xy)):
        if xy[i, 0] > xy[keep[-1], 0] + 1e-6:
            keep.append(i)
    return xy[keep]


def merge(parts):
    allp = np.vstack(sorted(parts, key=lambda a: a[0, 0]))
    order = np.argsort(allp[:, 0], kind='stable')
    return monotone(allp[order])


def overlap_mean(a, b):
    lo = max(a[0, 0], b[0, 0]); hi = min(a[-1, 0], b[-1, 0])
    if hi <= lo:
        return a[:, 1].mean() - b[:, 1].mean()
    xs = np.linspace(lo, hi, 50)
    return np.interp(xs, a[:, 0], a[:, 1]).mean() - np.interp(xs, b[:, 0], b[:, 1]).mean()


# ---------------------------------------------------------------- assignment
def assign(plot, pcs, X, Y, stype, toks, notes):
    kind = plot['kind']
    for p in pcs:
        p['xy'] = monotone(to_data(p['pts'], X, Y))
    res = {}
    if kind == 'sens':
        solid = [p for p in pcs if p['style'] == 'solid']
        dashed = [p for p in pcs if p['style'] != 'solid']
        if stype == 'bw':
            res['log_sensitivity'] = merge([p['xy'] for p in solid])
            if len(solid) > 1:
                notes.append(f'B&W sensitivity built from {len(solid)} sub-paths')
        else:
            groups = defaultdict(list)
            for p in solid:
                xy = p['xy']; mid = (xy[0, 0] + xy[-1, 0]) / 2
                ch = 'b' if mid < 495 else 'g' if mid < 590 else 'r'
                groups[ch].append(xy)
            for ch, parts in groups.items():
                if len(parts) > 1:
                    notes.append(f'sensitivity {ch}: merged {len(parts)} sub-paths')
                res[f'log_sensitivity_{ch}'] = merge(parts)
            if dashed:
                res['log_sensitivity_cyan_layer'] = merge([p['xy'] for p in dashed])
    elif kind == 'dye':
        if stype == 'positive':
            groups = defaultdict(list)
            for p in pcs:
                xy = p['xy']; pk = xy[np.argmax(xy[:, 1]), 0]
                ch = 'y' if pk < 500 else 'm' if pk < 600 else 'c'
                groups[ch].append(xy)
            for ch, parts in groups.items():
                if len(parts) > 1:
                    notes.append(f'dye {ch}: merged {len(parts)} sub-paths')
                res[f'dye_density_{ch}'] = merge(parts)
        else:
            xys = sorted([p['xy'] for p in pcs], key=lambda a: -np.ptp(a[:, 0]))
            if len(xys) != 2:
                notes.append(f'dye density plot had {len(xys)} sub-paths (expected 2)')
            a, b = xys[0], xys[1]
            mid, mn = (a, b) if overlap_mean(a, b) > 0 else (b, a)
            res['dye_density_mid'] = mid; res['dye_density_min'] = mn
            for extra in xys[2:]:
                d_mid = abs(overlap_mean(extra, mid)); d_min = abs(overlap_mean(extra, mn))
                tgt = 'dye_density_mid' if d_mid < d_min else 'dye_density_min'
                res[tgt] = merge([res[tgt], extra])
    elif kind == 'char':
        if stype == 'positive':
            by = defaultdict(list)
            for p in pcs:
                by[{'solid': 'r', 'dashdot': 'g', 'dashed': 'b'}[p['style']]].append(p['xy'])
            R = merge(by['r'])
            res['density_curve_r'] = R
            for ch in 'gb':
                if not by[ch]:
                    notes.append(f'char {ch}: no own trace, identical to red (curves coincide)')
                    res[f'density_curve_{ch}'] = R.copy(); continue
                own = merge(by[ch])
                lo, hi = own[0, 0], own[-1, 0]
                ext = [own]
                if R[-1, 0] > hi + 0.02:
                    ext.append(R[R[:, 0] > hi + 1e-6])
                if R[0, 0] < lo - 0.02:
                    ext.append(R[R[:, 0] < lo - 1e-6])
                if len(ext) > 1:
                    notes.append(f'char {ch}: own dashed trace covers logH {lo:.2f}..{hi:.2f}; '
                                 f'outside that range the curves coincide and the shared solid (red) trace is used')
                res[f'density_curve_{ch}'] = merge(ext)
        elif stype == 'negative':
            xys = [p['xy'] for p in pcs]
            if len(xys) != 3:
                notes.append(f'characteristic plot had {len(xys)} sub-paths (expected 3)')
            # order by density: blue highest, red lowest (Status M, C-41 negatives)
            xys = sorted(xys, key=lambda a: -np.mean(a[:, 1]))
            res['density_curve_b'], res['density_curve_g'], res['density_curve_r'] = xys[:3]
        else:  # bw: several development times
            xys = sorted([p['xy'] for p in pcs], key=lambda a: -a[:, 1].max())
            G = plot['G']
            labs = []
            for t in toks:
                if t['t'].startswith('min') and t['x0'] > G.x1 and G.y0 < t['y0'] < G.y1:
                    labs.append(t)
            labs.sort(key=lambda t: t['y0'])
            times = []
            for t in labs:
                pre = [u for u in toks if abs((u['y0'] + u['y1']) / 2 - (t['y0'] + t['y1']) / 2) < 3.5 and u['x1'] <= t['x0'] + 1 and u['x0'] > G.x1]
                pre.sort(key=lambda u: u['x0'])
                s = ''.join(u['t'] for u in pre) + t['t']
                s = s.replace('min.,', '').replace('min.', '').replace(',', '')
                times.append(s)
            res['_times'] = times
            res['_curves'] = xys
    elif kind == 'mtf':
        xys = [p['xy'] for p in pcs]
        res['mtf'] = merge(xys)
    return res


def time_slug(s):
    s = s.strip().replace(' ', '')
    s = s.replace('1/2', '.5').replace('1/4', '.25').replace('3/4', '.75')
    m = re.match(r'(\d+)(\.\d+)?', s)
    if not m:
        return s
    v = float(m.group(1) + (m.group(2) or ''))
    return (f'{v:g}').replace('.', 'p') + 'min'


# ---------------------------------------------------------------- output
def write_csv(path, xy, xdec=4, ydec=5):
    with open(path, 'w', newline='') as f:
        for x, y in xy:
            f.write(f'{x:.{xdec}f}, {y:.{ydec}f}\n')


def half_text(page, side):
    out = []
    for t, r in lines_text(page):
        if side == 'A' or (side == 'L' and r.x0 < MID_X) or (side == 'R' and r.x0 >= MID_X):
            out.append((t, r))
    return out


def meta_from_text(page, side):
    tl = half_text(page, side)
    txt = '\n'.join(t for t, r in sorted(tl, key=lambda q: (q[1].y0, q[1].x0)))
    iso = re.search(r'(ISO|EI) ?\d+/\d+°', txt)
    light = re.search(r'(Daylight|Tungsten) ?Type', txt)
    proc = re.findall(r'Process\s*:\s*([^\n]+)', txt)
    dens = re.findall(r'Densitometry\s*:\s*([^\n]+)', txt)
    gran = re.search(r'VALUE\W*(\d+)', txt)
    exp = re.findall(r'Exposure\s*:\s*([^\n]+)', txt)
    return dict(iso=iso.group(0) if iso else '', light=(light.group(1) if light else ''),
                process=sorted({p.strip() for p in proc}), densitometry=sorted({d.strip() for d in dens}),
                rms_granularity=gran.group(1) if gran else '', exposure=sorted({e.strip().rstrip(',').strip() for e in exp}))


COLORS = {'r': (220, 0, 0), 'g': (0, 160, 0), 'b': (0, 60, 255), 'cyan_layer': (0, 200, 200),
          'mid': (255, 120, 0), 'min': (160, 0, 200), 'c': (0, 190, 210), 'm': (220, 0, 180), 'y': (210, 170, 0),
          'k': (255, 0, 0), 'mtf': (255, 0, 120)}


def main():
    global PDF, OUT, CHK
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pdf', default=PDF, help='path of ProfessionalFilmDataGuide.pdf')
    ap.add_argument('--out', default=OUT, help='output folder for the raw records (replaced)')
    ap.add_argument('--checks', default=None, help='folder for overlay check PNGs (default: <out>/_checks)')
    args = ap.parse_args()
    PDF, OUT = args.pdf, args.out
    CHK = args.checks or os.path.join(OUT, '_checks')
    doc = pymupdf.open(PDF)
    for sub in ('negative', 'positive', 'bw'):
        if os.path.isdir(os.path.join(OUT, sub)):
            shutil.rmtree(os.path.join(OUT, sub))
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CHK, exist_ok=True)
    index_rows, summary = [], {}
    pages = sorted({s[0] for s in STOCKS})
    cache = {}
    for pn in pages:
        page = doc[pn - 1]
        plots, hl, vl, strokes, drs = find_plots(page)
        cache[pn] = (page, plots, hl, vl, strokes, drs, page_tokens(page))

    for (pn, side, stype, sid, name, aliases) in STOCKS:
        page, plots, hl, vl, strokes, drs, toks = cache[pn]
        mine = [p for p in plots if side == 'A' or (side == 'L') == ((p['G'].x0 + p['G'].x1) / 2 < MID_X)]
        mine = [p for p in mine if p['kind'] in ('sens', 'dye', 'char', 'mtf')]
        folder = os.path.join(OUT, stype, sid); os.makedirs(folder)
        notes, files, calib = [], {}, {}
        overlay = []  # (plot, X, Y, {name: xy}, labels)
        for plot in sorted(mine, key=lambda p: (p['G'].y0, p['G'].x0)):
            kind = plot['kind']
            try:
                X, Y, cinfo, labs = calibrate(plot, toks, hl, vl, drs)
            except Exception as e:
                notes.append(f'{kind} plot at {tuple(round(v) for v in plot["G"])}: calibration FAILED ({e})')
                continue
            for ax_ in ('x', 'y'):
                dr_ = cinfo.get(f'{ax_}_labels_dropped')
                if dr_:
                    notes.append(f'{kind}{"_" + plot["size"] if plot["size"] else ""}: {ax_}-axis label(s) {dr_} not '
                                 'consistent with the grid and ignored in calibration (stray/other-axis label or a '
                                 'printed-chart offset; see check PNG)')
            pcs = pieces_in(plot, strokes)
            if not pcs:
                notes.append(f'{kind}: no vector curve strokes found'); continue
            res = assign(plot, pcs, X, Y, stype, toks, notes)
            tag = kind + (f'_{plot["size"]}' if plot['size'] else '')
            calib[tag] = cinfo
            out = {}
            if stype == 'bw' and kind == 'char':
                times, curves = res['_times'], res['_curves']
                if len(times) != len(curves):
                    notes.append(f'char {plot["size"]}: {len(curves)} curves vs {len(times)} time labels')
                for i, xy in enumerate(curves):
                    t = time_slug(times[i]) if i < len(times) else f'curve{i}'
                    fn = f'density_curve_{plot["size"]}_{t}' if plot['size'] else f'density_curve_{t}'
                    out[fn] = xy
                calib[tag]['development_times_top_to_bottom'] = times
            else:
                out = res
            for fn, xy in out.items():
                if fn.startswith('_'):
                    continue
                if fn == 'mtf':
                    write_csv(os.path.join(folder, 'mtf.csv'), xy, 3, 3)
                else:
                    write_csv(os.path.join(folder, fn + '.csv'), xy)
                files[fn] = dict(n=len(xy), x=(round(float(xy[0, 0]), 3), round(float(xy[-1, 0]), 3)),
                                 y=(round(float(xy[:, 1].min()), 3), round(float(xy[:, 1].max()), 3)))
            overlay.append((plot, X, Y, out, labs))
        # B&W default density_curve.csv: 135 size, middle development time
        if stype == 'bw':
            c135 = [f for f in files if f.startswith('density_curve_135_')] or \
                   [f for f in files if re.match(r'density_curve_[\dp]+min$', f)]
            c135 = sorted(c135,
                          key=lambda f: float(f.split('_')[-1].replace('min', '').replace('p', '.')))
            if c135:
                pick = c135[len(c135) // 2]
                shutil.copy(os.path.join(folder, pick + '.csv'), os.path.join(folder, 'density_curve.csv'))
                files['density_curve'] = dict(files[pick], copy_of=pick)
                notes.append(f'density_curve.csv is a copy of {pick}.csv (135 size where sizes differ; middle of the three '
                             'published D-76 development times); all times/sizes are kept as separate files')
        meta = meta_from_text(page, side)
        write_info(folder, name, pn, stype, meta, files, calib, notes, None)
        render_check(doc, pn, side, sid, overlay)
        row = dict(id=sid, name=name, type=stype, folder=os.path.relpath(folder, OUT), page=pn, alias_of='',
                   files=';'.join(sorted(f + '.csv' for f in files)))
        index_rows.append(row)
        summary[sid] = dict(files=files, notes=notes, calib=calib, meta=meta)
        for aid, aname in aliases:
            af = os.path.join(OUT, stype, aid)
            shutil.copytree(folder, af)
            write_info(af, aname, pn, stype, meta, files, calib, notes, (sid, name))
            index_rows.append(dict(row, id=aid, name=aname, folder=os.path.relpath(af, OUT), alias_of=sid))
    with open(os.path.join(OUT, 'index.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['id', 'name', 'type', 'folder', 'page', 'alias_of', 'files'])
        w.writeheader(); w.writerows(index_rows)
    with open(os.path.join(OUT, 'extraction_summary.json'), 'w') as f:
        json.dump(summary, f, indent=1, default=str)
    print('stocks:', len(index_rows), 'out:', OUT)
    for sid, s in summary.items():
        print(sid, sorted(s['files']), '|', '; '.join(s['notes']))


def write_info(folder, name, pn, stype, meta, files, calib, notes, alias):
    L = [name,
         f'Datasheet: {REF}, PDF page {pn}',
         f'Source URL: {SRC_URL}']
    if alias:
        L.append(f'Alias: the guide publishes one shared data set for this stock and {alias[1]} '
                 f'(folder {alias[0]}); files are identical copies.')
    L += [f'Type: {stype}',
          f'Speed: {meta["iso"]}', f'Light type: {meta["light"] or ("Daylight (5400K spectrogram)" if stype=="bw" else "")}',
          f'Process: {", ".join(meta["process"]) or ("D-76, small tank, 20C" if stype=="bw" else "")}',
          f'Densitometry: {", ".join(meta["densitometry"]) or ("visual/diffuse (not stated)" if stype=="bw" else "")}',
          f'Exposure (as printed): {", ".join(meta["exposure"])}',
          f'Diffuse RMS granularity (as printed): {meta["rms_granularity"]}',
          '',
          'Files (x range, y range, n points):']
    for fn, d in sorted(files.items()):
        L.append(f'  {fn}.csv  x {d["x"][0]}..{d["x"][1]}  y {d["y"][0]}..{d["y"][1]}  n={d["n"]}'
                 + (f'  (copy of {d["copy_of"]}.csv)' if 'copy_of' in d else ''))
    L += ['',
          'Units: log_sensitivity_* = wavelength nm, log10 relative sensitivity (sensitivity = 1/exposure in J/cm2',
          '  giving the specified density above D-min, see page). density_curve_* = log10 H (lux-seconds), density.',
          '  dye_density_* = wavelength nm, spectral diffuse density. mtf.csv = cycles/mm, response %.',
          'Extraction: vector strokes read directly from the PDF (pymupdf), axes calibrated from tick labels',
          '  snapped to grid lines (script: scripts/extract_fujifilm_data_guide.py). Typical accuracy ~0.1-0.2 pt on the page',
          '  (about 0.5-1 nm, 0.005-0.01 log H, 0.005-0.01 density) plus the original drawing accuracy.',
          'Calibration:']
    for k, v in calib.items():
        L.append(f'  {k}: {json.dumps(v)}')
    L += ['Caveats:']
    if stype != 'bw':
        L.append('  density curves are total densities as printed (base/fog NOT subtracted).')
    L += [f'  {n}' for n in notes] or ['  none']
    with open(os.path.join(folder, 'info.txt'), 'w') as f:
        f.write('\n'.join(L) + '\n')


def render_check(doc, pn, side, sid, overlay, dpi=200):
    page = doc[pn - 1]
    clip = pymupdf.Rect(0, 40, MID_X + 5, 538) if side == 'L' else (
        pymupdf.Rect(MID_X - 5, 40, 592, 538) if side == 'R' else pymupdf.Rect(0, 40, 592, 538))
    s = dpi / 72
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    dr = ImageDraw.Draw(im)

    def P(x, y):
        return ((x - clip.x0) * s, (y - clip.y0) * s)

    for plot, X, Y, out, (xs, ys) in overlay:
        G = plot['G']
        # calibration ticks: magenta marks at each label value
        for p, v in xs:
            px = float(X.inv(v)) if (not X.log or v > 0) else None
            if px is None:
                continue
            a = P(px, G.y1 + 1); b = P(px, G.y1 + 6)
            dr.line([a, b], fill=(255, 0, 255), width=2)
        for p, v in ys:
            py = float(Y.inv(v)) if (not Y.log or v > 0) else None
            if py is None:
                continue
            a = P(G.x0 - 6, py); b = P(G.x0 - 1, py)
            dr.line([a, b], fill=(255, 0, 255), width=2)
        for fn, xy in out.items():
            if fn.startswith('_'):
                continue
            key = 'cyan_layer' if fn.endswith('cyan_layer') else fn.split('_')[-1]
            if fn.startswith('density_curve_') and len(fn.split('_')) > 3:
                key = 'k'
            col = COLORS.get(key, (255, 0, 0))
            px = X.inv(xy[:, 0]); py = Y.inv(xy[:, 1])
            for i in range(0, len(px), 2):
                cx, cy = P(px[i], py[i])
                dr.ellipse([cx - 1.6, cy - 1.6, cx + 1.6, cy + 1.6], fill=col)
    im.save(os.path.join(CHK, f'{sid}.png'))


if __name__ == '__main__':
    main()
