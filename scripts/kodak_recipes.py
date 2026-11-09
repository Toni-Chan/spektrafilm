"""Write the builder recipe CSV for the KODAK technical-data records.

    python scripts/kodak_recipes.py src/spektrafilm_profile_builder/data/raw/kodak_technical_data

Reads records.csv (written by extract_kodak_datasheets.py) and each record's
info.txt, and writes recipes.csv next to it: one row per profile built.
Only the current revision of each sheet is built; superseded revisions,
digital-exposure materials, Radiance reversal papers and the duplicating film
stay records only (see the README for the reasons).
"""
import csv, os, re, sys

# id -> (display name, reference illuminant, antihalation)
NEGATIVES = {
    'kodak_portra_160nc_e190': ('Kodak Portra 160NC', 'D55', 'strong'),
    'kodak_portra_160vc_e190': ('Kodak Portra 160VC', 'D55', 'strong'),
    'kodak_portra_400nc_e190': ('Kodak Portra 400NC', 'D55', 'strong'),
    'kodak_portra_400vc_e190': ('Kodak Portra 400VC', 'D55', 'strong'),
    'kodak_portra_400uc_e190': ('Kodak Portra 400UC', 'D55', 'strong'),
    'kodak_portra_800_e190': ('Kodak Portra 800', 'D55', 'strong'),
    'kodak_portra_100t_e2468': ('Kodak Portra 100T', 'T', 'strong'),
    'kodak_ektapress_pj100_e116': ('Kodak Ektapress PJ100', 'D55', 'strong'),
    'kodak_ektapress_pj400_e116': ('Kodak Ektapress PJ400', 'D55', 'strong'),
    'kodak_ektapress_pj800_e116': ('Kodak Ektapress PJ800', 'D55', 'strong'),
    'kodak_pro_100_e182': ('Kodak Pro 100', 'D55', 'strong'),
    'kodak_pro_100t_e182': ('Kodak Pro 100T', 'T', 'strong'),
    'kodak_pro_400_e182': ('Kodak Pro 400', 'D55', 'strong'),
    'kodak_pro_400mc_e182': ('Kodak Pro 400 MC', 'D55', 'strong'),
    'kodak_pro_1000_e182': ('Kodak Pro 1000', 'D55', 'strong'),
    'kodak_pro_100t_e29': ('Kodak Pro 100T', 'T', 'strong'),
    'kodak_pro_image_100_e4l': ('Kodak Pro Image 100', 'D55', 'strong'),
    'kodak_vericolor_iii_e26': ('Kodak Vericolor III', 'D55', 'strong'),
    'kodak_royal_gold_400_e7007': ('Kodak Royal Gold 400', 'D55', 'weak'),
    'kodak_max_versatility_400_e2330': ('Kodak Max Versatility 400', 'D55', 'weak'),
    'kodak_max_versatility_plus_800_e2452': ('Kodak Max Versatility Plus 800', 'D55', 'weak'),
    'kodak_bright_sun_flash_200_e2329': ('Kodak Bright Sun & Flash 200', 'D55', 'weak'),
    'kodak_advantix_100_e46': ('Kodak Advantix 100', 'D55', 'weak'),
    'kodak_advantix_200_e46': ('Kodak Advantix 200', 'D55', 'weak'),
    'kodak_advantix_400_e46': ('Kodak Advantix 400', 'D55', 'weak'),
    'kodak_advantix_100_e7003': ('Kodak Advantix 100', 'D55', 'weak'),
    'kodak_advantix_bright_sun_flash_hd200_e7003': ('Kodak Advantix Bright Sun & Flash 200', 'D55', 'weak'),
    'kodak_advantix_versatility_e7003': ('Kodak Advantix Versatility 400', 'D55', 'weak'),
}
POSITIVES = {
    'kodak_ektachrome_64_e8': ('Kodak Ektachrome 64 (EPR)', 'D55', 'strong'),
    'kodak_ektachrome_100_e27': ('Kodak Ektachrome 100 (EPN)', 'D55', 'strong'),
    'kodak_ektachrome_100_plus_e113': ('Kodak Ektachrome 100 Plus (EPP)', 'D55', 'strong'),
    'kodak_ektachrome_64t_e130': ('Kodak Ektachrome 64T (EPY)', 'T', 'strong'),
    'kodak_ektachrome_160t_e144': ('Kodak Ektachrome 160T (EPT)', 'T', 'strong'),
    'kodak_ektachrome_320t_e145': ('Kodak Ektachrome 320T (EPJ)', 'T', 'strong'),
    'kodak_ektachrome_p1600_e147': ('Kodak Ektachrome P1600 (EPH)', 'D55', 'strong'),
    'kodak_ektachrome_400x_e161': ('Kodak Ektachrome 400X (EPL)', 'D55', 'strong'),
    'kodak_ektachrome_e100vs_e163': ('Kodak Ektachrome E100VS', 'D55', 'strong'),
    'kodak_ektachrome_e100s_e164': ('Kodak Ektachrome E100S', 'D55', 'strong'),
    'kodak_ektachrome_e100sw_e164': ('Kodak Ektachrome E100SW', 'D55', 'strong'),
    'kodak_ektachrome_e200_e28': ('Kodak Ektachrome E200', 'D55', 'strong'),
    'kodak_ektachrome_e100g_e4024': ('Kodak Ektachrome E100G', 'D55', 'strong'),
    'kodak_ektachrome_e100gx_e4024': ('Kodak Ektachrome E100GX', 'D55', 'strong'),
    'kodak_elite_chrome_100_e7014': ('Kodak Elite Chrome 100', 'D55', 'weak'),
    'kodak_elite_chrome_extra_color_100_e126': ('Kodak Elite Chrome Extra Color 100', 'D55', 'weak'),
    'kodak_elite_chrome_200_e148': ('Kodak Elite Chrome 200', 'D55', 'weak'),
    'kodak_elite_chrome_160t_e154': ('Kodak Elite Chrome 160T', 'T', 'weak'),
}
# id -> (display name, support)   support 'film' = transparent/translucent display material (like kodak_2383)
PAPERS = {
    'kodak_portra_iii_e140': ('Kodak Professional Portra III Paper', 'paper'),
    'kodak_supra_iii_e141': ('Kodak Professional Supra III Paper', 'paper'),
    'kodak_ultra_iii_e142': ('Kodak Professional Ultra III Paper', 'paper'),
    'kodak_ektacolor_edge_7_e19': ('Kodak Ektacolor Edge 7 Paper', 'paper'),
    'kodak_ektacolor_royal_vii_e23': ('Kodak Ektacolor Royal VII Paper', 'paper'),
    'kodak_color_metallic_e4005': ('Kodak Professional Color Metallic Paper', 'paper'),
    'kodak_ultra_endura_e4020': ('Kodak Professional Ultra Endura Paper', 'paper'),
    'kodak_portra_endura_e4021': ('Kodak Professional Portra Endura Paper', 'paper'),
    'kodak_supra_endura_e4021': ('Kodak Professional Supra Endura Paper', 'paper'),
    'kodak_endura_metallic_e4028': ('Kodak Professional Endura Metallic Paper', 'paper'),
    'kodak_royal_generations_e7009': ('Kodak Royal Generations Paper', 'paper'),
    'kodak_edge_generations_e7010': ('Kodak Edge Generations Paper', 'paper'),
    'kodak_duraflex_e143': ('Kodak Professional Duraflex Print Material', 'paper'),
    'kodak_duratrans_e143': ('Kodak Professional Duratrans Display Material', 'film'),
    'kodak_duraclear_e143': ('Kodak Professional Duraclear Display Material', 'film'),
    'kodak_endura_transparency_e4030': ('Kodak Professional Endura Transparency Display Material', 'film'),
    'kodak_endura_clear_e4030': ('Kodak Professional Endura Clear Display Material', 'film'),
}


def year(date):
    m = re.search(r'(\d{4})', date)
    return m.group(1) if m else ''


def density_over_min(info, default):
    m = re.search(r'^Sensitivity defined at:[ \t]*(.*)$', info, re.M)
    s = m.group(1) if m else ''
    v = re.search(r'(\d+\.\d+)', s)
    return float(v.group(1)) if v else default


def main():
    root = sys.argv[1]
    rows = list(csv.DictReader(open(os.path.join(root, 'records.csv'))))
    out = []
    for r in rows:
        rid = r['id']
        info = open(os.path.join(root, r['folder'], 'info.txt')).read()
        tag = f"{r['publication']}, {year(r['date'])}"
        src = (f"KODAK technical data {r['publication']} ({r['date']}), {r['pdf']}, PDF page(s) {r['pages']}, "
               f"{r['name']}: https://125px.com/docs/unsorted/kodak/{r['pdf']}")
        base = dict(stock=rid, record=r['folder'], datasource=src, source_id=rid, page=r['pages'])
        if rid in NEGATIVES:
            name, ill, ah = NEGATIVES[rid]
            out.append(dict(base, name=f'{name} ({tag})', type='negative', target_print='kodak_portra_endura',
                            reference_illuminant=ill, viewing_illuminant='D50', antihalation=ah,
                            log_sensitivity_density_over_min=density_over_min(info, 0.2),
                            data_trustability=1.0, support=''))
        elif rid in POSITIVES:
            name, ill, ah = POSITIVES[rid]
            out.append(dict(base, name=f'{name} ({tag})', type='positive', target_print='',
                            reference_illuminant=ill, viewing_illuminant='D50', antihalation=ah,
                            log_sensitivity_density_over_min=density_over_min(info, 1.0),
                            data_trustability=1.0, support=''))
        elif rid in PAPERS:
            name, support = PAPERS[rid]
            out.append(dict(base, name=f'{name} ({tag})', type='paper', target_print='',
                            reference_illuminant='TH-KG3', viewing_illuminant='D50', antihalation='strong',
                            log_sensitivity_density_over_min=density_over_min(info, 1.0),
                            data_trustability=1.0, support=support))
    cols = ['stock', 'name', 'type', 'record', 'support', 'target_print', 'reference_illuminant',
            'viewing_illuminant', 'antihalation', 'log_sensitivity_density_over_min', 'data_trustability',
            'datasource', 'source_id', 'page']
    with open(os.path.join(root, 'recipes.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(out)
    known = set(NEGATIVES) | set(POSITIVES) | set(PAPERS)
    missing = known - {r['id'] for r in rows}
    if missing:
        sys.exit(f'records missing for {sorted(missing)}')
    print(f'{len(out)} recipes')


if __name__ == '__main__':
    main()
