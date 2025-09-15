#!/usr/bin/env python3
"""
Minimal test script to isolate the app startup issue
"""

print("Starting minimal test...")

try:
    print("1. Testing basic imports...")
    import sys
    import os
    print("   - sys, os: OK")
    
    print("2. Testing PySide6 imports...")
    from PySide6.QtWidgets import QApplication
    print("   - QApplication: OK")
    
    print("3. Testing database imports...")
    from db import init_db, get_conn
    print("   - db imports: OK")
    
    print("4. Testing database initialization...")
    init_db()
    print("   - init_db(): OK")
    
    print("5. Testing database connection...")
    conn = get_conn()
    print("   - get_conn(): OK")
    
    print("6. Testing credit functions...")
    from db import get_client_credit, add_client_credit, use_client_credit
    print("   - credit functions: OK")
    
    print("7. Testing stripe imports...")
    from stripe_integration import list_booking_services
    print("   - stripe imports: OK")
    
    print("8. Testing QApplication creation...")
    app = QApplication(sys.argv)
    print("   - QApplication created: OK")
    
    print("9. Testing basic widget creation...")
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
    widget = QWidget()
    layout = QVBoxLayout(widget)
    label = QLabel("Test")
    layout.addWidget(label)
    print("   - Basic widgets: OK")
    
    print("\nAll basic tests passed! The issue might be in a specific component.")
    print("Now testing individual tab components...")
    
    print("10. Testing ClientsTab...")
    # Import the main app to test ClientsTab
    from app import ClientsTab
    clients_tab = ClientsTab()
    print("   - ClientsTab: OK")
    
    print("11. Testing BookingsTab...")
    from app import BookingsTab
    bookings_tab = BookingsTab()
    print("   - BookingsTab: OK")
    
    print("\nAll tests completed successfully!")
    
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    
print("Test completed.")
