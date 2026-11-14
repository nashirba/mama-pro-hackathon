from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import FullNameForm

from .models import Child


def not_in_future(value: date | None) -> None:
    if value is not None and value > timezone.localdate():
        raise ValidationError(_("Дата рождения не может быть в будущем"))


class ProfileForm(FullNameForm):
    class Meta(FullNameForm.Meta):
        fields = ["last_name", "first_name", "birth_date"]
        labels = {**FullNameForm.Meta.labels, "birth_date": _("Дата рождения")}
        widgets = {
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "birth_date": forms.DateInput(
                attrs={"type": "date", "autocomplete": "bday"}, format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].required = False

    def clean_birth_date(self):
        value = self.cleaned_data["birth_date"]
        not_in_future(value)
        return value


class ChildForm(forms.ModelForm):
    class Meta:
        model = Child
        fields = ["first_name", "last_name", "birth_date", "sex"]
        labels = {
            "first_name": _("Имя"),
            "last_name": _("Фамилия"),
            "birth_date": _("Дата рождения"),
            "sex": _("Пол"),
        }
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sex"].choices = [("", _("Не указан")), *Child.Sex.choices]

    def clean_birth_date(self):
        value = self.cleaned_data["birth_date"]
        not_in_future(value)
        return value
