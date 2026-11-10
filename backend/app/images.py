from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SPEC = spec_from_file_location(
    "campusconnect_imaging",
    Path(__file__).resolve().parents[1] / "lambda" / "image_processor" / "imaging.py",
)
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
thumbnail_bytes = _MODULE.thumbnail_bytes
