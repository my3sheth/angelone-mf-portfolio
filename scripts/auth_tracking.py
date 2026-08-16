#!/usr/bin/env python
"""
Auth Tracking Utility - View and manage authentication details per account.

Usage:
    python scripts/auth_tracking.py list              # List all accounts with auth details
    python scripts/auth_tracking.py view <account>    # View auth details for specific account
    python scripts/auth_tracking.py delete <account>  # Delete auth details for account
    python scripts/auth_tracking.py export            # Export all auth details
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from angelone.auth_store import (
    list_all_auth_details,
    load_auth_details,
    delete_auth_details,
    DB_PATH,
)


def format_timestamp(ts):
    """Format ISO timestamp for display."""
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return ts


def cmd_list():
    """List all accounts with authentication details."""
    auth_list = list_all_auth_details()
    
    if not auth_list:
        print("No authentication details found.")
        return
    
    print("\n" + "=" * 80)
    print("AUTHENTICATION TRACKING - All Accounts")
    print("=" * 80 + "\n")
    
    for i, auth in enumerate(auth_list, 1):
        print(f"[{i}] Account Name: {auth.get('account_name')}")
        print(f"    Inferred Name: {auth.get('inferred_name', 'N/A')}")
        print(f"    Saved At: {format_timestamp(auth.get('saved_at'))}")
        print(f"    Status: {auth.get('status', 'unknown')}")
        print(f"    File: {auth.get('file')}")
        print()
    
    print(f"Total: {len(auth_list)} account(s)\n")


def cmd_view(account_name):
    """View detailed auth information for a specific account."""
    if not account_name:
        print("Error: Account name required. Usage: python auth_tracking.py view <account>")
        return
    
    auth_details = load_auth_details(account_name)
    
    if not auth_details:
        print(f"Error: No auth details found for account '{account_name}'")
        return
    
    print("\n" + "=" * 80)
    print(f"AUTH DETAILS - {account_name}")
    print("=" * 80 + "\n")
    
    print(f"Account Name: {auth_details.get('account_name')}")
    print(f"Inferred Name: {auth_details.get('inferred_name', 'N/A')}")
    print(f"Saved At: {format_timestamp(auth_details.get('saved_at'))}")
    print(f"Status: {auth_details.get('status', 'unknown')}")
    print(f"API URL: {auth_details.get('url', 'N/A')}")
    
    headers = auth_details.get('headers', {})
    cookies = auth_details.get('cookies', [])
    
    print(f"\nHeaders ({len(headers)} total):")
    for key, value in sorted(headers.items()):
        if value:
            preview = str(value)[:60] + "..." if len(str(value)) > 60 else str(value)
            print(f"  {key}: {preview}")
    
    print(f"\nCookies ({len(cookies)} total):")
    for i, cookie in enumerate(cookies[:5], 1):
        print(f"  [{i}] {cookie.get('name')} (domain: {cookie.get('domain')})")
    if len(cookies) > 5:
        print(f"  ... and {len(cookies) - 5} more cookies")
    
    print("\n" + "=" * 80 + "\n")


def cmd_delete(account_name):
    """Delete auth details for a specific account."""
    if not account_name:
        print("Error: Account name required. Usage: python auth_tracking.py delete <account>")
        return
    
    auth_details = load_auth_details(account_name)
    if not auth_details:
        print(f"Error: No auth details found for account '{account_name}'")
        return
    
    confirm = input(f"Delete auth details for '{account_name}'? (yes/no): ").strip().lower()
    if confirm == "yes":
        delete_auth_details(account_name)
        print(f"[OK] Deleted auth details for '{account_name}'")
    else:
        print("Cancelled.")


def cmd_export():
    """Export all auth details to a JSON file."""
    auth_list = list_all_auth_details()
    
    if not auth_list:
        print("No authentication details to export.")
        return
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    export_file = Path(__file__).resolve().parents[1] / f"auth_export_{timestamp}.json"
    
    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "total_accounts": len(auth_list),
        "accounts": auth_list,
    }
    
    export_file.write_text(json.dumps(export_data, indent=2), encoding="utf-8")
    print(f"[OK] Exported auth details to: {export_file}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print(f"Auth database: {DB_PATH}\n")
        return
    
    command = sys.argv[1].lower()
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    if command == "list":
        cmd_list()
    elif command == "view":
        cmd_view(arg)
    elif command == "delete":
        cmd_delete(arg)
    elif command == "export":
        cmd_export()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
