from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.urls import reverse, translate_url
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.consents.services import record_consents

from .forms import CodeForm, FullNameForm, PhoneForm
from .models import User
from .otp import OtpLocked, issue_code, verify_code

SESSION_PHONE = "login_phone"


def _safe_next(request) -> str:
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return ""


def login_view(request):
    next_url = _safe_next(request)
    if request.method == "POST":
        form = PhoneForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone"]
            issue_code(phone)
            request.session[SESSION_PHONE] = phone
            url = reverse("accounts:verify")
            if next_url:
                url += "?" + urlencode({"next": next_url})
            return redirect(url)
    else:
        form = PhoneForm()
    return render(request, "accounts/phone_form.html", {"form": form, "next": next_url})


def _language_redirect(user: User, target: str):
    response = redirect(target)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        user.preferred_language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    return response


def _login_response(request, user: User, next_url: str):
    lang = user.preferred_language
    if next_url:
        target = translate_url(next_url, lang)
    else:
        with translation.override(lang):
            target = reverse("core:home")
    return _language_redirect(user, target)


def _otp_login_allowed(user: User) -> bool:
    return user.is_active and not user.is_staff and not user.is_superuser


def verify_view(request):
    phone = request.session.get(SESSION_PHONE)
    if not phone:
        return redirect("accounts:login")
    user = User.objects.filter(phone=phone).first()
    is_new = user is None
    next_url = _safe_next(request)

    if request.method == "POST":
        form = CodeForm(request.POST, require_consents=is_new)
        # Consents are validated before the code so an incomplete registration does not burn an attempt.
        if form.is_valid() and not is_new and not _otp_login_allowed(user):
            # Staff and inactive accounts never log in with the public demo code.
            form.add_error("code", _("Неверный или просроченный код"))
        elif form.is_valid():
            try:
                code_ok = verify_code(phone, form.cleaned_data["code"])
            except OtpLocked:
                form.add_error("code", _("Слишком много неверных попыток. Запросите новый код."))
            else:
                if code_ok:
                    if is_new:
                        user, _created = User.objects.get_or_create(
                            phone=phone, defaults={"preferred_language": request.LANGUAGE_CODE}
                        )
                        record_consents(user, form.accepted_kinds, request.META.get("REMOTE_ADDR", ""))
                    login(request, user)
                    request.session.pop(SESSION_PHONE, None)
                    if is_new:
                        with translation.override(user.preferred_language):
                            target = reverse("accounts:register")
                        if next_url:
                            target += "?" + urlencode({"next": next_url})
                        return _language_redirect(user, target)
                    return _login_response(request, user, next_url)
                form.add_error("code", _("Неверный или просроченный код"))
    else:
        form = CodeForm(require_consents=is_new)
    return render(
        request,
        "accounts/code_form.html",
        {
            "form": form,
            "phone": phone,
            "is_new": is_new,
            "next": next_url,
            "demo_otp_code": settings.DEMO_OTP_CODE,
        },
    )


def register_view(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), reverse("accounts:login"))
    if request.user.has_full_name:
        return redirect("core:home")  # Task 5: cabinet:home
    next_url = _safe_next(request)
    if request.method == "POST":
        form = FullNameForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect(next_url or "core:home")  # Task 5: cabinet:home
    else:
        form = FullNameForm(instance=request.user)
    return render(request, "accounts/register.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:home")


@require_POST
def logout_all_view(request):
    user = request.user
    if user.is_authenticated:
        user.session_epoch += 1
        user.save(update_fields=["session_epoch"])
        logout(request)
    return redirect("core:home")
