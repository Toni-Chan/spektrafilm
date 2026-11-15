"""Catalogue every KODAK technical data sheet (e*.pdf) in a folder.

Writes index.csv with one row per PDF: publication code, date, stocks, material
type, curve sets found (plot headings), vector vs raster, superseded revisions
and notes.  Uses the plot finder from kodak_plots.py and the stock table from
extract_kodak_datasheets.py.

    python scripts/kodak_catalog.py --pdfs DIR --records DIR --out index.csv
"""
import argparse, collections, csv, importlib.util, os, re, sys

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kodak_plots as K  # noqa: E402
import extract_kodak_datasheets as E  # noqa: E402

# Sheets with no characteristic / spectral curves (checked by hand).
NO_CURVES = {
    'e103bf': ('selection guide', 'KODAK PROFESSIONAL film selection guide (applications table); no curves'),
    'e103cp': ('selection guide', 'KODAK PROFESSIONAL colour paper selection guide; no curves'),
    'e103nf': ('selection guide', 'KODAK PROFESSIONAL PORTRA films selection guide; no curves'),
    'e11': ('reference', 'Pathways to Color (introductory reference); no sensitometric curves'),
    'e119': ('display material (digital exposure)', 'DURATRANS / DURACLEAR Plus Digital Display Material; text only, no plotted curves'),
    'e176': ('reference', 'Effects of post-processing treatments on print image stability; no sensitometric curves'),
    'e24': ('colour print film (slide film from negatives)', 'VERICOLOR Slide Film; exposure/processing data only, no plotted curves'),
    'e30': ('reference', 'Storage and care of KODAK photographic materials; no sensitometric curves'),
    'e4013': ('display material (digital exposure)', 'Day/Night Digital Display Material; no plotted curves'),
}

TYPE_LABEL = {
    'negative': 'colour negative film', 'positive': 'colour reversal film',
    'duplicating': 'colour duplicating film', 'paper': 'colour negative paper (optical)',
    'display': 'colour display material (optical, transparent/translucent)',
    'paper_digital': 'colour paper (digital exposure)', 'display_digital': 'display material (digital exposure)',
    'reversal_paper': 'colour reversal paper (Radiance)', 'bw': 'B&W',
}


# Sheets whose first page names the product without the word KODAK (checked by hand).
TITLES = {'e55': 'KODACHROME 25, 64, and 200 Professional Film'}


def title_of(doc, stem=''):
    if stem in TITLES:
        return TITLES[stem]
    lines = [l.strip() for l in doc[0].get_text().splitlines() if l.strip()]
    for l in lines[:12]:
        if re.search(r'KODAK', l) and len(l) > 10:
            return l[:90]
    return lines[0][:90] if lines else ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdfs', required=True)
    ap.add_argument('--records', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    recs = collections.defaultdict(list)
    with open(os.path.join(a.records, 'records.csv')) as f:
        for r in csv.DictReader(f):
            recs[r['pdf']].append(r)
    stems = sorted(f[:-4] for f in os.listdir(a.pdfs) if re.match(r'e.*\.pdf$', f))
    newer = {s.split('-')[0]: s for s in stems if '-' in s}
    rows = []
    for stem in stems:
        doc = pymupdf.open(os.path.join(a.pdfs, stem + '.pdf'))
        date, _ = E.pub_info(doc)
        pub = 'E-' + stem[1:].split('-')[0].upper()
        nimg = sum(len(p.get_images()) for p in doc)
        nseg = sum(len(p.get_drawings()) for p in doc)
        kinds = collections.Counter()
        for p in doc:
            for h in K.headings(p):
                kinds[h['kind']] += 1
        rr = recs.get(stem + '.pdf', [])
        types = sorted({r['type'] for r in rr})
        notes = []
        if stem in NO_CURVES:
            typ, note = NO_CURVES[stem]
            notes.append(note)
        else:
            typ = '; '.join(TYPE_LABEL.get(t, t) for t in types) or 'unclassified'
        sup = ''
        if stem in newer:
            sup = f'superseded by {newer[stem]}.pdf'
        elif '-' in stem:
            sup = f'supersedes {stem.split("-")[0]}.pdf'
        if nimg:
            notes.append(f'{nimg} embedded image(s); curves are vector')
        rows.append({
            'file': stem + '.pdf', 'publication': pub, 'date': date, 'pages': len(doc),
            'title': title_of(doc, stem),
            'stocks': '; '.join(r['name'] for r in rr),
            'record_ids': '; '.join(r['id'] for r in rr),
            'type': typ,
            'curve_sets': '; '.join(f'{k}x{v}' for k, v in sorted(kinds.items())),
            'graphics': 'vector' if nseg and not nimg else ('vector+raster' if nseg else 'raster'),
            'superseded': sup, 'notes': ' | '.join(notes),
            'url': E.source_url(stem),
        })
    with open(a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f'{len(rows)} sheets -> {a.out}')


if __name__ == '__main__':
    main()
