from django import forms 

class Helloform(forms.Form):
    name = forms.CharField(max_length=100, required=True, label='Your Name')
    message = forms.CharField(widget=forms.Textarea, required=False, label='Your Message')