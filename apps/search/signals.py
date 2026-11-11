"""Keep SearchOffer in sync: every relevant save schedules a rebuild of the affected contexts after commit."""

from django.db import transaction
from django.db.models.signals import m2m_changed, post_save

from apps.catalog.models import PracticeContext, Service, SpecialistProfile
from apps.geo.models import Address

from .builder import rebuild_for_context


def schedule_rebuild(context_ids) -> None:
    for context_id in set(context_ids):
        transaction.on_commit(lambda context_id=context_id: rebuild_for_context(context_id))


def _on_context_saved(sender, instance, **kwargs):
    schedule_rebuild([instance.pk])


def _on_profile_saved(sender, instance, **kwargs):
    schedule_rebuild(instance.contexts.values_list("pk", flat=True))


def _on_profile_translation_saved(sender, instance, **kwargs):
    schedule_rebuild(PracticeContext.objects.filter(specialist_id=instance.master_id).values_list("pk", flat=True))


def _on_service_saved(sender, instance, **kwargs):
    schedule_rebuild([instance.context_id])


def _on_service_translation_saved(sender, instance, **kwargs):
    schedule_rebuild(Service.objects.filter(pk=instance.master_id).values_list("context_id", flat=True))


def _on_address_saved(sender, instance, **kwargs):
    schedule_rebuild(Service.objects.filter(addresses=instance).values_list("context_id", flat=True))


def _on_m2m_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """Handles both directions: `instance` is the profile/service, or (reverse) a reference/address row."""
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    if isinstance(instance, SpecialistProfile):
        schedule_rebuild(instance.contexts.values_list("pk", flat=True))
    elif isinstance(instance, Service):
        schedule_rebuild([instance.context_id])
    elif reverse and pk_set:
        # a reference row or address changed its profiles/services; the other side is in pk_set
        if sender in PROFILE_M2M_THROUGH:
            schedule_rebuild(PracticeContext.objects.filter(specialist_id__in=pk_set).values_list("pk", flat=True))
        else:
            schedule_rebuild(Service.objects.filter(pk__in=pk_set).values_list("context_id", flat=True))


PROFILE_M2M_THROUGH = {
    SpecialistProfile.specialist_types.through,
    SpecialistProfile.conditions.through,
    SpecialistProfile.methods.through,
    SpecialistProfile.languages.through,
}
SERVICE_M2M_THROUGH = {
    Service.conditions.through,
    Service.methods.through,
    Service.languages.through,
    Service.addresses.through,
}

post_save.connect(_on_context_saved, sender=PracticeContext, dispatch_uid="search_context_saved")
post_save.connect(_on_profile_saved, sender=SpecialistProfile, dispatch_uid="search_profile_saved")
post_save.connect(
    _on_profile_translation_saved, sender=SpecialistProfile._parler_meta.root_model, dispatch_uid="search_profile_tr_saved"
)
post_save.connect(_on_service_saved, sender=Service, dispatch_uid="search_service_saved")
post_save.connect(
    _on_service_translation_saved, sender=Service._parler_meta.root_model, dispatch_uid="search_service_tr_saved"
)
post_save.connect(_on_address_saved, sender=Address, dispatch_uid="search_address_saved")
for _through in PROFILE_M2M_THROUGH | SERVICE_M2M_THROUGH:
    m2m_changed.connect(_on_m2m_changed, sender=_through, dispatch_uid=f"search_m2m_{_through.__name__}")
