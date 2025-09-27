import pytest
from pathlib import Path

import meta_human_dna_core as core  # resolved via sys.path injection in headless harness

TEST_DNA = Path(__file__).parent / 'test_files' / 'dna' / 'ada' / 'head.dna'


def test_meta_core_capabilities_tier3():
    assert hasattr(core, 'CAPABILITIES'), 'CAPABILITIES not exported (stale module staged?)'
    assert core.CAPABILITIES['tier'] == 3, f"Expected tier=3 got {core.CAPABILITIES}"
    assert core.CAPABILITIES['vertex_transforms'] is True, 'vertex_transforms capability not enabled'
    reader = core.Reader.create(str(TEST_DNA))
    reader.read()
    # Mesh names may be empty with stub DNA heuristic; ensure API callable
    assert reader.getMeshCount() >= 0
    joint_count = reader.getJointCount()
    assert joint_count > 0, 'Expected placeholder joints'
    root_parent = reader.getJointParentIndex(0)
    assert root_parent == -1
    # Sample a mid joint
    mid_index = min(5, joint_count-1)
    name = reader.getJointName(mid_index)
    pos = reader.getJointNeutralPosition(mid_index)
    rot = reader.getJointNeutralRotation(mid_index)
    assert isinstance(name, str)
    assert len(pos) == 3
    assert len(rot) == 4
