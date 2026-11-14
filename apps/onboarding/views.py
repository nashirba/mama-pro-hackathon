from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import services
from .forms import ApplicationForm, CourseForm, DocumentForm
from .models import Application, ApplicationCourse, ApplicationDocument


def _own_application(request) -> Application:
    application = Application.objects.filter(user=request.user).first()
    if application is None:
        raise Http404
    return application


def status_page(request, application: Application, *, document_form=None, course_form=None, errors=None):
    """The cabinet of a specialist or a nanny: the application, its status, documents and courses."""
    return render(
        request,
        "onboarding/status.html",
        {
            "application": application,
            "missing": services.missing_for_submit(application) if application.is_editable else [],
            "document_form": document_form or DocumentForm(),
            "course_form": course_form or CourseForm(),
            "submit_errors": errors or [],
        },
    )


@login_required
def edit(request):
    application = _own_application(request)
    if not application.is_editable:
        return redirect("cabinet:home")
    form = ApplicationForm(request.POST or None, instance=application)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Анкета сохранена"))
        return redirect("cabinet:home")
    return render(request, "onboarding/form.html", {"form": form, "application": application})


@login_required
@require_POST
def submit(request):
    application = _own_application(request)
    try:
        services.submit(application)
    except ValidationError as exc:
        return status_page(request, application, errors=exc.messages)
    return redirect("cabinet:home")


@login_required
@require_POST
def document_add(request):
    application = _own_application(request)
    if not application.is_editable:
        return redirect("cabinet:home")
    form = DocumentForm(request.POST, request.FILES)
    if form.is_valid():
        form.save(application)
        return redirect("cabinet:home")
    return status_page(request, application, document_form=form)


@login_required
@require_POST
def document_delete(request, pk):
    application = _own_application(request)
    if application.is_editable:
        get_object_or_404(ApplicationDocument, pk=pk, application=application).delete()
    return redirect("cabinet:home")


@login_required
def document_file(request, pk):
    """The owner and staff only: documents are personal data and never get a public URL."""
    document = get_object_or_404(ApplicationDocument.objects.select_related("application"), pk=pk)
    if not (request.user.is_staff or document.application.user_id == request.user.pk):
        raise Http404
    response = HttpResponse(bytes(document.data), content_type=document.content_type)
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def course_add(request):
    application = _own_application(request)
    if not (application.is_editable and application.is_nanny):
        return redirect("cabinet:home")
    form = CourseForm(request.POST)
    if form.is_valid():
        course = form.save(commit=False)
        course.application = application
        course.save()
        return redirect("cabinet:home")
    return status_page(request, application, course_form=form)


@login_required
@require_POST
def course_delete(request, pk):
    application = _own_application(request)
    if application.is_editable:
        get_object_or_404(ApplicationCourse, pk=pk, application=application).delete()
    return redirect("cabinet:home")
