import factory
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.accounts.models import User
from apps.cabinet.models import Child
from apps.catalog.models import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Method,
    PracticeContext,
    ProfileCategory,
    Service,
    ServiceKind,
    SpecialistProfile,
    SpecialistType,
    Training,
)
from apps.community.models import Comment, Post
from apps.favorites.models import Favorite
from apps.geo.models import Address, KatoNode


def _resolve(model, field: str, items) -> list:
    """Accept reference objects or their slugs (language codes)."""
    return [i if isinstance(i, model) else model.objects.get(**{field: i}) for i in items]


def _m2m(name: str, model, field: str):
    """Post-generation M2M declaration: a list of slugs or objects, applied on create only."""

    @factory.post_generation
    def declaration(obj, create, extracted, **kwargs):
        if create and extracted:
            getattr(obj, name).set(_resolve(model, field, extracted))

    return declaration


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    phone = factory.Sequence(lambda n: f"+7700{n:07d}")
    last_name = "Иванова"
    first_name = "Айгуль"


class NicknamedUserFactory(UserFactory):
    """A parent who has already chosen a community nickname."""

    display_name = factory.Sequence(lambda n: f"Мама {n}")


class SpecialistFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SpecialistProfile
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory, role="specialist")
    slug = factory.Sequence(lambda n: f"specialist-{n}")
    display_name = factory.Sequence(lambda n: f"Специалист {n}")
    bio = factory.LazyAttribute(lambda o: f"Био: {o.display_name}")
    approach = factory.LazyAttribute(lambda o: f"Подход: {o.display_name}")
    practice_start_year = factory.LazyFunction(lambda: timezone.localdate().year - 5)
    age_min = 0
    age_max = 18
    formats = factory.LazyFunction(lambda: ["in_person"])

    specialist_types = _m2m("specialist_types", SpecialistType, "slug")
    conditions = _m2m("conditions", DevelopmentalCondition, "slug")
    methods = _m2m("methods", Method, "slug")
    languages = _m2m("languages", CommunicationLanguage, "code")


class PrivateContextFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PracticeContext

    specialist = factory.SubFactory(SpecialistFactory)
    kind = PracticeContext.Kind.PRIVATE
    catalog_enabled = True


class ServiceKindFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ServiceKind
        django_get_or_create = ("slug",)

    slug = "consultation"


class AddressFactory(factory.django.DjangoModelFactory):
    """Needs `kato` or the `kato_demo` fixture (defaults to the demo node `almaty`)."""

    class Meta:
        model = Address

    kato = factory.LazyFunction(lambda: KatoNode.objects.get(slug="almaty"))
    street = "Тестовая"
    building = factory.Sequence(lambda n: str(n + 1))
    point = factory.LazyFunction(lambda: Point(76.9, 43.25, srid=4326))


class ServiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Service
        skip_postgeneration_save = True

    context = factory.SubFactory(PrivateContextFactory)
    kind = factory.SubFactory(ServiceKindFactory)
    title = "Консультация"
    description = ""
    duration_min = 45
    formats = factory.LazyFunction(lambda: ["in_person"])
    price_session = 5000

    @factory.post_generation
    def addresses(obj, create, extracted, **kwargs):
        if create and extracted:
            obj.addresses.set(extracted)

    conditions = _m2m("conditions", DevelopmentalCondition, "slug")
    methods = _m2m("methods", Method, "slug")
    languages = _m2m("languages", CommunicationLanguage, "code")


class NannyFactory(SpecialistFactory):
    """A nanny with a criminal record certificate; add `TrainingFactory` rows to make her visible in the section."""

    user = factory.SubFactory(UserFactory, role="nanny")
    slug = factory.Sequence(lambda n: f"nanny-{n}")
    display_name = factory.Sequence(lambda n: f"Няня {n}")
    category = ProfileCategory.NANNY
    formats = factory.LazyFunction(lambda: ["home_visit"])
    criminal_record_issued_on = factory.LazyFunction(lambda: timezone.localdate().replace(month=1, day=15))
    availability = "Будни с 9 до 18"


class TrainingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Training

    profile = factory.SubFactory(NannyFactory)
    title = factory.Sequence(lambda n: f"Курс {n}")
    issuer = "Учебный центр"
    year = 2024
    hours = 24
    certificate_number = factory.Sequence(lambda n: f"CERT-{n:05d}")
    is_first_aid = False


class NannyServiceFactory(ServiceFactory):
    """Needs the reference data (`childcare`) and the `kato_demo` fixture (the home visit area defaults to `almaty`)."""

    context = factory.SubFactory(PrivateContextFactory, specialist=factory.SubFactory(NannyFactory))
    kind = factory.LazyFunction(lambda: ServiceKind.objects.get(slug="childcare"))
    title = "Услуги няни"
    duration_min = 60
    formats = factory.LazyFunction(lambda: ["home_visit"])
    home_visit_area = factory.LazyFunction(lambda: KatoNode.objects.get(slug="almaty"))
    price_session = None
    price_hour = 3000
    price_night = 15000
    price_month = None


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    author = factory.SubFactory(NicknamedUserFactory)
    kind = Post.Kind.QUESTION
    body = "Текст поста"


class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comment

    post = factory.SubFactory(PostFactory)
    author = factory.SubFactory(NicknamedUserFactory)
    body = "Текст комментария"


class ChildFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Child

    parent = factory.SubFactory(UserFactory)
    first_name = "Арман"


class FavoriteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Favorite

    user = factory.SubFactory(UserFactory)
    profile = factory.SubFactory(SpecialistFactory)
