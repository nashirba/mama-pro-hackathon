import re
import warnings
from io import BytesIO

from django import forms
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

from apps.accounts.models import User
from apps.catalog.models import DevelopmentalCondition
from apps.catalog.visibility import catalog_visible_specialists
from apps.geo.models import KatoNode

from .models import COMMENT_BODY_MAX, Complaint, Post
from .names import is_specialist
from .pii import looks_sensitive

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


# Phone cameras write multi-picture JPEGs that Pillow reports as MPO; they are served as plain JPEG.
IMAGE_TYPES = {"JPEG": "image/jpeg", "MPO": "image/jpeg", "PNG": "image/png"}
SENSITIVE_MESSAGE = _("Похоже, в тексте есть ИИН или телефон. Не публикуйте данные ребёнка.")


class _PostFieldsForm(forms.ModelForm):
    """Shared body, photo, condition and city handling; `upload` holds the validated photo."""

    image = forms.FileField(label=_("Фото"), required=False)
    confirm_sensitive = forms.BooleanField(required=False, widget=forms.HiddenInput)
    condition = forms.ModelChoiceField(
        label=_("Особенность развития"), queryset=DevelopmentalCondition.objects.all(), required=False
    )
    city = forms.ModelChoiceField(
        label=_("Город"), queryset=KatoNode.objects.filter(level=KatoNode.Level.CITY), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.upload: tuple[bytes, str] | None = None
        self.sensitive_warning = False
        self.fields["body"].label = _("Текст")

    @property
    def condition_choices(self) -> list[DevelopmentalCondition]:
        return sorted(DevelopmentalCondition.objects.prefetch_related("translations"), key=lambda c: c.name)

    @property
    def city_choices(self) -> list[KatoNode]:
        qs = KatoNode.objects.filter(level=KatoNode.Level.CITY).prefetch_related("translations")
        return sorted(qs, key=lambda c: c.name)

    def clean_image(self):
        file = self.cleaned_data.get("image")
        if not file:
            return None
        if file.size > settings.COMMUNITY_IMAGE_MAX_BYTES:
            raise forms.ValidationError(_("Фото больше 2 МБ"))
        data = file.read()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as img:
                    fmt = img.format
                    img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            fmt = None
        if fmt not in IMAGE_TYPES:
            raise forms.ValidationError(_("Загрузите фото в формате JPEG или PNG"))
        self.upload = (data, IMAGE_TYPES[fmt])
        return file

    def clean(self):
        cleaned = super().clean()
        body = cleaned.get("body")
        if body and looks_sensitive(body) and not cleaned.get("confirm_sensitive"):
            self.sensitive_warning = True
            self.add_error("body", SENSITIVE_MESSAGE)
        return cleaned


class PostForm(_PostFieldsForm):
    specialist = forms.ModelChoiceField(label=_("Специалист"), queryset=catalog_visible_specialists(), required=False)

    class Meta:
        model = Post
        fields = ["kind", "body", "condition", "city", "specialist"]

    def __init__(self, *args, user: User, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["kind"].label = _("Тип")
        self.fields["kind"].choices = [
            c for c in Post.Kind.choices if not (c[0] == Post.Kind.REVIEW and is_specialist(user))
        ]
        self.initial.setdefault("kind", Post.Kind.QUESTION)
        if self.initial["kind"] not in self.allowed_kinds:
            self.initial["kind"] = Post.Kind.QUESTION

    @property
    def allowed_kinds(self) -> list[str]:
        return [value for value, _label in self.fields["kind"].choices]

    @property
    def current_kind(self) -> str:
        """The kind to show as selected: a submitted value only if it is a real choice."""
        raw = self.data.get("kind") if self.is_bound else self.initial["kind"]
        return raw if raw in self.allowed_kinds else Post.Kind.QUESTION

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind == Post.Kind.REVIEW:
            if not cleaned.get("specialist") and "specialist" not in self.errors:
                self.add_error("specialist", _("Выберите специалиста"))
        elif kind:
            cleaned["specialist"] = None
        return cleaned


class PostEditForm(_PostFieldsForm):
    remove_image = forms.BooleanField(label=_("Удалить фото"), required=False)

    class Meta:
        model = Post
        fields = ["body", "condition", "city"]


class CommentForm(forms.Form):
    body = forms.CharField(label=_("Комментарий"), max_length=COMMENT_BODY_MAX, strip=True, widget=forms.Textarea)


class ComplaintForm(forms.Form):
    reason = forms.ChoiceField(label=_("Причина"), choices=Complaint.Reason.choices, widget=forms.RadioSelect)
    text = forms.CharField(label=_("Пояснение"), max_length=1000, required=False, strip=True, widget=forms.Textarea)
