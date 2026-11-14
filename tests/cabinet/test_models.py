from datetime import date

from apps.cabinet.models import Child
from tests.factories import ChildFactory, UserFactory


def test_has_full_name(db):
    assert UserFactory().has_full_name
    assert not UserFactory(first_name="").has_full_name
    assert not UserFactory(last_name="  ").has_full_name


def test_children_ordered_oldest_first_undated_last(db):
    parent = UserFactory()
    undated = ChildFactory(parent=parent, first_name="Без даты")
    young = ChildFactory(
        parent=parent, first_name="Младший", birth_date=date(2022, 1, 1)
    )
    old = ChildFactory(parent=parent, first_name="Старший", birth_date=date(2019, 1, 1))
    assert list(parent.children.all()) == [old, young, undated]


def test_children_deleted_with_parent(db):
    child = ChildFactory()
    child.parent.delete()
    assert not Child.objects.exists()
