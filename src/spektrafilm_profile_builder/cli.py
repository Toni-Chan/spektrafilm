"""Command line interface.

    spektrafilm-profile-builder build RECORD_DIR --stock ID --name NAME --type negative \
        --target-print kodak_portra_endura -o OUT_DIR
    spektrafilm-profile-builder batch RECIPES.csv -o OUT_DIR [--only id1,id2] [--filters-json F]
    spektrafilm-profile-builder fit-filters PROFILE.json [...] --filters-json F
    spektrafilm-profile-builder catalog PROFILE.json [...]

``python -m spektrafilm_profile_builder`` works the same way.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from spektrafilm.model.stocks import PrintPapers
from spektrafilm.profiles.io import profile_from_dict

from .process import BuildReport, Recipe, build_profile
from .records import load_record
from .writer import save_profile_json

_BOOL = {'1': True, 'true': True, 'yes': True, '0': False, 'false': False, 'no': False, '': None}


def _recipe_from_row(row: dict) -> Recipe:
    kw = {}
    for key, value in row.items():
        if key is None or key in ('record', 'source_id', 'page', 'notes') or value is None:
            continue
        value = value.strip()
        if value == '':
            continue
        if key in ('grey_ramp_correction',):
            kw[key] = _BOOL[value.lower()]
        elif key in ('log_sensitivity_density_over_min', 'data_trustability'):
            kw[key] = float(value)
        elif key == 'adaptation_donors':
            kw[key] = [v for v in value.replace(';', ' ').split() if v]
        else:
            kw[key] = value
    return Recipe(**kw)


def read_recipes(path) -> list[tuple[Path, Recipe]]:
    """Batch recipe CSV: one row per profile; ``record`` is the record folder
    (relative to the CSV), the other columns are :class:`Recipe` fields."""
    path = Path(path)
    rows = []
    with path.open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if not row.get('stock') or row['stock'].startswith('#'):
                continue
            rows.append(((path.parent / row['record']).resolve(), _recipe_from_row(row)))
    return rows


def _print_report(report: BuildReport):
    print(f'[{report.stock}] ({report.type})')
    for step in report.steps:
        print('   ', step)


def fit_filters_for_profiles(profiles, filters_json, papers=None, illuminant='TH-KG3', only_missing=False):
    """Fit neutral enlarger filters of each negative on every print paper and
    merge them into a ``neutral_print_filters.json`` (created if missing).
    Paper profiles in ``profiles`` are skipped (they are print targets).
    ``only_missing`` keeps every entry already in the file untouched."""
    from .runtime_fit import fit_neutral_print_filters

    filters_json = Path(filters_json)
    db = json.loads(filters_json.read_text()) if filters_json.exists() else {}
    papers = papers or [p.value for p in PrintPapers]
    for profile in profiles:
        if profile.info.stage == 'printing':
            continue
        stock = profile.info.stock
        for paper in papers:
            slot = db.setdefault(paper, {}).setdefault(illuminant, {})
            if only_missing and stock in slot:
                continue
            if profile.info.type == 'positive':
                cmy = (0.0, 50.0, 50.0)  # placeholder, as for the shipped reversal films
                res = 0.0
            else:
                cmy, res = fit_neutral_print_filters(profile, paper, illuminant=illuminant)
            slot[stock] = list(cmy)
            print(f'   filters {stock} on {paper}: C {cmy[0]:.2f} M {cmy[1]:.2f} Y {cmy[2]:.2f} (res {res:.1e})')
            filters_json.parent.mkdir(parents=True, exist_ok=True)
            filters_json.write_text(json.dumps(db, indent=4) + '\n')
    filters_json.parent.mkdir(parents=True, exist_ok=True)
    filters_json.write_text(json.dumps(db, indent=4) + '\n')


def _load_profiles(items):
    from spektrafilm.profiles.io import load_profile
    out = []
    for item in items:
        p = Path(item)
        out.append(profile_from_dict(json.loads(p.read_text())) if p.suffix == '.json' and p.exists()
                   else load_profile(item))
    return out


def _add_recipe_args(ap):
    ap.add_argument('--stock', required=True, help='profile id (file name stem); must not clash with shipped ids')
    ap.add_argument('--name', required=True, help='display name (info.name)')
    ap.add_argument('--type', choices=('negative', 'positive', 'paper'), default=None,
                    help='default: from info.txt / available files')
    ap.add_argument('--support', choices=('paper', 'film'), default=None,
                    help="paper type only: 'paper' (reflection print, default) or 'film' (display transparency)")
    ap.add_argument('--densitometer', choices=('status_M', 'status_A'), default=None)
    ap.add_argument('--density-over-min', type=float, default=1.0, dest='log_sensitivity_density_over_min',
                    help='density above D-min at which the sheet defines sensitivity (default 1.0)')
    ap.add_argument('--reference-illuminant', default='D55')
    ap.add_argument('--viewing-illuminant', default='D50')
    ap.add_argument('--target-print', default=None, help='paper profile id (negatives)')
    ap.add_argument('--use', choices=('still', 'cine'), default='still')
    ap.add_argument('--antihalation', choices=('strong', 'weak', 'no'), default='strong')
    ap.add_argument('--dye-start', default='generic_a')
    ap.add_argument('--no-grey-ramp', action='store_true', help='skip the runtime grey-ramp refinement')
    ap.add_argument('--data-trustability', type=float, default=0.3)
    ap.add_argument('--adaptation-donors', default='', help='comma-separated shipped profile ids')
    ap.add_argument('--density-min', default='',
                    help="base+fog 'r,g,b' (status density) instead of the toe fit: an estimate for curves cut off before D-min")
    ap.add_argument('--dye-extension', choices=('none', 'hold_decay'), default='none',
                    help="positives: continue dyes outside the printed range ('hold_decay', an estimate placeholder)")
    ap.add_argument('--datasource', default='')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='spektrafilm-profile-builder',
                                 description='Build spektrafilm film profiles from data-sheet curve records.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    b = sub.add_parser('build', help='build one profile from a record folder')
    b.add_argument('record')
    b.add_argument('-o', '--out', required=True, help='output folder for <stock>.json')
    b.add_argument('--filters-json', default=None,
                   help='also fit neutral print filters and merge them into this JSON')
    _add_recipe_args(b)

    bb = sub.add_parser('batch', help='build every row of a recipe CSV')
    bb.add_argument('recipes')
    bb.add_argument('-o', '--out', required=True)
    bb.add_argument('--only', default='', help='comma-separated stock ids to build')
    bb.add_argument('--filters-json', default=None)

    cc = sub.add_parser('catalog', help='print a JSON catalogue (id, name, short name, kind, ISO, '
                                        'target print, swatch) of profile JSONs, for downstream pickers')
    cc.add_argument('profiles', nargs='+')

    ff = sub.add_parser('fit-filters', help='fit neutral print filters for existing profile JSONs')
    ff.add_argument('profiles', nargs='+', help='profile JSON files or shipped profile ids')
    ff.add_argument('--filters-json', required=True)
    ff.add_argument('--papers', default='', help='comma-separated paper ids (default: every PrintPapers entry)')
    ff.add_argument('--only-missing', action='store_true', help='never overwrite an existing entry')

    args = ap.parse_args(argv)

    if args.cmd == 'catalog':
        from .catalog import catalog_entries
        profiles = [profile_from_dict(json.loads(Path(p).read_text())) for p in args.profiles]
        print(json.dumps({'stocks': catalog_entries(profiles)}, indent=1, ensure_ascii=False))
        return 0

    if args.cmd == 'fit-filters':
        papers = [p for p in args.papers.split(',') if p] or None
        fit_filters_for_profiles(_load_profiles(args.profiles), args.filters_json, papers=papers,
                                 only_missing=args.only_missing)
        return 0

    if args.cmd == 'build':
        record = load_record(args.record)
        recipe = Recipe(
            stock=args.stock, name=args.name, type=args.type or record.guessed_type, support=args.support,
            densitometer=args.densitometer,
            log_sensitivity_density_over_min=args.log_sensitivity_density_over_min,
            reference_illuminant=args.reference_illuminant, viewing_illuminant=args.viewing_illuminant,
            target_print=args.target_print, use=args.use, antihalation=args.antihalation,
            dye_start=args.dye_start, grey_ramp_correction=not args.no_grey_ramp,
            data_trustability=args.data_trustability,
            adaptation_donors=[d for d in args.adaptation_donors.split(',') if d],
            density_min=args.density_min, dye_extension=args.dye_extension, datasource=args.datasource,
        )
        jobs = [(record, recipe)]
    else:
        only = {s for s in args.only.split(',') if s}
        jobs = [(load_record(folder), recipe) for folder, recipe in read_recipes(args.recipes)
                if not only or recipe.stock in only]

    built = []
    for record, recipe in jobs:
        report = BuildReport(recipe.stock, recipe.type)
        profile = build_profile(record, recipe, report)
        path = save_profile_json(profile, args.out)
        _print_report(report)
        print('    ->', path)
        built.append(profile)
    if args.filters_json:
        fit_filters_for_profiles(built, args.filters_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
