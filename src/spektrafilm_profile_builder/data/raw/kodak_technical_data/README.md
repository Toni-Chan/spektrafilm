# KODAK technical data sheets — raw curve records

Source: the KODAK technical data sheets (publication series E-*, 1997-2003)
mirrored at <https://125px.com/docs/unsorted/kodak/>, plus E-55 KODACHROME 25,
64, and 200 Professional Film (June 2009) mirrored at
<https://125px.com/docs/film/kodak/e55.pdf>, published by Eastman
Kodak Company. **The PDFs are not redistributed here**; every record names
its file, publication code, date, page and URL, and `index.csv` catalogues all 69
`e*.pdf` sheets of that folder and E-55 (publication, date, stocks, material type,
curve sets found, vector/raster, superseded revisions, notes).

The curves were read from the vector strokes of the PDFs (all 69 sheets are
vector; only E-7003 also embeds two bitmaps, and its curves are vector too),
not traced from bitmaps, with
[`scripts/extract_kodak_datasheets.py`](../../../../../scripts/extract_kodak_datasheets.py)
(plot finding and axis calibration in `scripts/kodak_plots.py`; the
catalogue is written by `scripts/kodak_catalog.py`, the batch recipe by
`scripts/kodak_recipes.py`). Plots are located from their headings and tick
labels (frames differ between sheets), axes are calibrated from the tick
labels snapped to the printed tick/grid lines, Kodak's bar notation for
negative logarithms (1̄.0 = -1.0) is decoded, and polylines are simplified to
0.02 pt (about 0.001 density). Typical accuracy is 0.1-0.3 pt on the page
(about 0.5-1.5 nm, 0.005-0.015 log H or density) on top of the accuracy of
the original drawing. Each folder's `info.txt` lists the source, process,
densitometry, the density at which sensitivity is defined, the calibration
(labels used/dropped, residuals) and caveats; `extraction_summary.json`
collects the same for all records and `records.csv` lists them.

The data are Eastman Kodak Company's; they are included, like the other
data-sheet data spektrafilm is built on, as measurements digitised from
publicly published technical documents, with attribution, for simulation
purposes. The profiles built from them carry the CC BY-SA 4.0 profile licence
of this repository and name their source sheet in `metadata.datasource`.

## Records

| record | product (as on the sheet) | publication | file, page | class | profile |
|---|---|---|---|---|---|
| `negative/kodak_portra_160nc_e190` | KODAK PROFESSIONAL PORTRA 160NC | E-190 (May 2003) | e190-1.pdf p. 9 | negative | `kodak_portra_160nc_e190` |
| `negative/kodak_portra_160vc_e190` | KODAK PROFESSIONAL PORTRA 160VC | E-190 (May 2003) | e190-1.pdf p. 10 | negative | `kodak_portra_160vc_e190` |
| `negative/kodak_portra_400nc_e190` | KODAK PROFESSIONAL PORTRA 400NC | E-190 (May 2003) | e190-1.pdf p. 11 | negative | `kodak_portra_400nc_e190` |
| `negative/kodak_portra_400vc_e190` | KODAK PROFESSIONAL PORTRA 400VC | E-190 (May 2003) | e190-1.pdf p. 12 | negative | `kodak_portra_400vc_e190` |
| `negative/kodak_portra_400uc_e190` | KODAK PROFESSIONAL PORTRA 400UC | E-190 (May 2003) | e190-1.pdf p. 13 | negative | `kodak_portra_400uc_e190` |
| `negative/kodak_portra_800_e190` | KODAK PROFESSIONAL PORTRA 800 | E-190 (May 2003) | e190-1.pdf p. 14;15 | negative | `kodak_portra_800_e190` |
| `negative/kodak_portra_160nc_e190_1998` | KODAK PROFESSIONAL PORTRA 160NC | E-190 (November 1998) | e190.pdf p. 8 | negative | — (superseded revision; the current sheet is built) |
| `negative/kodak_portra_160vc_e190_1998` | KODAK PROFESSIONAL PORTRA 160VC | E-190 (November 1998) | e190.pdf p. 9 | negative | — (superseded revision; the current sheet is built) |
| `negative/kodak_portra_400nc_e190_1998` | KODAK PROFESSIONAL PORTRA 400NC | E-190 (November 1998) | e190.pdf p. 10 | negative | — (superseded revision; the current sheet is built) |
| `negative/kodak_portra_400vc_e190_1998` | KODAK PROFESSIONAL PORTRA 400VC | E-190 (November 1998) | e190.pdf p. 11 | negative | — (superseded revision; the current sheet is built) |
| `negative/kodak_portra_100t_e2468` | KODAK PROFESSIONAL PORTRA 100T | E-2468 (May 2003) | e2468.pdf p. 5 | negative | `kodak_portra_100t_e2468` |
| `negative/kodak_ektapress_pj100_e116` | KODAK PROFESSIONAL EKTAPRESS PJ100 | E-116 (April 2003) | e116-1.pdf p. 5 | negative | `kodak_ektapress_pj100_e116` |
| `negative/kodak_ektapress_pj400_e116` | KODAK PROFESSIONAL EKTAPRESS PJ400 | E-116 (April 2003) | e116-1.pdf p. 6;7 | negative | `kodak_ektapress_pj400_e116` |
| `negative/kodak_ektapress_pj800_e116` | KODAK PROFESSIONAL EKTAPRESS PJ800 | E-116 (April 2003) | e116-1.pdf p. 7;8 | negative | `kodak_ektapress_pj800_e116` |
| `negative/kodak_ektapress_pj100_e116_1999` | KODAK PROFESSIONAL EKTAPRESS PJ100 | E-116 (March 1999) | e116.pdf p. 5 | negative | — (superseded revision; the current sheet is built) |
| `negative/kodak_ektapress_pj400_e116_1999` | KODAK PROFESSIONAL EKTAPRESS PJ400 | E-116 (March 1999) | e116.pdf p. 6;7 | negative | — (superseded revision; the current sheet is built) |
| `negative/kodak_ektapress_pj800_e116_1999` | KODAK PROFESSIONAL EKTAPRESS PJ800 | E-116 (March 1999) | e116.pdf p. 7;8 | negative | — (superseded revision; the current sheet is built) |
| `negative/kodak_pro_100_e182` | KODAK Pro 100 [PRN] | E-182 (February 1997) | e182.pdf p. 8 | negative | `kodak_pro_100_e182` |
| `negative/kodak_pro_100t_e182` | KODAK Pro 100T [PRT] | E-182 (February 1997) | e182.pdf p. 9 | negative | `kodak_pro_100t_e182` |
| `negative/kodak_pro_400_e182` | KODAK Pro 400 [PPF] | E-182 (February 1997) | e182.pdf p. 10 | negative | `kodak_pro_400_e182` |
| `negative/kodak_pro_400mc_e182` | KODAK Pro 400 MC [PMC] | E-182 (February 1997) | e182.pdf p. 11 | negative | `kodak_pro_400mc_e182` |
| `negative/kodak_pro_1000_e182` | KODAK Pro 1000 [PMZ] | E-182 (February 1997) | e182.pdf p. 12 | negative | `kodak_pro_1000_e182` |
| `negative/kodak_pro_100t_e29` | KODAK Pro 100T [PRT] | E-29 (April 1999) | e29.pdf p. 4 | negative | `kodak_pro_100t_e29` |
| `negative/kodak_pro_image_100_e4l` | KODAK PROFESSIONAL PRO IMAGE 100 | E-4L (July 1997) | e4L.pdf p. 3 | negative | `kodak_pro_image_100_e4l` |
| `negative/kodak_vericolor_iii_e26` | KODAK VERICOLOR III Professional [VPS] | E-26 (April 1997) | e26.pdf p. 4 | negative | `kodak_vericolor_iii_e26` |
| `negative/kodak_royal_gold_400_e7007` | KODAK ROYAL GOLD 400 [RC] | E-7007 (March 2002) | e7007.pdf p. 5 | negative | `kodak_royal_gold_400_e7007` |
| `negative/kodak_max_versatility_400_e2330` | KODAK MAX Versatility (400) | E-2330 (June 2001) | e2330.pdf p. 3;4 | negative | `kodak_max_versatility_400_e2330` |
| `negative/kodak_max_versatility_plus_800_e2452` | KODAK MAX Versatility Plus (800) | E-2452 (June 2001) | e2452.pdf p. 5 | negative | `kodak_max_versatility_plus_800_e2452` |
| `negative/kodak_bright_sun_flash_200_e2329` | KODAK Bright Sun & Flash [GB] (200) | E-2329 (July 2003) | e2329.pdf p. 3;4 | negative | `kodak_bright_sun_flash_200_e2329` |
| `negative/kodak_advantix_100_e46` | KODAK ADVANTIX 100 (APS) | E-46 (February 1998) | e46.pdf p. 5 | negative | `kodak_advantix_100_e46` |
| `negative/kodak_advantix_200_e46` | KODAK ADVANTIX 200 (APS) | E-46 (February 1998) | e46.pdf p. 6 | negative | `kodak_advantix_200_e46` |
| `negative/kodak_advantix_400_e46` | KODAK ADVANTIX 400 (APS) | E-46 (February 1998) | e46.pdf p. 7 | negative | `kodak_advantix_400_e46` |
| `negative/kodak_advantix_100_e7003` | KODAK ADVANTiX 100 (APS) | E-7003 (February 2002) | e7003.pdf p. 6 | negative | `kodak_advantix_100_e7003` |
| `negative/kodak_advantix_bright_sun_flash_hd200_e7003` | KODAK ADVANTiX Bright Sun & Flash / High Definition 200 (APS) | E-7003 (February 2002) | e7003.pdf p. 6;7 | negative | `kodak_advantix_bright_sun_flash_hd200_e7003` |
| `negative/kodak_advantix_versatility_e7003` | KODAK ADVANTiX Versatility (APS) | E-7003 (February 2002) | e7003.pdf p. 7;8 | negative | `kodak_advantix_versatility_e7003` |
| `negative/kodak_profoto_100_e2e` | KODAK PROFESSIONAL PROFOTO 100 | E-2E (July 1997) | e2e.pdf p. 3 | negative | `kodak_profoto_100_e2e` |
| `negative/kodak_supra_100_e2519` | KODAK PROFESSIONAL SUPRA 100 | E-2519 (May 2003) | e2519.pdf p. 7 | negative | `kodak_supra_100_e2519` |
| `negative/kodak_supra_400_e2519` | KODAK PROFESSIONAL SUPRA 400 | E-2519 (May 2003) | e2519.pdf p. 8 | negative | `kodak_supra_400_e2519` |
| `negative/kodak_supra_800_e2519` | KODAK PROFESSIONAL SUPRA 800 | E-2519 (May 2003) | e2519.pdf p. 9;10 | negative | `kodak_supra_800_e2519` |
| `negative/kodak_supra_200_e4029` | KODAK PROFESSIONAL SUPRA 200 | E-4029 (May 2003) | e4029.pdf p. 7 | negative | `kodak_supra_200_e4029` |
| `negative/kodak_supra_400_e4029` | KODAK PROFESSIONAL SUPRA 400 | E-4029 (May 2003) | e4029.pdf p. 8 | negative | — (same curves as the E-4026 ROYAL SUPRA sheet; records only) |
| `negative/kodak_supra_800_e4029` | KODAK PROFESSIONAL SUPRA 800 | E-4029 (May 2003) | e4029.pdf p. 9;10 | negative | — (same curves as the E-4026 ROYAL SUPRA sheet; records only) |
| `negative/kodak_royal_supra_200_e4026` | KODAK PROFESSIONAL ROYAL SUPRA 200 | E-4026 (June 2002) | e4026.pdf p. 7 | negative | `kodak_royal_supra_200_e4026` |
| `negative/kodak_royal_supra_400_e4026` | KODAK PROFESSIONAL ROYAL SUPRA 400 | E-4026 (June 2002) | e4026.pdf p. 8 | negative | `kodak_royal_supra_400_e4026` |
| `negative/kodak_royal_supra_800_e4026` | KODAK PROFESSIONAL ROYAL SUPRA 800 | E-4026 (June 2002) | e4026.pdf p. 9;10 | negative | `kodak_royal_supra_800_e4026` |
| `negative/kodak_ultra_color_100uc_e4035` | KODAK PROFESSIONAL ULTRA COLOR 100UC | E-4035 (May 2007) | e4035.pdf p. 6 | negative | `kodak_ultra_color_100uc_e4035` |
| `negative/kodak_ultra_color_400uc_e4035` | KODAK PROFESSIONAL ULTRA COLOR 400UC | E-4035 (May 2007) | e4035.pdf p. 7 | negative | `kodak_ultra_color_400uc_e4035` |
| `negative/kodak_le100_le1` | KODAK PROFESSIONAL Law Enforcement LE100 | LE-1 (October 1998) | le1.pdf p. 5 | negative | `kodak_le100_le1` |
| `negative/kodak_le400_le1` | KODAK PROFESSIONAL Law Enforcement LE400 | LE-1 (October 1998) | le1.pdf p. 6;7 | negative | `kodak_le400_le1` |
| `negative/kodak_le800_le1` | KODAK PROFESSIONAL Law Enforcement LE800 | LE-1 (October 1998) | le1.pdf p. 7;8 | negative | `kodak_le800_le1` |
| `positive/kodak_ektachrome_64_e8` | KODAK EKTACHROME 64 Professional [EPR] | E-8 (June 2003) | e8.pdf p. 5 | positive | `kodak_ektachrome_64_e8` |
| `positive/kodak_ektachrome_100_e27` | KODAK EKTACHROME 100 Professional [EPN] | E-27 (June 2003) | e27-1.pdf p. 5 | positive | `kodak_ektachrome_100_e27` |
| `positive/kodak_ektachrome_100_e27_1998` | KODAK EKTACHROME 100 Professional [EPN] | E-27 (May 1998) | e27.pdf p. 5 | positive | — (superseded revision; the current sheet is built) |
| `positive/kodak_ektachrome_100_plus_e113` | KODAK EKTACHROME 100 PLUS Professional [EPP] | E-113 (June 2003) | e113-1.pdf p. 5 | positive | `kodak_ektachrome_100_plus_e113` |
| `positive/kodak_ektachrome_100_plus_e113_1997` | KODAK EKTACHROME 100 PLUS Professional [EPP] | E-113 (April 1997) | e113.pdf p. 5 | positive | — (superseded revision; the current sheet is built) |
| `positive/kodak_ektachrome_64t_e130` | KODAK EKTACHROME 64T Professional [EPY] | E-130 (June 2003) | e130-1.pdf p. 5 | positive | `kodak_ektachrome_64t_e130` |
| `positive/kodak_ektachrome_64t_e130_1997` | KODAK EKTACHROME 64T Professional [EPY] | E-130 (February 1997) | e130.pdf p. 3 | positive | — (superseded revision; the current sheet is built) |
| `positive/kodak_ektachrome_160t_e144` | KODAK EKTACHROME 160T Professional [EPT] | E-144 (June 2003) | e144.pdf p. 4;5 | positive | `kodak_ektachrome_160t_e144` |
| `positive/kodak_ektachrome_320t_e145` | KODAK EKTACHROME 320T Professional [EPJ] | E-145 (June 2003) | e145.pdf p. 5 | positive | `kodak_ektachrome_320t_e145` |
| `positive/kodak_ektachrome_p1600_e147` | KODAK EKTACHROME P1600 Professional [EPH] | E-147 (June 2003) | e147.pdf p. 5 | positive | `kodak_ektachrome_p1600_e147` |
| `positive/kodak_ektachrome_400x_e161` | KODAK EKTACHROME 400X Professional [EPL] | E-161 (June 2003) | e161.pdf p. 5 | positive | `kodak_ektachrome_400x_e161` |
| `positive/kodak_ektachrome_e100vs_e163` | KODAK PROFESSIONAL EKTACHROME E100VS | E-163 (2001) | e163-1.pdf p. 5 | positive | `kodak_ektachrome_e100vs_e163` |
| `positive/kodak_ektachrome_e100vs_e163_1998` | KODAK PROFESSIONAL EKTACHROME E100VS | E-163 (December 1998) | e163.pdf p. 5 | positive | — (superseded revision; the current sheet is built) |
| `positive/kodak_ektachrome_e100s_e164` | KODAK PROFESSIONAL EKTACHROME E100S | E-164 (June 2003) | e164.pdf p. 5;6 | positive | `kodak_ektachrome_e100s_e164` |
| `positive/kodak_ektachrome_e100sw_e164` | KODAK PROFESSIONAL EKTACHROME E100SW | E-164 (June 2003) | e164.pdf p. 5;6 | positive | `kodak_ektachrome_e100sw_e164` |
| `positive/kodak_ektachrome_e200_e28` | KODAK PROFESSIONAL EKTACHROME E200 | E-28 (December 2002) | e28-1.pdf p. 5 | positive | `kodak_ektachrome_e200_e28` |
| `positive/kodak_ektachrome_e200_e28_1999` | KODAK PROFESSIONAL EKTACHROME E200 | E-28 (February 1999) | e28.pdf p. 5 | positive | — (superseded revision; the current sheet is built) |
| `positive/kodak_ektachrome_e100g_e4024` | KODAK PROFESSIONAL EKTACHROME E100G | E-4024 (July 2003) | e4024.pdf p. 5;6 | positive | `kodak_ektachrome_e100g_e4024` |
| `positive/kodak_ektachrome_e100gx_e4024` | KODAK PROFESSIONAL EKTACHROME E100GX | E-4024 (July 2003) | e4024.pdf p. 5;6 | positive | `kodak_ektachrome_e100gx_e4024` |
| `positive/kodak_elite_chrome_100_e7014` | KODAK ELITE Chrome 100 | E-7014 (January 2003) | e7014.pdf p. 3;4 | positive | `kodak_elite_chrome_100_e7014` |
| `positive/kodak_elite_chrome_extra_color_100_e126` | KODAK ELITE Chrome Extra Color 100 | E-126 (September 1998) | e126.pdf p. 5 | positive | `kodak_elite_chrome_extra_color_100_e126` |
| `positive/kodak_elite_chrome_200_e148` | KODAK ELITE Chrome 200 | E-148 (January 1998) | e148.pdf p. 4 | positive | `kodak_elite_chrome_200_e148` |
| `positive/kodak_elite_chrome_160t_e154` | KODAK ELITE Chrome 160T | E-154 (January 1998) | e154.pdf p. 3;4 | positive | `kodak_elite_chrome_160t_e154` |
| `positive/kodak_kodachrome_25_e55` | KODAK KODACHROME 25 Professional [PKM] | E-55 (June 2009) | e55.pdf p. 3 | positive | `kodak_kodachrome_25_e55` |
| `positive/kodak_kodachrome_64_e55` | KODAK KODACHROME 64 Professional [PKR] | E-55 (June 2009) | e55.pdf p. 4 | positive | `kodak_kodachrome_64_e55` |
| `positive/kodak_kodachrome_200_e55` | KODAK KODACHROME 200 Professional [PKL] | E-55 (June 2009) | e55.pdf p. 5 | positive | `kodak_kodachrome_200_e55` |
| `other/kodak_ektachrome_duplicating_edupe_e2529` | KODAK PROFESSIONAL EKTACHROME Duplicating Film EDUPE | E-2529 (May 2002) | e2529.pdf p. 6;7 | duplicating | — (duplicating film, not a camera film) |
| `paper/kodak_portra_iii_e140` | KODAK PROFESSIONAL PORTRA III Paper | E-140 (July 2002) | e140.pdf p. 5 | paper | `kodak_portra_iii_e140` |
| `paper/kodak_supra_iii_e141` | KODAK PROFESSIONAL SUPRA III Paper | E-141 (July 2002) | e141.pdf p. 6 | paper | `kodak_supra_iii_e141` |
| `paper/kodak_ultra_iii_e142` | KODAK PROFESSIONAL ULTRA III Paper | E-142 (January 2003) | e142.pdf p. 6 | paper | `kodak_ultra_iii_e142` |
| `paper/kodak_ektacolor_edge_7_e19` | KODAK EKTACOLOR Edge 7 Paper | E-19 (July 2003) | e19.pdf p. 5 | paper | `kodak_ektacolor_edge_7_e19` |
| `paper/kodak_ektacolor_royal_vii_e23` | KODAK EKTACOLOR ROYAL VII Paper | E-23 (July 2003) | e23.pdf p. 5 | paper | `kodak_ektacolor_royal_vii_e23` |
| `paper/kodak_color_metallic_e4005` | KODAK PROFESSIONAL Color Metallic Paper | E-4005 (April 2003) | e4005.pdf p. 5;6 | paper | `kodak_color_metallic_e4005` |
| `paper/kodak_ultra_endura_e4020` | KODAK PROFESSIONAL ULTRA ENDURA Paper | E-4020 (July 2003) | e4020.pdf p. 7 | paper | `kodak_ultra_endura_e4020` |
| `paper/kodak_portra_endura_e4021` | KODAK PROFESSIONAL PORTRA ENDURA Paper | E-4021 (October 2003) | e4021.pdf p. 9;10 | paper | `kodak_portra_endura_e4021` |
| `paper/kodak_supra_endura_e4021` | KODAK PROFESSIONAL SUPRA ENDURA Paper | E-4021 (October 2003) | e4021.pdf p. 9;10 | paper | `kodak_supra_endura_e4021` |
| `paper/kodak_endura_metallic_e4028` | KODAK PROFESSIONAL ENDURA Metallic Paper | E-4028 (June 2003) | e4028.pdf p. 7;8 | paper | `kodak_endura_metallic_e4028` |
| `paper/kodak_royal_generations_e7009` | KODAK ROYAL Generations Paper | E-7009 (September 2002) | e7009.pdf p. 5 | paper | `kodak_royal_generations_e7009` |
| `paper/kodak_edge_generations_e7010` | KODAK EDGE Generations Paper | E-7010 (September 2002) | e7010.pdf p. 5 | paper | `kodak_edge_generations_e7010` |
| `paper/kodak_duraclear_e143` | KODAK PROFESSIONAL DURACLEAR Display Material | E-143 (January 2003) | e143.pdf p. 4 | display | `kodak_duraclear_e143` (film support) |
| `paper/kodak_duratrans_e143` | KODAK PROFESSIONAL DURATRANS Display Material | E-143 (January 2003) | e143.pdf p. 5 | display | `kodak_duratrans_e143` (film support) |
| `paper/kodak_duraflex_e143` | KODAK PROFESSIONAL DURAFLEX Print Material | E-143 (January 2003) | e143.pdf p. 6 | paper | `kodak_duraflex_e143` |
| `paper/kodak_endura_transparency_e4030` | KODAK PROFESSIONAL ENDURA Transparency Optical Display Material | E-4030 (October 2002) | e4030.pdf p. 5 | display | `kodak_endura_transparency_e4030` (film support) |
| `paper/kodak_endura_clear_e4030` | KODAK PROFESSIONAL ENDURA Clear Optical Display Material | E-4030 (October 2002) | e4030.pdf p. 5 | display | `kodak_endura_clear_e4030` (film support) |
| `paper/kodak_digital_paper_2976_e118` | KODAK PROFESSIONAL Digital Paper, Type 2976 | E-118 (April 1997) | e118.pdf p. 3 | paper_digital | — (digital-exposure material: laser/LED printers, not optical enlarging) |
| `paper/kodak_digital_iii_e2446` | KODAK PROFESSIONAL Digital III Color Paper | E-2446 (May 2003) | e2446.pdf p. 4 | paper_digital | — (digital-exposure material: laser/LED printers, not optical enlarging) |
| `paper/kodak_duraflex_plus_digital_e4014` | KODAK PROFESSIONAL DURAFLEX Plus Digital Display Material | E-4014 (May 2002) | e4014.pdf p. 4 | paper_digital | — (digital-exposure material: laser/LED printers, not optical enlarging) |
| `paper/kodak_endura_transparency_digital_e4031` | KODAK PROFESSIONAL ENDURA Transparency Digital Display Material | E-4031 (October 2003) | e4031.pdf p. 5 | display_digital | — (digital-exposure material) |
| `paper/kodak_endura_clear_digital_e4031` | KODAK PROFESSIONAL ENDURA Clear Digital Display Material | E-4031 (October 2003) | e4031.pdf p. 5 | display_digital | — (digital-exposure material) |
| `paper/kodak_radiance_iii_e1766` | KODAK EKTACHROME RADIANCE III Paper | E-1766 (February 2003) | e1766.pdf p. 5 | reversal_paper | — (reversal paper: positive-to-positive printing, no runtime path) |
| `paper/kodak_radiance_iii_copy_e2410` | KODAK EKTACHROME RADIANCE III Copy Paper | E-2410 (February 2003) | e2410.pdf p. 3;4 | reversal_paper | — (reversal paper: positive-to-positive printing, no runtime path) |
| `paper/kodak_radiance_iii_hc_copy_e2411` | KODAK EKTACHROME RADIANCE III HC Copy Paper | E-2411 (February 2003) | e2411.pdf p. 4 | reversal_paper | — (reversal paper: positive-to-positive printing, no runtime path) |
| `paper/kodak_radiance_iii_overhead_e2412a` | KODAK EKTACHROME RADIANCE III Overhead Material | E-2412A (February 2003) | e2412a.pdf p. 3 | reversal_paper | — (reversal paper: positive-to-positive printing, no runtime path) |
| `paper/kodak_radiance_iii_clear_display_e2412b` | KODAK EKTACHROME RADIANCE III Clear Display Material | E-2412B (February 2003) | e2412b.pdf p. 4 | reversal_paper | — (reversal paper: positive-to-positive printing, no runtime path) |
| `paper/kodak_radiance_iii_translucent_display_e2413` | KODAK EKTACHROME RADIANCE III Translucent Display Material | E-2413 (February 2003) | e2413.pdf p. 4 | reversal_paper | — (reversal paper: positive-to-positive printing, no runtime path) |

Sheets without curves (catalogued in `index.csv`, no record): E-103BF, E-103CP,
E-103NF (selection guides), E-11 (Pathways to Color), E-30 (storage and care),
E-176 (post-processing treatments and image stability), E-24 (VERICOLOR Slide
Film: exposure and processing data only), E-119 (DURATRANS / DURACLEAR Plus
Digital: text only) and E-4013 (Day/Night Digital Display Material).

## What is in a record

* Colour negative films: `log_sensitivity_{r,g,b}`, `density_curve_{r,g,b}`
  (status M, total density), `dye_density_{mid,min}` (mid-scale neutral and
  minimum spectral density; the builder reconstructs C/M/Y from them), and
  `mtf_{r,g,b}` where printed.
* Reversal films, papers and display materials: `log_sensitivity_{r,g,b}`,
  `density_curve_{r,g,b}` (status A, total density), `dye_density_{c,m,y}`
  (peak-normalised as printed) and, where the sheet draws it, the visual-neutral
  sum `dye_density_neutral` (kept for reference); `mtf*` where printed.
* Sheets covering several stocks (E-190 Portra, E-116 Ektapress, E-182 Pro,
  E-46 / E-7003 Advantix, E-164 E100S/SW, E-4024 E100G/GX, E-4021 Portra/Supra
  Endura, E-143 Duratrans/Duraclear/Duraflex, E-4030 / E-4031 Endura
  Transparency/Clear) are split into one record per stock. Where several stocks
  share a plot (e.g. E-4021's single sensitivity and dye plots) the shared
  curves are copied into each record.
* Superseded revisions (E-113, E-116, E-130, E-163, E-190, E-27, E-28 have an
  older and a `-1` revision) are kept as records with the year appended
  (`..._e190_1998`); profiles are built from the current revision only.

## Profiles

`recipes.csv` is the batch recipe of the 66 profiles
(`spektrafilm-profile-builder batch recipes.csv`):

* 28 colour negatives: status M, D55 (T for the tungsten stocks), sensitivity
  defined at the density the sheet states (0.2 over D-min; 1.0 for VERICOLOR
  III), `data_trustability` 1.0 and the grey-ramp refinement on
  `kodak_portra_endura`, as upstream's Kodak negatives; target print
  `kodak_portra_endura`.
* 21 reversal films (18 E-6 and the three K-14 KODACHROMEs of E-55): status A,
  scanned mid-grey anchored at 18.4 % (`log_sensitivity_density_over_min` = 1.0,
  the E.N.D. the sheets state).
* 17 print materials (`type: paper` in the recipe): 13 reflection papers
  (`support: paper`) and 4 backlit display transparencies (DURATRANS,
  DURACLEAR, ENDURA Transparency and Clear, `support: film` like
  `kodak_2383`), all `stage: printing`, status A, enlarger illuminant TH-KG3,
  viewed under D50, built like upstream's `process_paper_profile`, with log
  exposure 0 finally put where the print renders 18.4 % luminance under D50
  (shipped papers print mid-grey at about 0.46 sRGB; these print it at
  0.455-0.48).

## Caveats

* Kodak sheets plot sensitivity relative to the exposure that gives the stated
  density; for papers the sheets do not state it and 1.0 (the shipped paper
  convention) is recorded.
* EKTACHROME P1600 (E-147) only publishes E-6P push-2 curves; that is what the
  profile models (the film is meant to be pushed).
* EKTACOLOR Edge 7 (E-19) and EKTACOLOR Royal VII (E-23) print identical
  curves (different figure numbers); both profiles are built since they are
  separate products.
* The translucent display materials (ENDURA Transparency, DURATRANS) have a
  diffusing base of status-A density about 0.3; the runtime views every print
  under the same normalised illuminant (no backlight adaptation), so their
  whites render at roughly half luminance. DURACLEAR and ENDURA Clear have
  clear bases. ENDURA Transparency's magenta dye is printed only to 640 nm and
  is continued with a decay.
* RADIANCE III Translucent Display Material (E-2413): the characteristic plot
  has no numeric density axis, so the record has no `density_curve_*`.
* Cross-check against the raw curves upstream used (`a6dbcfd^`): KODAK
  EKTACOLOR Edge agrees with E-19 within 0.006-0.009 (dye density RMS),
  0.016-0.076 (log sensitivity RMS) and 0.04 (density); ULTRA Endura (E-4020)
  within about 0.05-0.2. Upstream's `kodak_portra_endura` spectral
  sensitivities sit about 50 nm shorter than E-4021's (whose peaks match every
  other RA-4 paper sheet), so its raw data most likely came from another source
  or carry a wavelength-axis offset; the shipped profile is unchanged.

## filmcolors.org negatives (PROFOTO, SUPRA, ROYAL SUPRA, ULTRA COLOR, LE)

Six more sheets listed in the [filmcolors.org](https://filmcolors.org/) Kodak
timeline, all vector PDFs: E-2E PROFOTO 100 (July 1997), E-2519 SUPRA 100 /
400 / 800 (May 2003, with its discontinuance notice), E-4029 SUPRA 200 / 400 /
800 (May 2003), E-4026 ROYAL SUPRA 200 / 400 / 800 (June 2002), E-4035 ULTRA
COLOR 100UC / 400UC (May 2007), mirrored at <https://125px.com/docs/film/kodak/>
(saved locally under the plain stem; `SOURCE_FILES` in the extractor gives
the full URL), and LE-1 Law Enforcement Films LE100 / LE400 / LE800 (October
1998) at <https://125px.com/docs/unsorted/kodak/le1.pdf> (filmcolors.org
links a 2003 reprint). `index.csv` catalogues them too (76 rows).

* **SUPRA editions.** E-2519 describes the original SUPRA films; the 2003
  SUPRA 200 / 400 / 800 of E-4029 print the ROYAL SUPRA curves of E-4026
  (all curves agree within 0.001 density / log H). SUPRA 100 / 400 / 800 are
  built from E-2519, SUPRA 200 (only on E-4029) from E-4029, ROYAL SUPRA from
  E-4026; E-4029 SUPRA 400 / 800 are records only.
* **Plots used.** Normal-process characteristic curves only (push 1 / push 2
  and ULTRA COLOR 400UC at EI 800 are not used); ULTRA COLOR 400UC's MTF on
  p. 8 is not read (frame not detected), 100UC's is.
* **Estimates** (not on the sheets, also written into each profile's
  `metadata.datasource`): individual CMY dyes reconstructed by the builder
  from the mid-scale neutral and D-min curves, sensitivity tails beyond the
  printed curves, hanatos2025 adaptation parameters (donors pinned to
  upstream's Kodak still negatives and the E-series negatives above), and the
  interlayer DIR strength (runtime default, except ULTRA COLOR 100UC / 400UC:
  `film_render_overrides` 1.4 / 1.25, ColorChecker C* 44.5 / 46.0 -> 49.7
  against PORTRA 400UC 49.6, since E-4035 sells them as the most saturated
  Kodak negatives).
* **ROYAL SUPRA / SUPRA 200 dyes.** Their mid-scale neutral rises steeply
  below 400 nm (to D 2.5 at 380 nm), which the generic dye start reproduces
  less well: reconstruction cost 0.27-0.41 against 0.003-0.19 for the other
  sheets.

## KODACHROME 25 / 64 / 200 (E-55, June 2009)

E-55 pages 3, 4 and 5 give each stock its characteristic curves (status A,
K-14, daylight), spectral sensitivities (E.N.D. 1.00, 250-750 nm axis),
spectral dye densities (normalised to a visual density of 1.0 for a 3200 K
viewing illuminant, cyan / magenta / yellow / visual neutral) and MTF. All
curves are vector strokes. The dye plots have no top frame label above 1.0 and
the cyan dye (peak about 1.2-1.3) and the visual neutral (about 1.3-1.4) run
above the highest y label, so for these sheets the extractor reads the dye
plot up to the top of its frame (`frame_top` selector option). Checked by
overlaying the CSVs on 600 dpi renders of the pages: every extracted point lies
on a printed stroke (at most 0.12 pt from a dark pixel).

Not on the sheet, so **estimate placeholders** (named in each profile's
`metadata.datasource`):

* dye densities outside the printed range (420-700 nm for 25/64, 410-700 nm for
  200): `dye_extension: hold_decay` holds the first printed value towards
  380 nm and decays the last one (25 nm) towards 780 nm, instead of the default
  NaN (opaque);
* sensitivity tails below the printed log -2 and beyond the printed wavelengths
  (e.g. the KODACHROME 25 cyan-forming layer beyond 702 nm, the blue-forming
  layer below 420 nm): the builder's usual smooth tail continuation;
* KODACHROME 25 base+fog: its characteristic curves stop at log H +0.63 while
  still falling (D 0.16-0.18), so the toe fit lands below zero (R -0.095);
  `density_min` 0.10/0.10/0.10 is assumed (the 64 / 200 toe fits give
  0.085-0.17);
* interlayer (interimage) strength: `film_render_overrides/<stock>.json`,
  `dir_couplers_interlayer_scale` 1.4 for all three (see that README).

The hanatos2025 adaptation donors are pinned (`adaptation_donors`) to the Kodak
positives shipped before E-55. Cross-checks: the KODACHROME 25 sensitivities
have area-normalised mean wavelengths of 447.7 / 554.5 / 632.3 nm (B/G/R,
printed range) against 444.3 / 554.8 / 632.0 nm from the analysis of the 1980
E-77 curves at <https://visns.neocities.org/4x5LFphotography/HGWK>; upstream's
`kodak_kodachrome_64` matches the E-55 KODACHROME 64 dyes within 0.002 RMS
(peak-normalised) and its R/G sensitivities within 0.014 log RMS.
