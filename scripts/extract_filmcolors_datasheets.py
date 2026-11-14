#!/usr/bin/env python
"""Digitise data-sheet curves catalogued by filmcolors.org (Timeline of Historical Film Colors,
https://filmcolors.org/cat/Data-sheets/) into spektrafilm_profile_builder raw records.

Usage (needs `pip install pymupdf pillow scipy`; the PDFs are not shipped with the repository —
download them from the URLs in sheets/*.json):

    python scripts/extract_filmcolors_datasheets.py --pdfs filmcolors_pdfs \
        [--raw src/spektrafilm_profile_builder/data/raw/filmcolors_data_sheets] [--checks /tmp/checks] [--only af3-796e]

Most of these sheets (Fujifilm AF3-* data sheets of the 1990s-2000s, the 2019 KODAK H-1-5294 sheet)
carry their curves as embedded 1-bit or colour scans, often with the axis labels inside the bitmap,
so the vector readers used for the Fujifilm Data Guide and the KODAK E-series sheets do not apply.
This script renders each plot at 600 dpi and digitises the raster:

1. grid / frame lines: rows and columns whose dark-pixel count exceeds half the plot extent; their
   pixels are cleared except where the run across the line is thicker than the line (a curve
   crossing it), so curves stay connected through the grid;
2. axes: piecewise-linear through the grid lines named in the sheet config (`x`/`y`:
   [value, approximate page position in pt], snapped to the nearest detected line), which absorbs
   the small scale non-uniformity of scanned bitmaps;
3. curves: followed column by column from seed points given in the config (data units), taking the
   run centre (an isolated stroke, steep or flat) or the linear prediction clamped into the run
   (merged strokes at crossings), bridging dashes and gaps; text blocks are masked by rectangles
   (`mask`, data units) or dropped as small connected components (`min_component`, px). Seeds are
   points `[x, y(, xmin, xmax)]`, `{"col": x, "rank": k}` (k-th stroke from the top in that column),
   or `{"row": y, "rank": k, "ylim": [..]}` (k-th stroke from the left, traced as x(y) for steep
   stretches where overlapping characteristic curves are ordered left to right); a curve with `rgb`
   (and `rgb_tol`) is traced only through pixels of that colour (colour-printed curves that cross); a curve with
   `fill` takes another curve's points outside its own traced range (status-A curves that coincide
   on the sheet). Sheets whose curves are vector art use `{"path": [drawing, sub-path]}` seeds,
   which read the PDF path directly (no tracing) and share the same axis calibration;
4. points are binned (4 px = 0.5 pt), lightly smoothed and simplified (0.35 px), then written as
   headerless 'x, y' CSVs; overlay check sheets (600 dpi) and the distance of every written curve to
   the printed strokes are reported.

Sheet configs also carry the stock metadata and the builder recipe (estimate placeholders listed);
records.csv, recipes.csv and extraction_summary.json are rewritten from all configs.

The same reader serves data sheets that filmcolors.org does not catalogue (`--raw` pointing at another
raw folder, e.g. fujifilm_motion_picture_data_sheets; `entry` is then omitted). Further config options:
`"derotate": true` (sheet; pages stored rotated, read in their displayed orientation), `"dense_lines": true`
(plot; straight vector segments sampled densely so that binning does not bend them), `"borrow"` (stock; a
sheet that prints only some plots takes the missing curves from a sibling record, listed as estimates),
and `"use"` in the recipe (e.g. "cine").
"""
import argparse, csv, glob, json, math, os, shutil, sys
import numpy as np
import pymupdf
from PIL import Image, ImageDraw
from scipy import ndimage

DPI = 600


def render(pdf, page, rect, dpi=DPI, rgb=False):
    doc = pymupdf.open(pdf) if isinstance(pdf, str) else pdf
    pg = doc[page - 1]
    pix = pg.get_pixmap(dpi=dpi, clip=pymupdf.Rect(*rect), colorspace=pymupdf.csRGB if rgb else pymupdf.csGRAY)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    return a if rgb else a[..., 0]


def _clusters(idx):
    out = []
    for i in idx:
        if out and i - out[-1][-1] <= 1:
            out[-1].append(i)
        else:
            out.append([i])
    return [(float(np.mean(c)), len(c)) for c in out]


def detect_lines(dark, frac=0.55):
    """Long horizontal / vertical dark lines (grid + frame): rows/cols whose longest dark run covers
    `frac` of the image extent.  Returns lists of (centre_px, thickness_px)."""
    H, W = dark.shape
    rh = dark.sum(1).astype(float); rv = dark.sum(0).astype(float)
    h = _clusters(np.where(rh > frac * W)[0]); v = _clusters(np.where(rv > frac * H)[0])
    return h, v


class Axis:
    """pixel -> data.  Linear least-squares fit of the label positions, or (piecewise=True, for
    scanned bitmaps whose scale is not perfectly uniform) piecewise-linear through them, continued
    with the end segments."""
    def __init__(self, pairs, log=False, piecewise=False):
        p = np.array([q[1] for q in pairs], float); val = np.array([q[0] for q in pairs], float)
        self.log = log
        if log:
            val = np.log10(val)
        o = np.argsort(p); self.p, self.v = p[o], val[o]
        A = np.vstack([p, np.ones_like(p)]).T
        (self.a, self.b), *_ = np.linalg.lstsq(A, val, rcond=None)
        self.resid = float(np.max(np.abs(A @ [self.a, self.b] - val) / abs(self.a))) if len(p) > 2 else 0.0
        self.piecewise = piecewise and len(p) >= 3

    def _fwd(self, px):
        px = np.asarray(px, float)
        if not self.piecewise:
            return self.a * px + self.b
        p, v = self.p, self.v
        out = np.interp(px, p, v)
        lo = px < p[0]; hi = px > p[-1]
        out = np.where(lo, v[0] + (px - p[0]) * (v[1] - v[0]) / (p[1] - p[0]), out)
        out = np.where(hi, v[-1] + (px - p[-1]) * (v[-1] - v[-2]) / (p[-1] - p[-2]), out)
        return out

    def _inv(self, val):
        val = np.asarray(val, float)
        if not self.piecewise:
            return (val - self.b) / self.a
        p, v = self.p, self.v
        if v[0] > v[-1]:
            p2, v2 = p[::-1], v[::-1]
        else:
            p2, v2 = p, v
        out = np.interp(val, v2, p2)
        lo = val < v2[0]; hi = val > v2[-1]
        out = np.where(lo, p2[0] + (val - v2[0]) * (p2[1] - p2[0]) / (v2[1] - v2[0]), out)
        out = np.where(hi, p2[-1] + (val - v2[-1]) * (p2[-1] - p2[-2]) / (v2[-1] - v2[-2]), out)
        return out

    def __call__(self, px):
        v = self._fwd(px)
        return 10 ** v if self.log else v

    def inv(self, v):
        v = np.log10(v) if self.log else np.asarray(v, float)
        return self._inv(v)


def snap(cal, lines, origin_pt, s, tol_pt=3.0):
    """cal: [[value, approx_pt], ...] -> [[value, px], ...] snapped to detected lines."""
    out, notes = [], []
    for val, pt in cal:
        px = (pt - origin_pt) * s
        if lines:
            c = min(lines, key=lambda l: abs(l[0] - px))
            if abs(c[0] - px) <= tol_pt * s:
                out.append([val, c[0]]); continue
        notes.append(f'label {val}: no grid line within {tol_pt} pt of {pt}; used as given')
        out.append([val, px])
    return out, notes


def column_runs(mask):
    """per column: array of (start,end) dark runs (inclusive start, exclusive end)."""
    m = np.pad(mask.astype(np.int8), ((1, 1), (0, 0)))
    d = np.diff(m, axis=0)
    cols = []
    for x in range(mask.shape[1]):
        s = np.where(d[:, x] == 1)[0]; e = np.where(d[:, x] == -1)[0]
        cols.append(np.column_stack([s, e]) if len(s) else np.zeros((0, 2), int))
    return cols


def track(runs, seed, stroke, x_lo, x_hi, tol=None, gap=60, hist=30, direction=+1, valid=None, y_lo=None, y_hi=None):
    """Follow one curve y(x) from seed=(x, y) px in `direction`, column by column.

    In each column the dark run nearest a linear prediction (fit to the last `hist` hits) is taken.
    The curve point is the run centre when the run is no longer than one stroke crossing the column
    at the predicted slope explains (exact for an isolated stroke, steep or flat); a longer run
    (curves merged at a crossing, a touching label) gives the prediction clamped into the run, so
    the curve goes straight through the crossing.  When no run is near the prediction but a run
    touches the previous column's run, the curve has turned sharply (e.g. a flat top falling into a
    steep edge) and that run's centre is taken.  Gaps (dashes, removed grid pixels) are bridged
    for up to `gap` columns.  Returns [(x, y), ...] (hits only)."""
    tol = tol or max(4.0, 2.5 * stroke)
    x0, y0 = seed
    pts = [(x0, y0)]
    misses = 0
    x = int(x0)
    prev = None
    while True:
        x += direction
        if x < x_lo or x > x_hi:
            break
        P = np.array(pts[-hist:])
        if len(P) >= 3 and np.ptp(P[:, 0]) > 0:
            w = np.linspace(0.3, 1.0, len(P))
            k, c = np.polyfit(P[:, 0], P[:, 1], 1, w=w)
            pred = k * x + c
        else:
            k = 0.0; pred = pts[-1][1]
        ka = min(abs(k), 40.0)
        if y_lo is not None and (pred < y_lo - 2 * stroke or pred > y_hi + 2 * stroke):
            break
        best = None
        tl = tol + 1.5 * ka + min(misses, 20) * 0.3 * (1 + min(ka, 3))
        for s0, e0 in runs[x]:
            lo, hi = s0, e0 - 1
            L = hi - lo + 1
            if L > 1.6 * stroke + ka + 3:
                y = min(max(pred, lo + stroke / 2), hi - stroke / 2)
            else:
                y = (lo + hi) / 2
            d = max(lo - pred, pred - hi, 0.0)
            if d <= tl:
                sc = abs(y - pred)
                if best is None or sc < best[0]:
                    best = (sc, y, (lo, hi))
        if best is None and prev is not None and misses == 0:
            for s0, e0 in runs[x]:
                lo, hi = s0, e0 - 1
                if lo <= prev[1] + 1 and hi >= prev[0] - 1:
                    y = (lo + hi) / 2
                    sc = max(lo - pred, pred - hi, 0.0)
                    if best is None or sc < best[0]:
                        best = (sc, y, (lo, hi))
        if best is None:
            misses += 1
            prev = None
            if misses > gap:
                break
            continue
        misses = 0
        prev = best[2]
        pts.append((x, best[1]))
    return pts


def trace(runs, seed, stroke, x_lo, x_hi, **kw):
    left = track(runs, seed, stroke, x_lo, x_hi, direction=-1, **kw)
    right = track(runs, seed, stroke, x_lo, x_hi, direction=+1, **kw)
    pts = left[::-1] + right[1:]
    return np.array(pts, float)


def snap_seed(runs, seed, stroke, win=12):
    x, y = int(round(seed[0])), seed[1]
    best = None
    for dx in range(-win, win + 1):
        xx = x + dx
        if xx < 0 or xx >= len(runs):
            continue
        for s0, e0 in runs[xx]:
            yy = min(max(y, s0), e0 - 1)
            d = abs(yy - y) + 0.3 * abs(dx)
            if best is None or d < best[0]:
                best = (d, xx, (s0 + e0 - 1) / 2 if e0 - s0 <= 2.2 * stroke else yy)
    if best is None or best[0] > 25:
        raise ValueError(f'no curve stroke near seed {seed}')
    return best[1], best[2]




COL = {'r': (230, 0, 0), 'g': (0, 170, 0), 'b': (0, 60, 255), 'c': (0, 190, 210), 'm': (230, 0, 200),
       'y': (230, 170, 0), 'mid': (255, 120, 0), 'min': (160, 0, 200), 'neutral': (120, 120, 120), 'layer': (0, 120, 120)}


def rdp(P, tol):
    if len(P) < 3:
        return np.arange(len(P))
    keep = np.zeros(len(P), bool); keep[[0, -1]] = True
    st = [(0, len(P) - 1)]
    while st:
        i, j = st.pop()
        if j <= i + 1:
            continue
        a, b = P[i], P[j]; d = b - a; L = np.hypot(*d)
        seg = P[i + 1:j] - a
        dist = np.abs(seg[:, 0] * d[1] - seg[:, 1] * d[0]) / L if L > 0 else np.hypot(seg[:, 0], seg[:, 1])
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = i + 1 + k; keep[m] = True; st += [(i, m), (m, j)]
    return np.where(keep)[0]


def clean(pts, binw=4):
    """pixel trace -> binned median (binw px), light smoothing, endpoints kept."""
    pts = pts[np.argsort(pts[:, 0], kind='stable')]
    xb = np.floor(pts[:, 0] / binw)
    ux = np.unique(xb)
    out = np.array([[pts[xb == u, 0].mean(), np.median(pts[xb == u, 1])] for u in ux])
    if len(out) > 4:
        y = out[:, 1].copy()
        out[1:-1, 1] = (y[:-2] + 2 * y[1:-1] + y[2:]) / 4
    # keep a vertical end drop (appended by the tracker) as its own vertex
    for end in (0, -1):
        if abs(pts[end, 1] - out[end, 1]) > 2:
            out = np.vstack([out, pts[end]]) if end == -1 else np.vstack([pts[end], out])
    return out


def _runlen(col):
    """length of the dark run through every pixel of a 1-D boolean array"""
    d = np.diff(np.r_[0, col.astype(np.int8), 0])
    st, en = np.where(d == 1)[0], np.where(d == -1)[0]
    out = np.zeros(len(col), int)
    for a, b in zip(st, en):
        out[a:b] = b - a
    return out


def remove_lines(dark, h, v):
    """clear grid/frame line pixels, but keep them where a curve crosses (the run across the line
    is then longer than the line is thick), so curves stay connected through grid lines."""
    m = dark.copy()
    for c, t in h:
        r0, r1 = max(0, int(c - t / 2 - 2)), min(dark.shape[0], int(c + t / 2 + 3))
        if r1 <= r0:
            continue
        for x in range(dark.shape[1]):
            col = dark[:, x]
            if not col[r0:r1].any():
                continue
            rl = _runlen(col[max(0, r0 - 12):r1 + 12])[r0 - max(0, r0 - 12):r0 - max(0, r0 - 12) + (r1 - r0)]
            sel = ((rl > 0) & (rl <= t + 4))[:r1 - r0]
            m[r0:r0 + len(sel), x][sel] = False
    for c, t in v:
        c0, c1 = max(0, int(c - t / 2 - 2)), min(dark.shape[1], int(c + t / 2 + 3))
        if c1 <= c0:
            continue
        for y in range(dark.shape[0]):
            row = dark[y, :]
            if not row[c0:c1].any():
                continue
            rl = _runlen(row[max(0, c0 - 12):c1 + 12])[c0 - max(0, c0 - 12):c0 - max(0, c0 - 12) + (c1 - c0)]
            sel = ((rl > 0) & (rl <= t + 4))[:c1 - c0]
            m[y, c0:c0 + len(sel)][sel] = False
    # grid crossings: both runs are long there, so the rule above keeps them; clear them outright
    for c, t in h:
        r0, r1 = max(0, int(c - t / 2 - 2)), max(0, min(dark.shape[0], int(c + t / 2 + 3)))
        for c2, t2 in v:
            c0, c1 = max(0, int(c2 - t2 / 2 - 1)), min(dark.shape[1], int(c2 + t2 / 2 + 2))
            if c1 > c0 and r1 > r0:
                m[r0:r1, c0:c1] = False
    return m


def vector_subpaths(doc, page, idx, n=24, dense_lines=False):
    """sampled sub-paths (page pt) of drawing number idx on a page, for sheets whose curves are vector art"""
    segs, cur = [], None
    for it in doc[page - 1].get_drawings()[idx]['items']:
        if it[0] == 'c':
            p0, p1, p2, p3 = (np.array([q.x, q.y]) for q in it[1:5])
            t = np.linspace(0, 1, n)[:, None]
            pts = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
        elif it[0] == 'l' and dense_lines:
            # long straight segments sampled every ~0.5 pt like the Bezier pieces, so that binning and smoothing
            # do not bend them (plot option "dense_lines"; off for the configs digitised before it existed)
            p0, p1 = np.array([it[1].x, it[1].y]), np.array([it[2].x, it[2].y])
            k = max(2, int(np.ceil(np.hypot(*(p1 - p0)) / 0.5)) + 1)
            pts = p0 + np.linspace(0, 1, k)[:, None] * (p1 - p0)
        elif it[0] == 'l':
            pts = np.array([[it[1].x, it[1].y], [it[2].x, it[2].y]])
        else:
            continue
        if cur is None or np.abs(pts[0] - cur[-1][-1]).sum() > 0.3:
            cur = [pts]; segs.append(cur)
        else:
            cur.append(pts[1:])
    return [np.vstack(c) for c in segs]


def extract_plot(doc, pc, thr=160):
    rect = pc['rect']; s = DPI / 72
    g = render(doc, pc['page'], rect)
    if pc.get('rotate'):  # deskew a tilted scan (degrees, about the centre of the plot rect)
        g = ndimage.rotate(g, pc['rotate'], reshape=False, cval=255, order=1)
    dark = g < pc.get('threshold', thr)
    h, v = detect_lines(dark, frac=pc.get('line_frac', 0.5))
    notes = []
    xc, n1 = snap(pc['x'], v, rect[0], s); yc, n2 = snap(pc['y'], h, rect[1], s)
    notes += [f'x {n}' for n in n1] + [f'y {n}' for n in n2]
    pw = pc.get('piecewise', True)
    X = Axis(xc, log=pc.get('xlog', False), piecewise=pw); Y = Axis(yc, log=pc.get('ylog', False), piecewise=pw)
    Y0 = Y
    s_ = s
    for val in pc.get('extra_h', []):  # grid lines hidden under a curve (not detected): data y values
        h.append((float(Y0.inv(val)), 6))
    for val in pc.get('extra_v', []):
        v.append((float(X.inv(val)), 6))
    m = remove_lines(dark, h, v)
    keep_m = np.ones_like(m)
    for (a, b, c_, d) in pc.get('mask', []):  # data coords
        xa, xb = sorted([X.inv(a), X.inv(c_)]); ya, yb = sorted([Y.inv(b), Y.inv(d)])
        keep_m[max(0, int(ya)):int(yb) + 1, max(0, int(xa)):int(xb) + 1] = False
    for (a, b, c_, d) in pc.get('mask_pt', []):  # page pt
        keep_m[max(0, int((b - rect[1]) * s)):int((d - rect[1]) * s) + 1, max(0, int((a - rect[0]) * s)):int((c_ - rect[0]) * s) + 1] = False
    m &= keep_m
    mc = pc.get('min_component', 0)
    if mc:

        lab, n = ndimage.label(m, structure=np.ones((3, 3)))
        sl = ndimage.find_objects(lab)
        for i, sli in enumerate(sl):
            if max(sli[0].stop - sli[0].start, sli[1].stop - sli[1].start) < mc:
                m[sli][lab[sli] == i + 1] = False
    runs = column_runs(m)
    rl = np.concatenate([r[:, 1] - r[:, 0] for r in runs if len(r)])
    stroke = float(np.median(rl[(rl >= 2) & (rl < 14)]))
    # frame = outermost vertical lines
    xs = sorted(c for c, t in v)
    vt = {c: t for c, t in v}
    x_lo, x_hi = (int(xs[0] + vt[xs[0]] + 3), int(xs[-1] - vt[xs[-1]] - 3)) if len(xs) >= 2 else (0, m.shape[1] - 1)
    ys = sorted(c for c, t in h)
    y_lo, y_hi = (ys[0], ys[-1]) if len(ys) >= 2 else (0, m.shape[0] - 1)
    res = {}
    rgb_img = None
    for name, cfg in pc['curves'].items():
        seeds = cfg['seeds'] if isinstance(cfg, dict) else cfg
        opts = cfg if isinstance(cfg, dict) else {}
        lo, hi = x_lo, x_hi
        runs_use = runs
        if 'rgb' in opts:
            # colour-printed curves that cross each other: trace only the pixels of this curve's colour
            # ('rgb': [R, G, B] of the stroke, 'rgb_tol': Euclidean distance in 8-bit RGB)
            if rgb_img is None:
                rgb_img = render(doc, pc['page'], rect, rgb=True)[..., :3].astype(float)
                if pc.get('rotate'):
                    rgb_img = ndimage.rotate(rgb_img, pc['rotate'], axes=(1, 0), reshape=False, cval=255, order=1)
            mc = np.linalg.norm(rgb_img - np.asarray(opts['rgb'], float), axis=2) < opts.get('rgb_tol', 90)
            runs_use = column_runs(remove_lines(mc, h, v) & keep_m)
        if 'xlim' in opts:
            a, b = sorted([X.inv(opts['xlim'][0]), X.inv(opts['xlim'][1])]); lo, hi = max(lo, int(a)), min(hi, int(b))
        parts = []
        runs_t = None
        for sd in seeds:
            if isinstance(sd, dict) and 'path' in sd:
                # vector art: [drawing index, sub-path index] on the page; exact, no tracing needed
                sp = vector_subpaths(doc, pc['page'], sd['path'][0], dense_lines=pc.get('dense_lines', False))[sd['path'][1] if len(sd['path']) > 1 else 0]
                P_ = np.column_stack([(sp[:, 0] - rect[0]) * s, (sp[:, 1] - rect[1]) * s])
                a, b = (X.inv(sd['xlim'][0]), X.inv(sd['xlim'][1])) if 'xlim' in sd else (lo, hi)
                a, b = sorted([float(a), float(b)])
                parts.append(P_[(P_[:, 0] >= max(a, lo - 4 * s)) & (P_[:, 0] <= min(b, hi + 4 * s))])
                continue
            if isinstance(sd, dict) and 'row' in sd:
                # transposed tracking x(y), for steep stretches where curves are ordered left to right
                if runs_t is None:
                    runs_t = column_runs(m.T)
                yy = int(round(float(Y.inv(sd['row']))))
                yy = max(range(yy - 10, yy + 11), key=lambda q: (len(runs_t[q]), -abs(q - yy)))  # dashes: densest row
                rr = sorted(runs_t[yy], key=lambda r: r[0])
                if not -len(rr) <= sd.get('rank', 0) < len(rr):
                    raise ValueError(f'{pc["kind"]} {name}: row {sd["row"]} has {len(rr)} strokes')
                r0 = rr[sd.get('rank', 0)]
                a, b = sorted([Y.inv(sd['ylim'][0]), Y.inv(sd['ylim'][1])]) if 'ylim' in sd else (y_lo, y_hi)
                tr = trace(runs_t, (yy, (r0[0] + r0[1] - 1) / 2), stroke, int(max(a, y_lo)), int(min(b, y_hi)),
                           gap=opts.get('gap', 60), tol=opts.get('tol'), y_lo=lo, y_hi=hi)
                parts.append(tr[:, ::-1])
                continue
            if isinstance(sd, dict) and 'col' in sd:
                xx = int(round(float(X.inv(sd['col']))))
                xx = max(range(xx - 10, xx + 11), key=lambda q: (len(runs_use[q]), -abs(q - xx)))  # dashes: densest column
                rr = sorted(runs_use[xx], key=lambda r: r[0])
                if not -len(rr) <= sd.get('rank', 0) < len(rr):
                    raise ValueError(f'{pc["kind"]} {name}: column {sd["col"]} has {len(rr)} strokes')
                r0 = rr[sd.get('rank', 0)]
                sx, sy = xx, (r0[0] + r0[1] - 1) / 2
                slo, shi = lo, hi
                if 'xlim' in sd:
                    a, b = sorted([X.inv(sd['xlim'][0]), X.inv(sd['xlim'][1])]); slo, shi = max(lo, int(a)), min(hi, int(b))
                parts.append(trace(runs_use, (sx, sy), stroke, slo, shi, gap=opts.get('gap', 60), tol=opts.get('tol'),
                                   y_lo=y_lo, y_hi=y_hi))
                continue
            sx, sy = float(X.inv(sd[0])), float(Y.inv(sd[1]))
            try:
                sx, sy = snap_seed(runs_use, (sx, sy), stroke)
            except ValueError as e:
                raise ValueError(f'{pc["kind"]} {name} seed {sd}: {e}')
            slo, shi = lo, hi
            if len(sd) >= 4:  # [x, y, xmin, xmax]: this seed's trace is limited to that x range
                a, b = sorted([X.inv(sd[2]), X.inv(sd[3])]); slo, shi = max(lo, int(a)), min(hi, int(b))
            tr = trace(runs_use, (sx, sy), stroke, slo, shi, gap=opts.get('gap', 60), tol=opts.get('tol'),
                       y_lo=y_lo, y_hi=y_hi)
            parts.append(tr)
        P = np.vstack(parts)
        P = clean(P)
        idx = rdp(P, 0.35)
        P = P[idx]
        xy = np.column_stack([X(P[:, 0]), Y(P[:, 1])])
        o = np.argsort(xy[:, 0], kind='stable'); xy = xy[o]
        # strictly increasing x
        keep = [0]
        for i in range(1, len(xy)):
            if xy[i, 0] > xy[keep[-1], 0] + 1e-6:
                keep.append(i)
        res[name] = xy[keep]
    # curves that merge into another one (overlapping status-A characteristic curves): beyond their own
    # traced range they coincide with the 'fill' curve, whose points are used there
    for name, cfg in pc['curves'].items():
        if isinstance(cfg, dict) and cfg.get('fill'):
            own, ref = res[name], res[cfg['fill']]
            lo_, hi_ = own[0, 0], own[-1, 0]
            mg = 0.01 * (ref[-1, 0] - ref[0, 0])  # ignore a sliver of the fill curve just outside the own trace
            res[name] = np.vstack([ref[ref[:, 0] < lo_ - mg], own, ref[ref[:, 0] > hi_ + mg]])
            notes.append(f'{pc["kind"]} {name}: own trace covers x {lo_:.3g}..{hi_:.3g}; outside it the curve '
                         f'coincides with {cfg["fill"]} on the sheet and that trace is used')
    cal = dict(x_labels=[c[0] for c in pc['x']], y_labels=[c[0] for c in pc['y']],
               x_resid_pt=round(X.resid / s, 3), y_resid_pt=round(Y.resid / s, 3), stroke_px=stroke,
               grid_lines=dict(h=len(h), v=len(v)))
    return res, dict(X=X, Y=Y, g=g, rect=rect, s=s, cal=cal, notes=notes, runs_mask=m)


def overlay(res, ctx, path=None):
    g = ctx['g']; X, Y = ctx['X'], ctx['Y']
    im = Image.fromarray(g).convert('RGB'); dr = ImageDraw.Draw(im)
    W, H = im.size
    for v in [c for c in ctx['cal']['x_labels']]:
        px = float(X.inv(v)); dr.line([(px, H - 40), (px, H - 1)], fill=(255, 0, 255), width=3)
    for v in ctx['cal']['y_labels']:
        py = float(Y.inv(v)); dr.line([(0, py), (40, py)], fill=(255, 0, 255), width=3)
    for name, xy in res.items():
        c = COL.get(name.split('_')[-1], (255, 0, 0))
        px = X.inv(xy[:, 0]); py = Y.inv(xy[:, 1])
        dr.line(list(zip(px, py)), fill=c, width=3)
        for a, b in zip(px, py):
            dr.ellipse([a - 4, b - 4, a + 4, b + 4], outline=c, width=2)
    if path:
        im.save(path)
    return im

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ================================================================== records, checks, recipes
KIND_PREFIX = {'sens': 'log_sensitivity_', 'char': 'density_curve_', 'dye': 'dye_density_'}


def accuracy(res, ctx, dark):
    """distance (pt) from the written polylines to the nearest dark pixel of the page render"""

    dist = ndimage.distance_transform_edt(~dark) / ctx['s']
    X, Y = ctx['X'], ctx['Y']; rep = {}
    for name, xy in res.items():
        if len(xy) < 2:
            rep[name] = dict(median_pt=None, p95_pt=None, max_pt=None, points=len(xy)); continue
        px = X.inv(xy[:, 0]); py = Y.inv(xy[:, 1])
        t = np.r_[0, np.cumsum(np.hypot(np.diff(px), np.diff(py)))]
        tt = np.arange(0, t[-1], 1.0)
        qx = np.interp(tt, t, px); qy = np.interp(tt, t, py)
        d = dist[np.clip(qy.astype(int), 0, dist.shape[0] - 1), np.clip(qx.astype(int), 0, dist.shape[1] - 1)]
        rep[name] = dict(median_pt=round(float(np.median(d)), 3), p95_pt=round(float(np.percentile(d, 95)), 3),
                         max_pt=round(float(d.max()), 3))
    return rep


def write_csv(path, xy, xdec=4, ydec=5):
    with open(path, 'w', newline='') as f:
        for x, y in xy:
            f.write(f'{x:.{xdec}f}, {y:.{ydec}f}\n')


def write_info(folder, sheet, st, files, calib, notes, acc):
    L = [st['name'],
         f"Datasheet: {sheet['publisher']} {sheet['doc']} ({sheet['date']}), {sheet['pdf']}, PDF page(s) "
         f"{', '.join(map(str, sorted({p['page'] for p in st['plots']})))}",
         f"Source URL: {sheet['url']}"] + ([f"Catalogue entry: {sheet['entry']}"] if sheet.get('entry') else []) + [
         f"Publication: {sheet['doc']}", f"Publication date: {sheet['date']}",
         f"Type: {st['type']}"]
    for k in ('densitometry', 'process', 'exposure', 'sensitivity_defined_at', 'speed'):
        if st.get('meta', {}).get(k):
            L.append(f"{k.replace('_', ' ').capitalize()}: {st['meta'][k]}")
    L += ['', 'Files (x range, y range, n points):']
    for fn, d in sorted(files.items()):
        L.append(f'  {fn}.csv  x {d["x"][0]}..{d["x"][1]}  y {d["y"][0]}..{d["y"][1]}  n={d["n"]}')
    L += ['',
          'Units: log_sensitivity_* = wavelength nm, log10 sensitivity (relative where the sheet prints no',
          '  absolute scale); density_curve_* = log10 H (lux-seconds), total density as printed (base+fog',
          '  included); dye_density_* = wavelength nm, spectral diffuse density (c/m/y: individual dyes as',
          '  printed; mid: mid-scale neutral; min: minimum density).',
          'Extraction: the plot is rendered from the PDF at 600 dpi (the curves are embedded 1-bit scans or',
          '  vector strokes), grid lines are found as long straight dark runs and removed except where a curve',
          '  crosses them, axes are calibrated piecewise-linearly through the printed grid lines named in the',
          '  sheet config (sheets/*.json), and each curve is followed column by column from a seed point',
          '  (script: scripts/extract_filmcolors_datasheets.py). Typical accuracy ~0.2-0.5 pt on the page',
          '  (about 1-2 nm, 0.01-0.02 log H or density) plus the accuracy of the original drawing / scan.',
          'Calibration:']
    for k, v in calib.items():
        L.append(f'  {k}: {json.dumps(v)}')
    L.append('Distance of the written curves to the printed strokes (pt): ' + json.dumps(acc))
    L += ['Caveats:'] + ([f'  {n}' for n in notes] or ['  none'])
    with open(os.path.join(folder, 'info.txt'), 'w') as f:
        f.write('\n'.join(L) + '\n')


def check_sheet(ims, path, h=1100):
    ims = [im.resize((int(im.width * h / im.height), h), Image.LANCZOS) for im in ims]
    rows = [ims[i:i + 2] for i in range(0, len(ims), 2)]
    W = max(sum(i.width for i in r) for r in rows)
    out = Image.new('RGB', (W, h * len(rows)), 'white')
    for k, r in enumerate(rows):
        x = 0
        for im in r:
            out.paste(im, (x, k * h)); x += im.width
    out.save(path)


def extract_sheet(sheet, pdf_dir, out, chk):
    doc = pymupdf.open(os.path.join(pdf_dir, sheet['pdf']))
    if sheet.get('derotate'):  # spreads stored as rotated portrait pages: work in the displayed orientation
        for pg in doc:
            pg.remove_rotation()
    rows, summary = [], {}
    for st in sheet['stocks']:
        bucket = 'positive' if st['type'] == 'positive' else 'negative'
        folder = os.path.join(out, bucket, st['id'])
        if os.path.isdir(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)
        files, calib, notes, acc, ims = {}, {}, list(st.get('notes', [])), {}, []
        for pc in st['plots']:
            res, ctx = extract_plot(doc, pc)
            notes += ctx['notes']
            tag = f"{pc['kind']}_p{pc['page']}"
            calib[tag] = ctx['cal']
            dark = ctx['g'] < pc.get('threshold', 160)
            for name, a in accuracy(res, ctx, dark).items():
                acc[f"{pc['kind']}:{name}"] = a
            for name, xy in res.items():
                fn = KIND_PREFIX[pc['kind']] + name
                write_csv(os.path.join(folder, fn + '.csv'), xy)
                files[fn] = dict(n=len(xy), x=(round(float(xy[0, 0]), 3), round(float(xy[-1, 0]), 3)),
                                 y=(round(float(xy[:, 1].min()), 3), round(float(xy[:, 1].max()), 3)))
            ims.append(overlay(res, ctx))
        missing = [f for f in ('log_sensitivity_r', 'log_sensitivity_g', 'log_sensitivity_b', 'density_curve_r',
                               'density_curve_g', 'density_curve_b') if f not in files
                   and f not in st.get('borrow', {}).get('files', [])]
        if missing:
            notes.append(f'MISSING: {missing}')
        write_info(folder, sheet, st, files, calib, notes, acc)
        os.makedirs(chk, exist_ok=True)
        check_sheet(ims, os.path.join(chk, f"{st['id']}_overlay600dpi.png"))
        rows.append(dict(id=st['id'], name=st['name'], type=st['type'], folder=f'{bucket}/{st["id"]}',
                         pdf=sheet['pdf'], document=sheet['doc'], date=sheet['date'],
                         pages=';'.join(map(str, sorted({p['page'] for p in st['plots']}))),
                         build=('yes' if st.get('recipe') else 'record only'), url=sheet['url'],
                         files=';'.join(sorted(f + '.csv' for f in files))))
        summary[st['id']] = dict(files=files, notes=notes, calib=calib, accuracy=acc)
        print(st['id'], sorted(files), '|', '; '.join(notes))
    return rows, summary


RECIPE_COLS = ['stock', 'name', 'type', 'record', 'target_print', 'reference_illuminant', 'viewing_illuminant',
               'antihalation', 'log_sensitivity_density_over_min', 'data_trustability', 'density_min',
               'dye_extension', 'adaptation_donors', 'datasource', 'source_id', 'page']


# hanatos2025 adaptation parameters are not on any sheet; they are borrowed from these shipped profiles
# (pinned, so that rebuilding does not drift once the profiles built here are shipped themselves)
DEFAULT_DONORS = {
    'positive': ['fujifilm_64t_type_ii_fdg', 'fujifilm_astia_100f_fdg', 'fujifilm_provia_100f',
                 'fujifilm_provia_100f_fdg', 'fujifilm_provia_400f_fdg', 'fujifilm_sensia_100_fdg',
                 'fujifilm_sensia_200_fdg', 'fujifilm_sensia_400_fdg', 'fujifilm_velvia_100',
                 'fujifilm_velvia_100_fdg', 'fujifilm_velvia_100f_fdg', 'fujifilm_velvia_50_fdg'],
    'negative': ['fujifilm_c200', 'fujifilm_nexia_400_fdg', 'fujifilm_nexia_800_fdg', 'fujifilm_nexia_a200_fdg',
                 'fujifilm_npl_160_fdg', 'fujifilm_pro_160c_fdg', 'fujifilm_pro_160s_fdg', 'fujifilm_pro_400h',
                 'fujifilm_pro_400h_fdg', 'fujifilm_pro_800z_fdg', 'fujifilm_superia_100_fdg',
                 'fujifilm_superia_1600_fdg', 'fujifilm_superia_200_fdg', 'fujifilm_superia_reala_fdg',
                 'fujifilm_superia_xtra_400_fdg', 'fujifilm_superia_xtra_800_fdg',
                 'fujifilm_true_definition_400_fdg', 'fujifilm_xtra_400'],
}


def recipes(sheets):
    out = []
    for sheet in sheets:
        for st in sheet['stocks']:
            r = st.get('recipe')
            if not r:
                continue
            pages = ';'.join(map(str, sorted({p['page'] for p in st['plots']})))
            src = (f"{sheet['publisher']} {sheet['doc']} ({sheet['date']}), {sheet['pdf']}, PDF page(s) {pages}, "
                   f"{st['name']}: {sheet['url']}" + (f" (catalogued at {sheet['entry']})" if sheet.get('entry') else ''))
            if r.get('estimates'):
                src += ' Estimate placeholders (not on the sheet): ' + '; '.join(r['estimates']) + '.'
            bucket = 'positive' if st['type'] == 'positive' else 'negative'
            out.append(dict(stock=r['stock'], name=r['name'], type=st['type'], record=f'{bucket}/{st["id"]}',
                            target_print=r.get('target_print', ''), reference_illuminant=r.get('reference_illuminant', 'D55'),
                            viewing_illuminant='D50', antihalation=r.get('antihalation', 'strong'),
                            log_sensitivity_density_over_min=r.get('density_over_min', 1.0),
                            data_trustability=r.get('data_trustability', 0.3), density_min=r.get('density_min', ''),
                            dye_extension=r.get('dye_extension', ''), adaptation_donors=' '.join(r.get('adaptation_donors', DEFAULT_DONORS.get(st['type'], []))),
                            datasource=src, source_id=st['id'], page=pages, **({'use': r['use']} if r.get('use') else {})))
    return out


BORROW_MARK = 'Borrowed curves (estimate placeholders, not on this sheet):'


def borrow(sheets, raw):
    """Stocks whose sheet prints only some plots (e.g. a manual with characteristic curves only) take the
    missing curves from a sibling record (`"borrow": {"from": id, "files": [...], "why": "..."}`); the copies
    are listed in info.txt and the extraction summary as estimates."""
    where = {st['id']: ('positive' if st['type'] == 'positive' else 'negative') for sh in sheets for st in sh['stocks']}
    out = {}
    for sheet in sheets:
        for st in sheet['stocks']:
            b = st.get('borrow')
            if not b:
                continue
            if b['from'] not in where:
                raise ValueError(f"{st['id']}: borrow source {b['from']} has no sheet config")
            src = os.path.join(raw, where[b['from']], b['from'])
            dst = os.path.join(raw, where[st['id']], st['id'])
            if not os.path.isdir(dst):
                continue
            for fn in b['files']:
                shutil.copyfile(os.path.join(src, fn + '.csv'), os.path.join(dst, fn + '.csv'))
            info = os.path.join(dst, 'info.txt')
            text = open(info).read().split(BORROW_MARK)[0].rstrip('\n') + '\n'
            text += f"{BORROW_MARK}\n  {', '.join(f + '.csv' for f in b['files'])} copied from {b['from']}"
            text += (f" ({b['why']})" if b.get('why') else '') + '\n'
            open(info, 'w').write(text)
            out[st['id']] = dict(source=b['from'], files=list(b['files']), why=b.get('why', ''))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pdfs', required=True, help='folder holding the downloaded sheet PDFs')
    ap.add_argument('--raw', default=os.path.join(ROOT, 'src', 'spektrafilm_profile_builder', 'data', 'raw',
                                                  'filmcolors_data_sheets'),
                    help='raw folder (sheets/*.json in, records + records.csv + recipes.csv out)')
    ap.add_argument('--checks', default=None, help='overlay check PNG folder (default <raw>/_checks)')
    ap.add_argument('--only', default='', help='comma-separated sheet config stems')
    a = ap.parse_args()
    cfgs = sorted(glob.glob(os.path.join(a.raw, 'sheets', '*.json')))
    sheets = [json.load(open(f)) for f in cfgs]
    only = {s for s in a.only.split(',') if s}
    summ_path = os.path.join(a.raw, 'extraction_summary.json')
    summary = json.load(open(summ_path)) if os.path.exists(summ_path) else {}
    rows = []
    for f, sheet in zip(cfgs, sheets):
        stem = os.path.basename(f)[:-5]
        if only and stem not in only:
            continue
        r, s = extract_sheet(sheet, a.pdfs, a.raw, a.checks or os.path.join(a.raw, '_checks'))
        summary.update(s)
    ids = {st['id'] for sh in sheets for st in sh['stocks']}
    summary = {k: v for k, v in summary.items() if k in ids}
    for k, v in borrow(sheets, a.raw).items():
        summary.setdefault(k, {})['borrowed'] = v
    for sheet in sheets:
        for st in sheet['stocks']:
            bucket = 'positive' if st['type'] == 'positive' else 'negative'
            files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(a.raw, bucket, st['id'], '*.csv')))
            rows.append(dict(id=st['id'], name=st['name'], type=st['type'], folder=f'{bucket}/{st["id"]}',
                             pdf=sheet['pdf'], document=sheet['doc'], date=sheet['date'],
                             pages=';'.join(map(str, sorted({p['page'] for p in st['plots']}))),
                             build=(st['recipe']['stock'] if st.get('recipe') else 'record only'),
                             url=sheet['url'], files=';'.join(files)))
    with open(os.path.join(a.raw, 'records.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(os.path.join(a.raw, 'recipes.csv'), 'w', newline='') as f:
        rr = recipes(sheets)
        cols = RECIPE_COLS + (['use'] if any('use' in r for r in rr) else [])
        w = csv.DictWriter(f, fieldnames=cols, restval=''); w.writeheader(); w.writerows(rr)
    with open(summ_path, 'w') as f:
        json.dump(summary, f, indent=1, sort_keys=True)


if __name__ == '__main__':
    main()
