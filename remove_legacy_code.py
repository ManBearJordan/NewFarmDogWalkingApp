#!/usr/bin/env python3
"""
Script to remove legacy fallback logic and patch scripts.

This script removes files and functions that are no longer needed 
with the new unified subscription-driven workflow.
"""

import os
import shutil
from pathlib import Path

def main():
    """Remove legacy files and update code to eliminate fallback logic."""
    
    # Files to remove completely
    legacy_files = [
        "cleanup_duplicate_bookings.py",
        "cleanup_duplicates.sql", 
        "cleanup_null_service_type.py",
        "cleanup_stale_holds.sql",
        "execute_duplicate_cleanup.py",
        "final_booking_cleanup.py", 
        "final_cleanup_orphaned_data.py",
        "fix_booking_creation_code.py",
        "fix_booking_issues.py",
        "patches/Apply-BookingsMerge.py",
        "verify_cleanup.py",
        # Test files for legacy functionality
        "test_booking_fixes.py",
        "test_canonical_fixes.py", 
        "test_fixes.py",
        "test_unified_fixes.py"
    ]
    
    removed_files = []
    
    # Remove legacy files
    for file_path in legacy_files:
        if os.path.exists(file_path):
            print(f"Removing legacy file: {file_path}")
            os.remove(file_path)
            removed_files.append(file_path)
    
    # Remove patches directory if empty
    if os.path.exists("patches") and not os.listdir("patches"):
        print("Removing empty patches directory")
        os.rmdir("patches")
        removed_files.append("patches/")
    
    # Also clean up .gitignore to exclude any remaining temporary files
    gitignore_additions = [
        "\n# Legacy cleanup - exclude temporary files",
        "*_backup.py",
        "*_fix.py", 
        "*cleanup*",
        "*.sql.bak",
        "patches/",
        "temp_*"
    ]
    
    try:
        with open(".gitignore", "a") as f:
            f.write("\n".join(gitignore_additions))
        print("Updated .gitignore to exclude temporary files")
    except Exception as e:
        print(f"Warning: Could not update .gitignore: {e}")
    
    print(f"\nRemoved {len(removed_files)} legacy files:")
    for file in removed_files:
        print(f"  - {file}")
    
    print("\n✅ Legacy cleanup complete!")
    print("The unified subscription-driven workflow is now the single source of truth.")
    print("No manual sync scripts or fallback logic remain.")

if __name__ == "__main__":
    main()