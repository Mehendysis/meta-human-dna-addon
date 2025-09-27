import json
from pathlib import Path

BIND_DIR = Path(__file__).resolve().parents[1] / 'src' / 'addons' / 'meta_human_dna' / 'bindings' / 'windows' / 'amd64'
MANIFEST = BIND_DIR / 'BINDINGS_MANIFEST.json'

def test_bindings_manifest_core_ok():
    assert MANIFEST.exists(), f"Manifest missing at {MANIFEST}"
    data = json.loads(MANIFEST.read_text())
    modules = data.get('modules', {})
    assert 'meta_human_dna_core' in modules, 'meta_human_dna_core absent from manifest'
    core = modules['meta_human_dna_core']
    assert core.get('status') == 'ok', f"meta_human_dna_core status not ok: {core.get('status')}"
    caps = core.get('caps') or {}
    assert caps.get('tier') == 3, f"Expected tier 3 got {caps.get('tier')}"
    # If partial flag set, ensure riglogic is the only degraded module
    if data.get('partial'):
        degraded = {m: md for m, md in modules.items() if md.get('status') != 'ok'}
        assert set(degraded.keys()) <= {'riglogic'}, f"Unexpected degraded modules: {list(degraded.keys())}"
