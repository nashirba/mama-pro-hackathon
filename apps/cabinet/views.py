from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ChildForm, ProfileForm
from .models import Child


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
