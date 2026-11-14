from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from apps.catalog.models import SpecialistType

from .questions import INTRO, RECOMMENDED_TYPE_SLUGS, SCALE, SECTIONS
from .scoring import from_session, score_answers, to_session, top_sections

SESSION_KEY = "questionnaire_scores"


@require_http_methods(["GET", "POST"])
def questionnaire(request):
    if request.method == "POST":
        request.session[SESSION_KEY] = to_session(score_answers(request.POST))
        request.session.set_expiry(0)
        return redirect("questionnaire:result")
    return render(request, "questionnaire/form.html", {"sections": SECTIONS, "scale": SCALE, "intro": INTRO})


@require_safe
def result(request):
    scores = from_session(request.session.get(SESSION_KEY))
    answered_any = bool(scores) and any(s.answered for s in scores)
    types = []
    if answered_any:
        types = sorted(
            SpecialistType.objects.filter(slug__in=RECOMMENDED_TYPE_SLUGS).prefetch_related("translations"),
            key=lambda t: RECOMMENDED_TYPE_SLUGS.index(t.slug),
        )
    context = {
        "scores": scores,
        "top": top_sections(scores) if scores else [],
        "answered_any": answered_any,
        "types": types,
    }
    return render(request, "questionnaire/result.html", context)
