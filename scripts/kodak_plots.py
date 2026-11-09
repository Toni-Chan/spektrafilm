"""Plot discovery and curve extraction for Kodak technical-data PDFs (E-series, 1997-2003).

Kodak data sheets draw curves as vector polylines; plot frames vary (full box, grid, or
only tick marks), so plots are located from their numeric tick labels: a column of
right-aligned numbers (y axis) and a row of numbers (x axis) under a section heading.
"""
import importlib.util, math, os, re
from collections import defaultdict
import numpy as np
import pymupdf

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('_fdg', os.path.join(_here, 'extract_fujifilm_data_guide.py'))
_fdg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_fdg)
page_tokens, lines_text, subpaths, robust_fit, Axis, monotone, merge, write_csv, num, NUM_RE = (
    _fdg.page_tokens, _fdg.lines_text, _fdg.subpaths, _fdg.robust_fit, _fdg.Axis, _fdg.monotone, _fdg.merge,
    _fdg.write_csv, _fdg.num, _fdg.NUM_RE)

HEAD_RE = re.compile(r'(charac\w*\s+curves?|spectral[- ]+sensitivity\s+curves?|spectral[- ]+dye[- ]+density'
                     r'|modulation[- ]+transfer|^mtf\b)', re.I)


def kind_of(text):
    t = text.lower()
    if 'charac' in t: return 'char'
    if 'sensitivity' in t: return 'sens'
    if 'dye' in t: return 'dye'
    return 'mtf'


def headings(page):
    out = []
    lt = lines_text(page)
    for i, (t, r) in enumerate(lt):
        m = HEAD_RE.search(t)
        if not m:
            continue
        # skip running text mentions (body font, long lines)
        if len(t) > 70:
            continue
        sub = []
        for t2, r2 in lt:
            if 0 <= r2.y0 - r.y1 < 12 and abs((r2.x0 + r2.x1) / 2 - (r.x0 + r.x1) / 2) < 60 and t2 != t:
                sub.append(t2)
        out.append(dict(text=t, rect=r, kind=kind_of(t), sub=' '.join(sub[:2])))
    # de-duplicate (same heading split in two text lines)
    ded = []
    for h in sorted(out, key=lambda h: (h['rect'].y0, h['rect'].x0)):
        if ded and ded[-1]['kind'] == h['kind'] and abs(ded[-1]['rect'].y0 - h['rect'].y0) < 14 \
                and abs(ded[-1]['rect'].x0 - h['rect'].x0) < 80:
            continue
        ded.append(h)
    return ded


def _num_tokens(toks):
    out = []
    for t in toks:
        if NUM_RE.match(t['t']):
            out.append(dict(t, v=num(t['t']), cx=(t['x0'] + t['x1']) / 2, cy=(t['y0'] + t['y1']) / 2))
    return out


def _groups(items, key, tol):
    items = sorted(items, key=key)
    gs = []
    for it in items:
        if gs and abs(key(it) - key(gs[-1][-1])) < tol:
            gs[-1].append(it)
        else:
            gs.append([it])
    return gs


def fix_bar_notation(vals):
    """Kodak log-exposure axes written with bar notation (4̄.0 3̄.0 ... 0.0 1.0): values left of the
    minimum are negative characteristic digits."""
    v = list(vals)
    if all(b > a for a, b in zip(v, v[1:])):
        return v, False
    k = int(np.argmin(v))
    if k > 0 and all(a > b for a, b in zip(v[:k + 1], v[1:k + 1])) and all(b > a for a, b in zip(v[k:], v[k + 1:])):
        out = []
        for i, x in enumerate(v):
            if i < k or (i == k and x != 0 and False):
                ip = math.floor(x); fr = x - ip
                out.append(-ip + fr)
            else:
                out.append(x)
        return out, True
    return v, False


def _round_steps(vals):
    """Axis labels of a linear scale step by a round amount (0.1, 0.2, 0.25, 0.5, 1, 2, 5 x 10^n)."""
    v = np.sort(np.asarray(vals, float))
    d = np.diff(v)
    if len(d) == 0 or np.any(d <= 0):
        return False
    st = d.min()
    e = 10 ** np.floor(np.log10(st))
    if not any(abs(st / e - r) < 1e-6 for r in (1, 2, 2.5, 5)):
        return False
    return bool(np.all(np.abs(d / st - np.round(d / st)) < 1e-6))


def axis_score(g, pos, vertical, allow_log=True):
    """(number of labels on one linear or log scale, their indices) for a candidate label group."""
    g = sorted(g, key=lambda t: t[pos])
    p = [t[pos] for t in g]
    v = [t['v'] for t in g]
    vv = v[::-1] if vertical else v
    vv, _ = fix_bar_notation(vv)
    v = vv[::-1] if vertical else vv
    best = (0, [])
    for log in ((False, True) if allow_log else (False,)):
        try:
            a, b, idx, res = robust_fit(p, v, log, tol=1.6)
        except Exception:
            continue
        if (vertical and a >= 0) or (not vertical and a <= 0):
            continue
        if not log and not _round_steps([v[i] for i in idx]):
            continue
        if len(idx) > best[0]:
            best = (len(idx), list(idx))
    return best


def find_plots(page):
    heads = headings(page)
    toks = page_tokens(page)
    nums = _num_tokens(toks)
    W = page.rect.width
    plots = []
    for h in heads:
        r = h['rect']; cx = (r.x0 + r.x1) / 2
        below = [g for g in heads if g is not h and g['rect'].y0 > r.y1 + 5 and abs((g['rect'].x0 + g['rect'].x1) / 2 - cx) < 150]
        ybot = min([g['rect'].y0 for g in below] + [r.y1 + 330])
        half = 150 if W < 700 else 200
        cand = [t for t in nums if r.y1 - 2 < t['cy'] < ybot and cx - half - 40 < t['cx'] < cx + half + 20]
        # y-label column: right-aligned numbers; x-label row: numbers on one baseline, split at big gaps
        cols = [g for g in _groups(cand, lambda t: t['x1'], 2.0) if len(g) >= 3 and np.ptp([t['cy'] for t in g]) > 40]
        cols = [(axis_score(g, 'cy', True, h['kind'] == 'mtf'), g) for g in cols]
        cols = [(sc, g) for sc, g in cols if sc[0] >= 3]
        if not cols:
            plots.append(dict(head=h, ok=False, why='no y column'))
            continue
        sc, col = sorted(cols, key=lambda c: (-c[0][0], abs((min(t['x0'] for t in c[1])) - (r.x0 - 40))))[0]
        col = [t for i, t in enumerate(sorted(col, key=lambda t: t['cy'])) if i in sc[1]]
        ytop = min(t['cy'] for t in col); ybot2 = max(t['cy'] for t in col)
        x0c = min(t['x0'] for t in col)
        rows = []
        for g in _groups([t for t in cand if t['x0'] > x0c - 15 and t['cy'] > ytop + 20], lambda t: t['y0'], 1.5):
            g = sorted(g, key=lambda t: t['cx'])
            run = [g[0]]
            gaps = np.diff([t['cx'] for t in g])
            lim = max(75.0, 2.2 * float(np.median(gaps))) if len(gaps) else 75.0
            for t in g[1:]:
                if t['cx'] - run[-1]['cx'] > lim:
                    rows.append(run); run = []
                run.append(t)
            rows.append(run)
        rows = [g for g in rows if len(g) >= 3 and np.ptp([t['cx'] for t in g]) > 60]
        rows = [(axis_score(g, 'cx', False, h['kind'] == 'mtf'), g) for g in rows]
        rows = [(sc_, g) for sc_, g in rows if sc_[0] >= 3]
        rows2 = [(s2, g) for s2, g in rows if min(t['cy'] for t in g) > ytop + 20 and min(t['x0'] for t in g) > x0c - 15
                 and min(t['cx'] for t in g) < x0c + 60]
        if not rows2:
            plots.append(dict(head=h, ok=False, why='no x row')); continue
        s2, row = sorted(rows2, key=lambda c: (abs(np.mean([t['cy'] for t in c[1]]) - ybot2), -c[0][0]))[0]
        row = [t for i, t in enumerate(sorted(row, key=lambda t: t['cx'])) if i in s2[1]]
        col = sorted(col, key=lambda t: t['cy'])
        row = [t for t in row if t not in col]
        plots.append(dict(head=h, ok=True, xl=row, yl=col, row_y=min(t['y0'] for t in row),
                          box=pymupdf.Rect(min(t['cx'] for t in row), min(t['cy'] for t in col),
                                           max(t['cx'] for t in row), max(t['cy'] for t in col))))
    return plots, toks


def axis_lines(page):
    hl, vl = [], []
    for d in page.get_drawings():
        if d['type'] not in ('s', 'fs'):
            continue
        for it in d['items']:
            if it[0] == 'l':
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 0.2 and abs(a.x - b.x) > 1:
                    hl.append((a.y, min(a.x, b.x), max(a.x, b.x)))
                elif abs(a.x - b.x) < 0.2 and abs(a.y - b.y) > 1:
                    vl.append((a.x, min(a.y, b.y), max(a.y, b.y)))
            elif it[0] == 're':
                R = it[1]
                hl += [(R.y0, R.x0, R.x1), (R.y1, R.x0, R.x1)]; vl += [(R.x0, R.y0, R.y1), (R.x1, R.y0, R.y1)]
    return hl, vl


def calibrate(plot, hl, vl, logx=False, logy=False):
    B = plot['box']
    xs = [(t['cx'], t['v']) for t in plot['xl']]
    ys = [(t['cy'], t['v']) for t in plot['yl']]
    info = {}
    xv, bar = fix_bar_notation([v for p, v in xs])
    if bar:
        info['x_bar_notation'] = True
        xs = [(p, v) for (p, _), v in zip(xs, xv)]
    yv, ybar = fix_bar_notation([v for p, v in ys][::-1])
    if ybar:
        info['y_bar_notation'] = True
        ys = [(p, v) for (p, _), v in zip(ys, yv[::-1])]
    # snap label centres to tick / grid lines near the axis
    vticks = [x for x, y0, y1 in vl if B.x0 - 4 < x < B.x1 + 4 and y1 > B.y1 - 12 and y0 < B.y1 + 2]
    hticks = [y for y, x0, x1 in hl if B.y0 - 4 < y < B.y1 + 4 and x0 < B.x0 + 14 and x1 > B.x0 - 30]

    def snap(p, grid, tol=2.6):
        if not grid:
            return p, 0.3
        g = min(grid, key=lambda q: abs(q - p))
        return (g, 1.0) if abs(g - p) < tol else (p, 0.3)

    sx = [snap(p, vticks) for p, v in xs]; sy = [snap(p, hticks) for p, v in ys]
    ax, bx, idx, rx = robust_fit([s[0] for s in sx], [v for p, v in xs], logx, weight=[s[1] for s in sx])
    info['x_labels_used'] = [xs[i][1] for i in idx]
    info['x_labels_dropped'] = [xs[i][1] for i in range(len(xs)) if i not in idx]
    info['x_fit_max_resid_pt'] = round(rx, 3)
    info['x_snapped_to_ticks'] = int(sum(s[1] == 1.0 for s in sx))
    ay, by, idy, ry = robust_fit([s[0] for s in sy], [v for p, v in ys], logy, weight=[s[1] for s in sy])
    info['y_labels_used'] = [ys[i][1] for i in idy]
    info['y_labels_dropped'] = [ys[i][1] for i in range(len(ys)) if i not in idy]
    info['y_fit_max_resid_pt'] = round(ry, 3)
    info['y_snapped_to_ticks'] = int(sum(s[1] == 1.0 for s in sy))
    return Axis(ax, bx, logx), Axis(ay, by, logy), info, (xs, ys)


def curve_drawings(page, min_w=0.6):
    out = []
    for d in page.get_drawings():
        if d['type'] not in ('s', 'fs') or (d.get('width') or 0) < min_w:
            continue
        diag = 0
        for it in d['items']:
            if it[0] == 'c':
                diag += 1
            elif it[0] == 'l':
                a, b = it[1], it[2]
                if abs(a.x - b.x) > 0.05 and abs(a.y - b.y) > 0.05:
                    diag += 1
        n = sum(1 for it in d['items'] if it[0] in ('l', 'c'))
        if diag >= (3 if d['type'] == 's' else 1) and diag > 0.5 * n:  # grid/tick drawings are (almost) all axis-aligned
            out.append(d)
    return out


def pieces_in(plot, drawings, margin=8):
    B = plot['box']
    E = pymupdf.Rect(B.x0 - margin, B.y0 - 2 * margin, B.x1 + margin, max(B.y1 + margin, plot.get('row_y', B.y1) - 1))
    out = []
    for d in drawings:
        for sp in subpaths(d):
            if np.ptp(sp[:, 0]) < 1.0 and np.ptp(sp[:, 1]) < 5:
                continue
            inside = (sp[:, 0] > E.x0) & (sp[:, 0] < E.x1) & (sp[:, 1] > E.y0) & (sp[:, 1] < E.y1)
            if inside.mean() < 0.8:
                continue
            q = sp[inside]
            chord = q[-1] - q[0]; L = float(np.hypot(*chord))
            if L > 0:
                dev = np.abs(chord[0] * (q[:, 1] - q[0, 1]) - chord[1] * (q[:, 0] - q[0, 0])) / L
                if dev.max() < 0.15 and (L > 0.6 * np.hypot(B.width, B.height)
                                         or abs(chord[0]) < 0.2 or abs(chord[1]) < 0.2):
                    continue  # tick mark, axis line or a stray straight construction line
            seg = np.diff(q, axis=0)
            sl = np.hypot(seg[:, 0], seg[:, 1])
            if sl.sum() > 0.5 * (B.width + B.height):
                aligned = np.minimum(np.abs(seg[:, 0]), np.abs(seg[:, 1])) < 0.05 * np.maximum(np.abs(seg[:, 0]), np.abs(seg[:, 1]))
                if sl[aligned].sum() > 0.95 * sl.sum():
                    continue  # a frame / outline made of horizontal and vertical lines
            out.append(dict(pts=q, width=d.get('width'), dashes=d.get('dashes')))
    return out
