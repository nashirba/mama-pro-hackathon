from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm


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
