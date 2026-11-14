from random import Random

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.phone import InvalidPhone, normalize_kz_mobile
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
from apps.demo.generators import (
    NannySpec,
    SpecialistSpec,
    build_addresses,
    build_nanny,
    build_specialist,
    is_online_only,
    load_json,
)
from apps.geo.models import Address, KatoNode
from apps.search.builder import rebuild_all


def _set_translations(obj, fields: dict[str, dict[str, str]]) -> None:
    """Write one translation row per language; `fields` maps a field to {language: text}. ru goes first."""
    for lang in ("ru", "kk"):
        if lang not in next(iter(fields.values())):
            continue
        obj.set_current_language(lang)
        for field, texts in fields.items():
            setattr(obj, field, texts[lang])
        obj.save()


class Command(BaseCommand):
    help = (
        "Fill the demo with synthetic specialists and nannies "
        "(idempotent: a rerun with the same --seed replaces, not duplicates)"
    )

    def add_arguments(self, parser):
        parser.add_argument("--specialists", type=int, default=80)
        parser.add_argument("--nannies", type=int, default=24)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        total, nannies, seed = options["specialists"], options["nannies"], options["seed"]
        if total < 0 or nannies < 0:
            raise CommandError("--specialists and --nannies must not be negative")
        contact_phone = self._contact_phone()

        call_command("load_kato_demo", stdout=self.stdout)
        call_command("seed_reference_data", stdout=self.stdout)

        districts = list(KatoNode.objects.filter(level=KatoNode.Level.DISTRICT).select_related("parent").order_by("slug"))
        if not districts:
            raise CommandError("The demo KATO tree has no districts")
        self.names = load_json("names_ru_kk.json")
        self.bios = load_json("bios.json")
        self.contact_phone = contact_phone
        self.kinds = {k.slug: k for k in ServiceKind.objects.all()}
        rng = Random(seed)
        today = timezone.localdate()
        year = today.year

        in_person_index = 0
        context_ids = []
        # Every save below schedules a SearchOffer rebuild after commit (apps.search.signals). The contexts stay hidden
        # until everything is written, so these rebuilds are cheap no-ops; one rebuild_all() at the end does the real work.
        with transaction.atomic():
            for i in range(total):
                spec = build_specialist(rng, i, self.names, self.bios, year)
                district, addresses = None, []
                if not is_online_only(i):
                    district = districts[in_person_index % len(districts)]  # deterministic: every district gets specialists
                    in_person_index += 1
                    city = district.parent or district
                    streets = self.names["streets"].get(city.slug, self.names["streets"]["default"])
                    center = (district.center.x, district.center.y) if district.center else (city.center.x, city.center.y)
                    addresses = build_addresses(rng, streets, center)
                context_ids.append(self._save(spec, district, addresses))

            # Its own generator, so adding or removing nannies never changes the specialists of a seed.
            nanny_rng = Random(f"nannies:{seed}")
            nanny_data = load_json("nannies.json")
            for i in range(nannies):
                spec = build_nanny(nanny_rng, i, self.names, nanny_data, year, today)
                context_ids.append(self._save_nanny(spec, districts[i % len(districts)]))

        PracticeContext.objects.filter(pk__in=context_ids).update(catalog_enabled=True)
        offers = rebuild_all()
        self.stdout.write(f"Demo specialists: {total}, nannies: {nannies}, search offers: {offers}")

    @staticmethod
    def _contact_phone() -> str:
        value = settings.DEMO_CONTACT_PHONE
        if not value:
            return ""
        try:
            return normalize_kz_mobile(value)
        except InvalidPhone:
            raise CommandError("DEMO_CONTACT_PHONE is not a Kazakhstan mobile number") from None

    def _save(self, spec: SpecialistSpec, district: KatoNode | None, addresses) -> int:
        """Write one specialist; returns the id of the private practice context."""
        user = User.objects.filter(phone=spec.login_phone).first() or User.objects.create_user(
            spec.login_phone, preferred_language=spec.preferred_language
        )
        profile = SpecialistProfile.objects.filter(user=user).first() or SpecialistProfile(user=user, slug=spec.slug)
        profile.display_name = spec.display_name
        profile.practice_start_year = spec.practice_start_year
        profile.age_min, profile.age_max = spec.age_min, spec.age_max
        profile.formats = spec.formats
        profile.whatsapp_phone = profile.public_phone = self.contact_phone
        profile.demo_verification_levels = spec.verification_levels
        _set_translations(profile, {"bio": spec.bio, "approach": spec.approach})
        profile.specialist_types.set(SpecialistType.objects.filter(slug__in=spec.specialist_types))
        profile.conditions.set(DevelopmentalCondition.objects.filter(slug__in=spec.conditions))
        profile.methods.set(Method.objects.filter(slug__in=spec.methods))
        profile.languages.set(CommunicationLanguage.objects.filter(code__in=spec.languages))

        context, _ = PracticeContext.objects.update_or_create(
            specialist=profile, kind=PracticeContext.Kind.PRIVATE, defaults={"catalog_enabled": False}
        )
        self._drop_services(context)
        address_rows = [
            Address.objects.create(kato=district, street=a.street, building=a.building, point=Point(a.lon, a.lat, srid=4326))
            for a in addresses
        ]
        city = (district.parent or district) if district else None
        for s in spec.services:
            service = Service(
                context=context,
                kind=self.kinds[s.kind],
                duration_min=s.duration_min,
                formats=s.formats,
                price_session=s.price_session,
                price_month=s.price_month,
                is_free=s.is_free,
                home_visit_area=city if "home_visit" in s.formats else None,
            )
            _set_translations(service, {"title": s.title, "description": s.description})
            if "in_person" in s.formats:
                service.addresses.set(address_rows)
        return context.pk

    def _save_nanny(self, spec: NannySpec, district: KatoNode) -> int:
        """Write one nanny with her courses and her childcare service; returns the id of the private practice context."""
        user = User.objects.filter(phone=spec.login_phone).first() or User.objects.create_user(
            spec.login_phone, preferred_language=spec.preferred_language
        )
        profile = SpecialistProfile.objects.filter(user=user).first() or SpecialistProfile(user=user, slug=spec.slug)
        profile.category = ProfileCategory.NANNY
        profile.display_name = spec.display_name
        profile.practice_start_year = spec.practice_start_year
        profile.age_min, profile.age_max = spec.age_min, spec.age_max
        profile.formats = ["home_visit"]
        profile.whatsapp_phone = profile.public_phone = self.contact_phone
        profile.demo_verification_levels = []
        profile.criminal_record_issued_on = spec.criminal_record_issued_on
        _set_translations(profile, {"bio": spec.bio, "approach": spec.approach, "availability": spec.availability})
        profile.specialist_types.clear()
        profile.methods.clear()
        profile.conditions.set(DevelopmentalCondition.objects.filter(slug__in=spec.conditions))
        profile.languages.set(CommunicationLanguage.objects.filter(code__in=spec.languages))

        profile.trainings.all().delete()
        for t in spec.trainings:
            training = Training(
                profile=profile,
                issuer=t.issuer,
                year=t.year,
                hours=t.hours,
                certificate_number=t.certificate_number,
                is_first_aid=t.is_first_aid,
            )
            _set_translations(training, {"title": {lang: t.title[lang] for lang in spec.bio}})

        context, _ = PracticeContext.objects.update_or_create(
            specialist=profile, kind=PracticeContext.Kind.PRIVATE, defaults={"catalog_enabled": False}
        )
        self._drop_services(context)
        service = Service(
            context=context,
            kind=self.kinds["childcare"],
            duration_min=60,
            formats=["home_visit"],
            price_hour=spec.price_hour,
            price_night=spec.price_night,
            price_month=spec.price_month,
            home_visit_area=district,
        )
        _set_translations(service, {"title": spec.service_title, "description": spec.service_description})
        return context.pk

    @staticmethod
    def _drop_services(context: PracticeContext) -> None:
        """A rerun replaces the services and addresses of the specialist, so nothing is duplicated."""
        services = Service.objects.filter(context=context)
        address_ids = list(Address.objects.filter(services__in=services).values_list("pk", flat=True).distinct())
        services.delete()
        Address.objects.filter(pk__in=address_ids).delete()
