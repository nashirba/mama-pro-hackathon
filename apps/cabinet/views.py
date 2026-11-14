from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.forms import CodeForm, PhoneForm
from apps.accounts.models import User
from apps.accounts.otp import OtpLocked, issue_code, verify_code

from .forms import ChildForm, ProfileForm
from .models import Child

SESSION_NEW_PHONE = "cabinet_new_phone"


@login_required
def home(request):
    return render(
        request, "cabinet/home.html", {"children": request.user.children.all()}
    )


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("cabinet:home")
    return render(request, "cabinet/profile_form.html", {"form": form})


@login_required
def child_add(request):
    form = ChildForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        child = form.save(commit=False)
        child.parent = request.user
        child.save()
        return redirect("cabinet:home")
    return render(request, "cabinet/child_form.html", {"form": form, "child": None})


@login_required
def child_edit(request, pk):
    child = get_object_or_404(Child, pk=pk, parent=request.user)
    form = ChildForm(request.POST or None, instance=child)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("cabinet:home")
    return render(request, "cabinet/child_form.html", {"form": form, "child": child})


@login_required
@require_POST
def child_delete(request, pk):
    get_object_or_404(Child, pk=pk, parent=request.user).delete()
    return redirect("cabinet:home")


@login_required
def phone_change(request):
    form = PhoneForm(request.POST or None)
    form.fields["phone"].label = _("Новый номер телефона")
    if request.method == "POST" and form.is_valid():
        new_phone = form.cleaned_data["phone"]
        if new_phone == request.user.phone:
            form.add_error("phone", _("Это ваш текущий номер"))
        elif User.objects.filter(phone=new_phone).exclude(pk=request.user.pk).exists():
            form.add_error("phone", _("Этот номер уже используется"))
        else:
            issue_code(new_phone)
            request.session[SESSION_NEW_PHONE] = new_phone
            return redirect("cabinet:phone_change_verify")
    return render(request, "cabinet/phone_form.html", {"form": form})


@login_required
def phone_change_verify(request):
    new_phone = request.session.get(SESSION_NEW_PHONE)
    if not new_phone:
        return redirect("cabinet:phone_change")
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            code_ok = verify_code(new_phone, form.cleaned_data["code"])
        except OtpLocked:
            form.add_error(
                "code", _("Слишком много неверных попыток. Запросите новый код.")
            )
        else:
            if code_ok:
                user = request.user
                old_phone = user.phone
                user.phone = new_phone
                try:
                    with transaction.atomic():
                        user.save(update_fields=["phone"])
                except IntegrityError:
                    user.phone = old_phone
                    request.session.pop(SESSION_NEW_PHONE, None)
                    form.add_error("code", _("Этот номер уже используется"))
                else:
                    request.session.pop(SESSION_NEW_PHONE, None)
                    messages.success(request, _("Номер телефона изменён"))
                    return redirect("cabinet:home")
            else:
                form.add_error("code", _("Неверный или просроченный код"))
    return render(
        request,
        "cabinet/phone_code.html",
        {
            "form": form,
            "phone": new_phone,
            "demo_otp_code": settings.DEMO_OTP_CODE,
        },
    )
