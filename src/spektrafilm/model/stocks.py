from enum import Enum

class FilmStocks(Enum):
    # kodak pro
    kodak_ektar_100 = 'kodak_ektar_100'
    kodak_portra_160 = 'kodak_portra_160'
    kodak_portra_400 = 'kodak_portra_400'
    kodak_portra_800 = 'kodak_portra_800'
    kodak_portra_800_push1 = 'kodak_portra_800_push1'
    kodak_portra_800_push2 = 'kodak_portra_800_push2'
    # kodak consumer
    kodak_gold_200 = 'kodak_gold_200'
    kodak_ultramax_400 = 'kodak_ultramax_400'
    # kodak cine
    kodak_vision3_50d = 'kodak_vision3_50d'
    kodak_vision3_250d = 'kodak_vision3_250d'
    kodak_verita_200d = 'kodak_verita_200d'
    kodak_vision3_200t = 'kodak_vision3_200t'
    kodak_vision3_500t = 'kodak_vision3_500t'
    # fuji pro
    fujifilm_pro_400h = 'fujifilm_pro_400h'
    # fuji consumer
    fujifilm_c200 = 'fujifilm_c200'
    fujifilm_xtra_400 = 'fujifilm_xtra_400'
    # positive
    kodak_ektachrome_100 = 'kodak_ektachrome_100'
    kodak_kodachrome_64 = 'kodak_kodachrome_64'
    fujifilm_velvia_100 = 'fujifilm_velvia_100'
    fujifilm_provia_100f = 'fujifilm_provia_100f'
    # fujifilm professional data guide (AF3-207U, 2005), built with spektrafilm_profile_builder
    # negative
    fujifilm_pro_160s_fdg = 'fujifilm_pro_160s_fdg'
    fujifilm_pro_160c_fdg = 'fujifilm_pro_160c_fdg'
    fujifilm_npl_160_fdg = 'fujifilm_npl_160_fdg'
    fujifilm_pro_400h_fdg = 'fujifilm_pro_400h_fdg'
    fujifilm_pro_800z_fdg = 'fujifilm_pro_800z_fdg'
    fujifilm_superia_reala_fdg = 'fujifilm_superia_reala_fdg'
    fujifilm_superia_100_fdg = 'fujifilm_superia_100_fdg'
    fujifilm_superia_200_fdg = 'fujifilm_superia_200_fdg'
    fujifilm_superia_xtra_400_fdg = 'fujifilm_superia_xtra_400_fdg'
    fujifilm_true_definition_400_fdg = 'fujifilm_true_definition_400_fdg'
    fujifilm_superia_xtra_800_fdg = 'fujifilm_superia_xtra_800_fdg'
    fujifilm_superia_1600_fdg = 'fujifilm_superia_1600_fdg'
    fujifilm_nexia_a200_fdg = 'fujifilm_nexia_a200_fdg'
    fujifilm_nexia_400_fdg = 'fujifilm_nexia_400_fdg'
    fujifilm_nexia_800_fdg = 'fujifilm_nexia_800_fdg'
    # positive
    fujifilm_velvia_50_fdg = 'fujifilm_velvia_50_fdg'
    fujifilm_velvia_100_fdg = 'fujifilm_velvia_100_fdg'
    fujifilm_velvia_100f_fdg = 'fujifilm_velvia_100f_fdg'
    fujifilm_provia_100f_fdg = 'fujifilm_provia_100f_fdg'
    fujifilm_astia_100f_fdg = 'fujifilm_astia_100f_fdg'
    fujifilm_provia_400f_fdg = 'fujifilm_provia_400f_fdg'
    fujifilm_64t_type_ii_fdg = 'fujifilm_64t_type_ii_fdg'
    fujifilm_sensia_100_fdg = 'fujifilm_sensia_100_fdg'
    fujifilm_sensia_200_fdg = 'fujifilm_sensia_200_fdg'
    fujifilm_sensia_400_fdg = 'fujifilm_sensia_400_fdg'

class PrintPapers(Enum):
    kodak_ultra_endura = 'kodak_ultra_endura' # problematic
    kodak_endura_premier = 'kodak_endura_premier'
    kodak_ektacolor_edge = 'kodak_ektacolor_edge'
    kodak_supra_endura = 'kodak_supra_endura'
    kodak_portra_endura = 'kodak_portra_endura'
    fujifilm_crystal_archive_typeii = 'fujifilm_crystal_archive_typeii'
    kodak_2383 = 'kodak_2383'
    kodak_2393 = 'kodak_2393'
