from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name","last_name","phone","birth_date","club","club_card"]
        widgets = {"birth_date": forms.DateInput(attrs={"type":"date"})}

class SignUpForm(UserCreationForm):
    phone = forms.CharField(label="Телефон", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "phone", "password1", "password2")
