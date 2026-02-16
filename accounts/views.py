from django.contrib.auth import login
from .forms import ProfileForm, SignUpForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

@login_required
def profile(request):
    return render(request, "accounts/profile.html")

@login_required
def personal_data(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Данные сохранены")
            return redirect("accounts:personal")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/personal.html", {"form": form})

def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.phone = form.cleaned_data.get("phone","")
            user.save()
            login(request, user)
            return redirect("core:home")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})
