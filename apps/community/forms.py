import re

from django import forms
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User

NICKNAME_RE = re.compile(r"^[\w ]+$")


class NicknameForm(forms.Form):
    display_name = forms.CharField(label=_("Псевдоним"), min_length=3, max_length=40, strip=True)

    def __init__(self, *args, user: User, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_display_name(self):
        name = " ".join(self.cleaned_data["display_name"].split())
        if not NICKNAME_RE.match(name):
            raise forms.ValidationError(_("Только буквы, цифры, пробел и _"))
        if User.objects.filter(display_name__iexact=name).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError(_("Этот псевдоним уже занят"))
        return name

    def save(self) -> bool:
        """False when another user took the name between validation and save."""
        self.user.display_name = self.cleaned_data["display_name"]
        try:
            with transaction.atomic():
                self.user.save(update_fields=["display_name"])
        except IntegrityError:
            self.add_error("display_name", _("Этот псевдоним уже занят"))
            return False
        return True
