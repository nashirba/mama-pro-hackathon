from apps.catalog.visibility import catalog_visible_specialists, is_specialist_visible


def test_catalog_visible_specialists(catalog_fixture):
    sp = catalog_fixture.specialists
    visible = set(catalog_visible_specialists())
    assert sp["hidden-logoped"] not in visible
    assert sp["ivanova-logoped"] in visible
    assert len(visible) == 7
    for profile in sp.values():
        assert is_specialist_visible(profile) == (profile in visible)
