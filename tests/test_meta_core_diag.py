def test_meta_core_diag():
    import meta_human_dna_core as m
    print('[diag] meta_human_dna_core.__file__=', getattr(m, '__file__', None))
    attrs = sorted([a for a in dir(m) if a[0].isalpha()])
    print('[diag] exported attrs (subset)=', attrs[:60])
    assert hasattr(m, 'CAPABILITIES'), 'CAPABILITIES missing from module'
    print('[diag] CAPABILITIES=', m.CAPABILITIES)
    assert m.CAPABILITIES['tier'] == 3, f"Expected tier 3 got {m.CAPABILITIES.get('tier')}"
    assert m.CAPABILITIES['vertex_transforms'] is True
