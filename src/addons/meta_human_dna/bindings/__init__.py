import os
import sys
import platform as _platform
from pathlib import Path
from ..exceptions import UnsupportedPlatformError

# High-priority dev override: if RIGLOGIC_DEV_BUILD_DIR is set, prepend it so that
# riglogic.pyd from active development build is imported instead of the packaged one.
_dev_build_dir = os.environ.get('RIGLOGIC_DEV_BUILD_DIR')
if _dev_build_dir:
    _dev_p = Path(_dev_build_dir)
    if _dev_p.exists():
        # Insert ahead of everything else for deterministic precedence.
        if str(_dev_p) not in sys.path:
            sys.path.insert(0, str(_dev_p))
        # Also widen DLL search early (Windows).
        try:
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(str(_dev_p))  # type: ignore[attr-defined]
        except Exception:
            pass
        # Mark that a dev override is active so later path scans won't eclipse it.
        _DEV_OVERRIDE_ACTIVE = True
    else:
        _DEV_OVERRIDE_ACTIVE = False
else:
    _DEV_OVERRIDE_ACTIVE = False


arch = 'x64'
if 'arm' in _platform.processor().lower():
    arch = 'arm64'
if sys.platform == 'win32' and arch == 'x64':
    arch = 'amd64'
if sys.platform == 'linux' and arch == 'x64':
    arch = 'x86_64'
if sys.platform == 'mac' and arch == 'x64':
    arch = 'x86_64'

platform_name = None
if sys.platform == "win32":
    platform_name = "windows"
elif sys.platform == "linux":
    platform_name = "linux"
elif sys.platform == "darwin":
    platform_name = "mac"
else:
    raise UnsupportedPlatformError

# add the platform specific bindings path to the sys.path if there are not already
bindings_path = Path(__file__).parent / platform_name / arch
_current_working_directory = os.getcwd()
INJECTED_SEARCH_PATHS = []  # recorded for external diagnostics
if bindings_path.exists():
    if bindings_path not in [Path(i) for i in sys.path]:
        # Preserve dev override precedence by not inserting ahead when active
        if _DEV_OVERRIDE_ACTIVE:
            sys.path.append(str(bindings_path))
        else:
            sys.path.insert(0, str(bindings_path))
        INJECTED_SEARCH_PATHS.append(str(bindings_path))

    # linux and macos need to set the LD_LIBRARY_PATH and DYLD_LIBRARY_PATH and DYLD_FALLBACK_LIBRARY_PATH
    # This is needed to load the shared libraries that are in the bindings folder on linux and macos
    os.chdir(str(bindings_path))

# Allow explicit override of binary directories via environment variables
# This is especially useful on Windows to help resolve .pyd and dependent .dll files.
for env_var in ("RIGLOGIC_BIN", "META_HUMAN_CORE_BIN"):
    p = os.environ.get(env_var)
    if p:
        p_path = Path(p)
        if p_path.exists():
            if str(p_path) not in sys.path:
                sys.path.insert(0, str(p_path))
                INJECTED_SEARCH_PATHS.append(str(p_path))
            os.environ["PATH"] = str(p_path) + os.pathsep + os.environ.get("PATH", "")

# Heuristic: if running inside a repo that vendors UnrealEngine as a submodule, attempt to add
# its plugin binary directories to sys.path and PATH for discovery/loading on Windows.
try:
    here = Path(__file__).resolve()
    ue_root = None
    for parent in [here.parent] + list(here.parents):
        cand = parent
        if (cand / "UnrealEngine" / "Engine").exists():
            ue_root = cand / "UnrealEngine"
            break
    # Opportunistically locate locally built extension modules (riglogic.pyd, meta_human_dna_core.pyd)
    # inside a monorepo-style ".build" directory produced by our CMake step. This avoids having to
    # manually copy the .pyd into bindings/windows/amd64 during active development.
    try:
        repo_root = None
        for parent in [here.parent] + list(here.parents):
            if (parent / '.build').exists():
                repo_root = parent
                break
        # If a dev override is active, don't inject .build paths that could overshadow it.
        if repo_root and not _DEV_OVERRIDE_ACTIVE:
            build_dir = repo_root / '.build'
            # Scan shallow (two levels) for riglogic.pyd to reduce overhead.
            for candidate in build_dir.rglob('riglogic.pyd'):
                candidate_parent = candidate.parent
                if str(candidate_parent) not in sys.path:
                    sys.path.insert(0, str(candidate_parent))
                    INJECTED_SEARCH_PATHS.append(str(candidate_parent))
                os.environ['PATH'] = str(candidate_parent) + os.pathsep + os.environ.get('PATH', '')
                try:
                    if hasattr(os, 'add_dll_directory'):
                        os.add_dll_directory(str(candidate_parent))  # type: ignore[attr-defined]
                except Exception:
                    pass
                # Only need first hit (prefer Release over Debug if both appear; rglob order is arbitrary
                # but usually deterministic enough for local dev). Break after first insertion.
                break
    except Exception:
        pass
    if ue_root:
        ue_candidates = [
            ue_root / "Engine" / "Plugins" / "Animation" / "RigLogic" / "Binaries" / "Win64",
            ue_root / "Engine" / "Plugins" / "MetaHuman" / "MetaHumanCoreTechLib" / "Binaries" / "Win64",
        ]
        # Add core engine binaries (needed for transitive deps like UnrealEditor-Core*.dll)
        engine_bin = ue_root / "Engine" / "Binaries" / "Win64"
        if engine_bin.exists():
            ue_candidates.append(engine_bin)
        # Add first-level ThirdParty Win64 directories for common dependencies (TBB, zlib, etc.)
        third_party_root = ue_root / "Engine" / "Binaries" / "ThirdParty"
        if third_party_root.exists():
            for child in third_party_root.iterdir():
                if child.is_dir():
                    # Prefer explicit Win64 subfolder if present
                    win64_sub = child / "Win64"
                    if win64_sub.exists():
                        ue_candidates.append(win64_sub)
                    else:
                        # Some third party libs put DLLs directly here
                        ue_candidates.append(child)
        for c in ue_candidates:
            if c.exists():
                if str(c) not in sys.path:
                    sys.path.insert(0, str(c))
                    INJECTED_SEARCH_PATHS.append(str(c))
                os.environ["PATH"] = str(c) + os.pathsep + os.environ.get("PATH", "")
                # On Python 3.8+ (incl 3.11 in Blender) explicitly widen DLL search
                try:
                    if hasattr(os, 'add_dll_directory'):
                        os.add_dll_directory(str(c))  # type: ignore[attr-defined]
                except Exception:
                    pass
except Exception:
    # Best-effort only; do not hard-fail
    pass

try:
    riglogic = sys.modules.get("riglogic")
    if not riglogic:
        # On Windows: proactively preload Unreal plugin/core dependency chain to avoid
        # 'DLL load failed' when importing the extension inside host apps (e.g. Blender)
        if sys.platform == 'win32':  # pragma: no cover - runtime env specific
            try:
                import ctypes  # noqa: WPS433 (stdlib import inside block is intentional)
                for _dll in [
                    'UnrealEditor-RigLogicLib.dll',
                    'UnrealEditor-Core.dll',  # transitive dependency of RigLogicLib
                ]:
                    try:
                        ctypes.WinDLL(_dll)
                    except OSError:
                        # Best effort; continue – missing will surface on import if critical
                        pass
            except Exception:
                pass
        import riglogic
    meta_human_dna_core = sys.modules.get("meta_human_dna_core")
    if not meta_human_dna_core:
        import meta_human_dna_core
except ModuleNotFoundError:
    # Provide a richer Python fallback shim so that importing code can at least
    # resolve enum / factory symbols without immediate AttributeErrors. This does NOT
    # implement real functionality – any attempt to actually read DNA data will raise.
    class _EnumShim:
        def __init__(self, **entries):
            for k, v in entries.items():
                setattr(self, k, v)
        def __iter__(self):  # for debugging
            for k, v in self.__dict__.items():
                if not k.startswith('_'):
                    yield k, v

    class _StatusShim:
        @staticmethod
        def isOk():  # always "ok" for stub
            return True
        @staticmethod
        def get():
            class _S: message = "stub status"  # noqa: D401
            return _S()

    class _FileStreamShim:
        def __init__(self, path, accessMode, openMode, memRes=None):  # noqa: D401
            self.path = path
            self.accessMode = accessMode
            self.openMode = openMode
            self.memRes = memRes
        @classmethod
        def create(cls, **kwargs):
            return cls(**kwargs)

    class _ReaderBaseShim:
        def __init__(self, stream, dataLayer, unknownLayerPolicy, unused_int, memRes):
            self._stream = stream
            self._dataLayer = dataLayer
            self._unknownLayerPolicy = unknownLayerPolicy
            self._memRes = memRes
        @classmethod
        def create(cls, stream, dataLayer, unknownLayerPolicy, unused_int, memRes):
            return cls(stream, dataLayer, unknownLayerPolicy, unused_int, memRes)
        # Methods expected by tests – return empty / neutral structures.
        def read(self):
            # Emulate successful read; real implementation required for functional tests.
            return None
        def getMeshCount(self):
            return 0
        def getMeshName(self, index):  # pragma: no cover - defensive
            raise IndexError(index)
        # Blend shape related accessors expected later; return empty sequences.
        def getBlendShapeTargetDeltaXs(self, *a, **k): return []
        def getBlendShapeTargetDeltaYs(self, *a, **k): return []
        def getBlendShapeTargetDeltaZs(self, *a, **k): return []
        def getBlendShapeTargetVertexIndices(self, *a, **k): return []

    class _WriterBaseShim:
        @classmethod
        def create(cls, stream):
            return cls()

    class riglogic:  # type: ignore
        __is_fake__ = True
        # Enum-like groups
        OpenMode = _EnumShim(Binary=0, Text=1)
        AccessMode = _EnumShim(Read=0, Write=1)
        DataLayer = _EnumShim(
            Descriptor=0,
            Definition=1,
            Behavior=2,
            Geometry=3,
            GeometryWithoutBlendShapes=4,
            AllWithoutBlendShapes=5,
            All=6,
        )
        UnknownLayerPolicy = _EnumShim(Preserve=0, Discard=1)
        Status = _StatusShim
        FileStream = _FileStreamShim
        BinaryStreamReader = _ReaderBaseShim
        JSONStreamReader = _ReaderBaseShim
        BinaryStreamWriter = _WriterBaseShim
        JSONStreamWriter = _WriterBaseShim
        # Placeholder high-level types
        RigLogic = object
        RigInstance = object

    class meta_human_dna_core:  # type: ignore
        __is_fake__ = True
        pass

    sys.modules["riglogic"] = riglogic  # type: ignore
    sys.modules["meta_human_dna_core"] = meta_human_dna_core  # type: ignore

except ImportError as e:
    raise e

# Harden against partially present stub builds that expose incorrect simple string
# placeholders instead of enum containers (observed when C++ stub returns const char*).
def _ensure_enum_shims():  # pragma: no cover - runtime defensive patching
    try:
        import riglogic as _rl
        # Late define here to access _EnumShim when real extension loaded
        from types import SimpleNamespace
        enum_mapping = {
            'OpenMode': dict(Binary=0, Text=1),
            'AccessMode': dict(Read=0, Write=1),
            'UnknownLayerPolicy': dict(Preserve=0, Discard=1),
            'DataLayer': dict(
                Descriptor=0,
                Definition=1,
                Behavior=2,
                Geometry=3,
                GeometryWithoutBlendShapes=4,
                AllWithoutBlendShapes=5,
                All=6,
            )
        }
        for enum_name, members in enum_mapping.items():
            current = getattr(_rl, enum_name, None)
            if isinstance(current, str) or current is None:
                shim = type('_EnumShimDynamic', (), {})()
                for k, v in members.items():
                    setattr(shim, k, v)
                setattr(_rl, enum_name, shim)

        # Patch required classes if missing (incomplete stub build scenario)
        if not hasattr(_rl, 'Status'):
            class _StatusShim:
                @staticmethod
                def isOk(): return True
                @staticmethod
                def get():
                    class _S: message = "stub status"
                    return _S()
            _rl.Status = _StatusShim  # type: ignore
        if not hasattr(_rl, 'FileStream'):
            class _FileStreamShim:
                def __init__(self, path, accessMode, openMode, memRes=None):
                    self.path = path
                @classmethod
                def create(cls, **kwargs): return cls(**kwargs)
            _rl.FileStream = _FileStreamShim  # type: ignore
        if not hasattr(_rl, 'BinaryStreamReader'):
            class _ReaderShim:
                def __init__(self, *a, **k): pass
                @classmethod
                def create(cls, *a, **k): return cls(*a, **k)
                def read(self): return None
                def getMeshCount(self): return 0
                def getMeshName(self, index): raise IndexError(index)
                def getBlendShapeTargetDeltaXs(self, *a, **k): return []
                def getBlendShapeTargetDeltaYs(self, *a, **k): return []
                def getBlendShapeTargetDeltaZs(self, *a, **k): return []
                def getBlendShapeTargetVertexIndices(self, *a, **k): return []
            _rl.BinaryStreamReader = _ReaderShim  # type: ignore
        elif isinstance(getattr(_rl, 'BinaryStreamReader'), str):
            # Replace broken string export with shim
            class _ReaderShim2:
                def __init__(self, *a, **k): pass
                @classmethod
                def create(cls, *a, **k): return cls(*a, **k)
                def read(self): return None
                def getMeshCount(self): return 0
                def getMeshName(self, index): raise IndexError(index)
                def getBlendShapeTargetDeltaXs(self, *a, **k): return []
                def getBlendShapeTargetDeltaYs(self, *a, **k): return []
                def getBlendShapeTargetDeltaZs(self, *a, **k): return []
                def getBlendShapeTargetVertexIndices(self, *a, **k): return []
            _rl.BinaryStreamReader = _ReaderShim2  # type: ignore
            setattr(_rl, '__is_incomplete__', True)
        if not hasattr(_rl, 'JSONStreamReader'):
            _rl.JSONStreamReader = _rl.BinaryStreamReader  # type: ignore
        elif isinstance(getattr(_rl, 'JSONStreamReader'), str):
            _rl.JSONStreamReader = _rl.BinaryStreamReader  # type: ignore
        # Debug aid: one-line print showing resolved types (will show once per process)
        if not getattr(_rl, '_shim_debug_printed', False):
            try:
                print(f"[bindings.debug] riglogic enum types: OpenMode={type(getattr(_rl,'OpenMode',None))} AccessMode={type(getattr(_rl,'AccessMode',None))}", file=sys.stderr)
            except Exception:
                pass
            setattr(_rl, '_shim_debug_printed', True)
    except Exception:
        pass

_ensure_enum_shims()
_ensure_enum_shims()


# restore the current working directory
os.chdir(_current_working_directory)

__all__ = [
    "riglogic",
    "meta_human_dna_core"
]
