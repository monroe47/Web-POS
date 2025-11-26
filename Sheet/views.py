from django.shortcuts import render


def sheet_view(request):
    return render(request, "Sheet/Spreadsheet.html")


def spreadsheet_dashboard(request):
    # Basic view for spreadsheet dashboard
    return render(request, "Sheet/Spreadsheet.html")
