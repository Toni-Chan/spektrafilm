"""spektrafilm_profile_builder — build spektrafilm film profiles from
digitised data-sheet curves.

Restored and modernised version of the upstream raw-curve profile factory
(``profiles_factory``, removed from the public repository in 049f677), writing
the current profile JSON schema (``spektrafilm.profiles.io``). Like the GUI and
the LUT creator it sits above the runtime core: it imports ``spektrafilm`` and
the runtime never imports it.
"""

__version__ = '0.1.0'

from .records import RawRecord, load_record  # noqa: E402
from .process import Recipe, BuildReport, build_profile, normalize_sensitivity  # noqa: E402
from .writer import profile_to_json, save_profile_json  # noqa: E402

__all__ = [
    '__version__', 'RawRecord', 'load_record', 'Recipe', 'BuildReport', 'build_profile',
    'normalize_sensitivity', 'profile_to_json', 'save_profile_json',
]
