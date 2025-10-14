# epts_backend/views.py
from django.shortcuts import render

def home(request):
    """
    Renders the home page for the EPTS backend.
    This page acts as a simple landing UI to confirm deployment.
    """
    return render(request, "home.html")
