from apps.catalog.visibility import is_catalog_visible


# Ростер зафиксирован, на него опираются Tasks 7-10.
def test_catalog_fixture_roster(catalog_fixture):
    sp = catalog_fixture.specialists
    assert list(sp) == ["ivanova-logoped", "serikov-aba", "kim-neuro", "nurlan-online", "bekova-karaganda", "omarova-home", "sergeev-free", "hidden-logoped"]
    assert [s for s in sp if is_catalog_visible(sp[s].contexts.get())] == list(sp)[:7]
    assert sp["kim-neuro"].methods.filter(slug="tomatis").exists()
    assert not sp["kim-neuro"].has_translation("kk") and sp["ivanova-logoped"].has_translation("kk")
    assert set(sp["serikov-aba"].services().values_list("price_session", flat=True)) == {12000, 6000}
    free = sp["sergeev-free"].services().get()
    assert free.is_free and free.price_session is None
    assert sp["nurlan-online"].formats == ["online"] and not sp["nurlan-online"].services().get().addresses.exists()
    assert sp["omarova-home"].services().get().home_visit_area == catalog_fixture.kato["almaty"]
    assert catalog_fixture.addresses["karaganda"].kato.slug == "karaganda"


def test_kk_rows_fill_every_translated_field(catalog_fixture):
    for slug, p in catalog_fixture.specialists.items():
        if p.has_translation("kk"):
            assert p.safe_translation_getter("bio", language_code="kk") and p.safe_translation_getter("approach", language_code="kk"), slug
