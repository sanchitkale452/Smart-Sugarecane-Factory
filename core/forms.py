from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User

class UserRegistrationForm(UserCreationForm):
    """Form for new user registration."""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already in use.')
        return email

class UserProfileForm(UserChangeForm):
    """Form for updating user profile."""
    password = None  # Remove password field from the form
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'address', 'profile_picture')
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email read-only after registration
        self.fields['email'].disabled = True
        self.fields['email'].help_text = 'Email cannot be changed after registration.'

class UserProfilePictureForm(forms.ModelForm):
    """Form for updating just the profile picture."""
    class Meta:
        model = User
        fields = ('profile_picture',)
