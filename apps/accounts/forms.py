from django import forms
from django.utils.translation import gettext_lazy as _

from apps.consents.models import Consent

from .models import Role, User
from .phone import InvalidPhone, normalize_kz_mobile

CONSENT_KINDS = [Consent.USER_AGREEMENT, Consent.PD_PROCESSING]


class PhoneForm(forms.Form):
    phone = forms.CharField(label=_("Номер телефона"), max_length=32)

    def clean_phone(self) -> str:
        try:
            return normalize_kz_mobile(self.cleaned_data["phone"])
        except InvalidPhone:
            raise forms.ValidationError(
                _("Введите казахстанский мобильный номер, например +7 701 123 45 67")
            ) from None


class CodeForm(forms.Form):
    code = forms.CharField(label=_("Код из SMS"), max_length=16)

    def __init__(self, *args, require_consents: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.require_consents = require_consents
        if require_consents:
            for kind in CONSENT_KINDS:
                self.fields[kind] = forms.BooleanField(
                    required=True,
                    error_messages={"required": _("Необходимо ваше согласие, чтобы продолжить")},
                )

    def clean_code(self) -> str:
        return self.cleaned_data["code"].strip()

    @property
    def accepted_kinds(self) -> list[str]:
        return list(CONSENT_KINDS) if self.require_consents else []


class FullNameForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["last_name", "first_name"]
        labels = {"last_name": _("Фамилия"), "first_name": _("Имя")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True


class RegisterForm(FullNameForm):
    """The registration step: the name and who the user is. The role is chosen once."""

    class Meta(FullNameForm.Meta):
        fields = ["last_name", "first_name", "role"]
        labels = {**FullNameForm.Meta.labels, "role": _("Кем вы являетесь?")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].widget = forms.RadioSelect(choices=Role.choices)
        self.initial["role"] = None  # an explicit choice, not the model default

    def clean_role(self) -> str:
        from apps.onboarding.services import is_phone_blocked

        role = self.cleaned_data["role"]
        if role != Role.PARENT and is_phone_blocked(self.instance.phone):
            raise forms.ValidationError(_("С этого номера нельзя подать анкету специалиста или няни"))
        return role
