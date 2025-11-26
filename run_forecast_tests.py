#!/usr/bin/env python
"""
Forecast Testing Script - Runs all Sales_forecast tests and displays results
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    os.environ['DJANGO_SETTINGS_MODULE'] = 'POSwithSalesForecast.settings'
    django.setup()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    
    print("=" * 70)
    print("SALES FORECAST TEST SUITE")
    print("=" * 70)
    print()
    
    failures = test_runner.run_tests(["Sales_forecast.tests"])
    
    print()
    print("=" * 70)
    if failures:
        print(f"RESULT: {failures} TEST(S) FAILED")
        sys.exit(1)
    else:
        print("RESULT: ALL TESTS PASSED ✓")
        sys.exit(0)
