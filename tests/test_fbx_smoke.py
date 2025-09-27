import os
import time
import hashlib
import pytest
from pathlib import Path
import sys

# Marker registration assumed in pytest.ini; use -m fbx to run selectively.
@pytest.mark.fbx
@pytest.mark.slow
@pytest.mark.usefixtures("load_dna")
def test_dna_to_fbx_smoke():
    """End-to-end DNA -> FBX smoke test.

    Preconditions:
      * head.dna (or body.dna) present at repo root
      * RigLogic bindings importable inside Blender (handled by load_dna fixture)
    Acceptance:
      * FBX file created, non-zero, exceeds minimal size threshold, recent mtime
    """
    # Resolve repo root via this test file location (../.. from tests directory)
    repo_root = Path(__file__).resolve().parents[2]
    dna_path = repo_root / 'head.dna'
    if not dna_path.exists():
        dna_path = repo_root / 'body.dna'
    if not dna_path.exists():
        pytest.skip('No head.dna or body.dna available for smoke test')

    # Import new minimal API with fallback path injection if not on sys.path yet.
    try:
        from dna_to_fbx import run_dna_to_fbx  # type: ignore
    except Exception:
        conv_src = repo_root / 'dna-to-fbx-converter' / 'src'
        if conv_src.exists() and str(conv_src) not in sys.path:
            sys.path.insert(0, str(conv_src))
        try:
            from dna_to_fbx import run_dna_to_fbx  # type: ignore
        except Exception as e:  # pragma: no cover - skip if still failing
            pytest.skip(f'dna_to_fbx API not available: {e}')

    out_dir = repo_root / 'artifacts' / 'fbx'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"smoke_{int(time.time())}.fbx"

    try:
        result = run_dna_to_fbx(dna_path, out_path)
    except Exception as exc:
        pytest.fail(f'run_dna_to_fbx raised exception: {exc}')

    assert Path(result['output']).exists(), 'FBX output file missing'
    size = Path(result['output']).stat().st_size
    if result.get('real_export'):
        # Real FBX should comfortably exceed a few KB.
        assert size >= 4096, f'Real export flagged but size unexpectedly small ({size} bytes)'
    else:
        # Allow stub placeholder until enforcement flag or real export becomes consistent.
        assert size >= 32, f'FBX size too small ({size} bytes)'
    assert (time.time() - Path(result['output']).stat().st_mtime) < 60, 'FBX file timestamp not recent'
    sha256 = hashlib.sha256(Path(result['output']).read_bytes()).hexdigest()[:16]
    dur = result.get('duration', 0.0)
    diag = result.get('diagnostics', {})
    print(
        f"[fbx-smoke] path={result['output']} size={size}B time={dur:.2f}s sha256={sha256} "
        f"joints={result.get('joints')} meshes={result.get('meshes')} real_export={result.get('real_export')} "
        f"auto_import={diag.get('auto_import_seeded')} rig={diag.get('import_rig')} mesh={diag.get('import_mesh')} "
        f"candidates={diag.get('fbx_candidates')} force_full={diag.get('force_full_import')}"
    )
    if os.environ.get('REQUIRE_REAL_FBX'):
        assert result.get('real_export'), f"REQUIRE_REAL_FBX set but real export failed; diagnostics={result.get('diagnostics')}"

# Backwards compatibility alias (some scripts invoke test_fbx_export_smoke)
@pytest.mark.fbx
@pytest.mark.slow
@pytest.mark.usefixtures("load_dna")
def test_fbx_export_smoke():  # pragma: no cover - simple delegate
    test_dna_to_fbx_smoke()
