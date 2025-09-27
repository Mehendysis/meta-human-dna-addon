import os
import sys
import math
import platform

ARCH = 'x64'
if 'arm' in platform.processor().lower():
    ARCH = 'arm64'
if sys.platform == 'win32' and ARCH == 'x64':
    ARCH = 'amd64'
if sys.platform == 'linux' and ARCH == 'x64':
    ARCH = 'x86_64'


OS_NAME = 'windows'
if sys.platform == 'darwin':
    OS_NAME = 'mac'
elif sys.platform == 'linux':
    OS_NAME = 'linux'

# Ensure that the riglogic module is not reloaded. Original expected layout:
#   <repo>/meta-human-dna-bindings/<os>/<arch>/riglogic*.pyd
# Our build/staging currently places them under the addon: 
#   <repo>/meta-human-dna-addon/src/addons/meta_human_dna/bindings/<os>/<arch>/

_binding_search_paths: list[str] = []

# 1. Explicit env override
env_dir = os.environ.get("DNA_BINDINGS_DIR")
if env_dir:
    _binding_search_paths.append(env_dir)

cwd_repo_guess = os.getcwd()

# 2. Original expected path
_binding_search_paths.append(os.path.join(cwd_repo_guess, os.pardir, 'meta-human-dna-bindings', OS_NAME, ARCH))

# 3. Addon staging path (absolute preferred)
_addon_bindings_abs = os.path.abspath(os.path.join(cwd_repo_guess, 'meta-human-dna-addon', 'src', 'addons', 'meta_human_dna', 'bindings', OS_NAME, ARCH))
_binding_search_paths.append(_addon_bindings_abs)

for p in _binding_search_paths:
    if p and os.path.isdir(p) and p not in sys.path:
        sys.path.append(p)

def _attempt_riglogic_import():
    if "riglogic" in sys.modules:
        return True
    try:
        import riglogic  # type: ignore  # noqa: F401
        sys.modules["riglogic"] = riglogic  # type: ignore
        return True
    except Exception:  # noqa: BLE001
        # Soft failure: check manifest to see if this is an expected dll_missing state
        try:
            from pathlib import Path as _P
            manifest = _P(__file__).resolve().parents[1] / 'src' / 'addons' / 'meta_human_dna' / 'bindings' / OS_NAME / ARCH / 'BINDINGS_MANIFEST.json'
            if manifest.exists():
                import json as _json
                data = _json.loads(manifest.read_text())
                rl = data.get('modules', {}).get('riglogic', {})
                if rl.get('status') == 'dll_missing':
                    print('[conftest] riglogic import skipped (dll_missing per manifest).')
                    return False
        except Exception:
            pass
        # Fallback to previous hard error for unexpected absence
        raise

_attempt_riglogic_import()


import pytest # noqa: E402
import shutil # noqa: E402
from typing import TYPE_CHECKING, Any
try:  # pragma: no cover - only executed when Blender available
    import bpy  # type: ignore  # noqa: E402, F401
    from mathutils import Vector, Euler  # type: ignore  # noqa: E402
except Exception:  # noqa: BLE001
    if TYPE_CHECKING:
        from typing import Any as Vector  # type: ignore
        from typing import Any as Euler  # type: ignore
    else:
        class _Dummy:
            def __init__(self, *a: Any, **k: Any):
                pass
            def __iter__(self):
                return iter(())
            def __repr__(self):
                return 'Dummy()'
        Vector = Euler = _Dummy  # type: ignore
        print('[conftest] Blender not available; using dummy Vector/Euler for non-Blender tests.')
from pathlib import Path # noqa: E402
from constants import REPO_ROOT # noqa: E402

def pytest_configure():
    """
    Installs the bindings for the addon.
    """

    bindings_source_folder = REPO_ROOT.parent / 'meta-human-dna-bindings'
    core_source_folder = REPO_ROOT.parent / 'meta-human-dna-core'
    bindings_destination_folder = REPO_ROOT / 'src' / 'addons' / 'meta_human_dna' / 'bindings'

    

    bindings_specific_source_folder = bindings_source_folder / OS_NAME / ARCH
    bindings_specific_destination_folder = bindings_destination_folder / OS_NAME / ARCH

    # Copy the bindings folder to the src directory if they doesn't exist
    if not bindings_specific_destination_folder.exists():
        if not bindings_specific_source_folder.exists():
            raise FileNotFoundError(
                f'The bindings in "{bindings_specific_destination_folder}" are missing. '
                'Please add them to run the tests.'
            )

        # Copy the bindings to the destination folder
        shutil.copytree(
            src=bindings_specific_source_folder,
            dst=bindings_specific_destination_folder,
            dirs_exist_ok=True
        )
        
    # If running tests on the CI, copy core to the specific destination folder
    core_destination_folder = bindings_specific_destination_folder / 'meta_human_dna_core'
    if core_source_folder.exists() and not core_destination_folder.exists() and os.environ.get('RUNNING_CI'):
        shutil.copytree(
            src=core_source_folder,
            dst=core_destination_folder,
            dirs_exist_ok=True
        )   

    # ensure the addon module is on the python path
    sys.path.append(str(REPO_ROOT / 'src' / 'addons'))
        

if not os.environ.get('TEST_MANIFEST_ONLY'):
    from fixtures.addon import addon  # noqa: E402, F401
    from fixtures.dna_data import (  # noqa: E402, F401
        original_dna_json_data,
        exported_dna_json_data,
        calibrated_dna_json_data
    )
    from fixtures.scene import (  # noqa: E402, F401
        load_dna,
        head_bmesh,
        head_armature,
        modify_scene
    )
else:
    print('[conftest] TEST_MANIFEST_ONLY set: skipping heavy Blender fixtures.')

@pytest.fixture(scope='session')
def addons() -> list:
    return [
        ('meta_human_dna', Path(__file__).parent.parent / 'src')
    ]

@pytest.fixture(scope='session')
def dna_folder_name() -> str:
    return 'ada'

@pytest.fixture(scope='session')
def import_shape_keys() -> bool:
    return False

@pytest.fixture(scope='session')
def import_lods() -> list:
    return [
        'lod0'
    ]

@pytest.fixture(scope='session')
def changed_head_bone_name() -> str:
    return 'FACIAL_C_12IPV_Chin3' # has no children

@pytest.fixture(scope='session')
def changed_head_bone_location() -> tuple[Vector, Vector]:
    # change bone location (blender value, dna value)
    return (
        Vector((0.0, 0.005, 0.02)),  # relative change blender value Z-up
        # Vector((0.0671469, 0.319794, 9.78912)), # original dna value Y-up
        Vector((0.0671469, 0.643585, 11.8251)) # new dna value Y-up
    )

@pytest.fixture(scope='session')
def changed_head_bone_rotation() -> tuple[Euler, Euler]:
    # change rotation of bone (blender value, dna value)
    return (
        Euler((
        math.radians(60),
        math.radians(0),
        math.radians(0)
        )),
        Euler((60.0, 0.0, 0.0))
    )

@pytest.fixture(scope='session')
def changed_head_mesh_name() -> str:
    return 'head_lod0_mesh'

@pytest.fixture(scope='session')
def changed_head_vertex_index() -> int:
    return 11955

@pytest.fixture(scope='session')
def changed_head_vertex_location() -> tuple[Vector, Vector, Vector]:
    # change vertex location (blender value, dna value)
    # Moves vertex on the back of the head up 0.01 meters
    return (
        Vector((0.008358, 0.059853, 1.75288)),  # new blender value Z-up
        Vector((0.85206276, 170.66174, -4.644782)),  # original dna value Y-up
        Vector((0.8358, 175.288, -5.9853077)), # new dna value Y-up
    )

@pytest.fixture(scope='session')
def temp_folder():
    temp_folder = Path(__file__).parent / 'temp'
    if temp_folder.exists():
        shutil.rmtree(temp_folder)  

    os.makedirs(temp_folder, exist_ok=True)
    
    yield temp_folder

    # Cleanup the temp folder
    if not os.environ.get('TESTS_KEEP_TEMP_FOLDER'):
        if temp_folder.exists():
            shutil.rmtree(temp_folder)


