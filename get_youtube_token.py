"""
ShortsFlow YouTube Token Generator Helper
Run this script locally to authenticate with Google and generate token.json or token_<account>.json.

Usage:
  python get_youtube_token.py           # Default (token.json, client_secrets.json)
  python get_youtube_token.py 2         # Account 2 (token_2.json, client_secrets_2.json)
  python get_youtube_token.py alt       # Account 'alt' (token_alt.json, client_secrets_alt.json)
"""
import os
import sys
import argparse

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def main():
    parser = argparse.ArgumentParser(description="YouTube Token Generator")
    parser.add_argument("account", nargs="?", default="", help="Optional account identifier/slot (e.g. 2, channel_b)")
    parser.add_argument("--account", dest="account_opt", default="", help="Account identifier")
    args = parser.parse_args()

    acc = (args.account_opt or args.account).strip()
    
    secrets_file = f"client_secrets_{acc}.json" if (acc and os.path.exists(f"client_secrets_{acc}.json")) else "client_secrets.json"
    token_file = f"token_{acc}.json" if acc else "token.json"

    if not os.path.exists(secrets_file):
        print(f"\n[Error] '{secrets_file}' is missing in the project root directory!\n")
        print("To get client secrets:")
        print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
        print("2. Create a project and enable 'YouTube Data API v3'.")
        print("3. Go to Credentials -> Create Credentials -> OAuth client ID.")
        print("4. Download the JSON file and place it in this folder as 'client_secrets.json'")
        if acc:
            print(f"   (or '{secrets_file}' for Account '{acc}').\n")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        print(f"[Log] Launching Google OAuth Browser Login (Account: {acc or 'default'}, Target: {token_file})...")
        flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
        creds = flow.run_local_server(port=0)
        
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
            
        print(f"\n[SUCCESS] '{token_file}' generated successfully!")
        print("\n[Next Steps]")
        if acc:
            print(f"1. Local Execution: Run with '--youtube_account {acc}' or set env YOUTUBE_ACCOUNT={acc}")
            print(f"2. GitHub Actions Setup: Copy contents of '{token_file}' to secret 'GOOGLE_YOUTUBE_TOKEN_{acc.upper()}'")
            print(f"   and '{secrets_file}' to secret 'GOOGLE_CLIENT_SECRETS_{acc.upper()}'.\n")
        else:
            print("1. Local Execution: Used automatically by main.py / gui_app.py.")
            print("2. GitHub Actions Setup: Copy contents of 'token.json' to secret 'GOOGLE_YOUTUBE_TOKEN'")
            print("   and 'client_secrets.json' to secret 'GOOGLE_CLIENT_SECRETS'.\n")

    except Exception as e:
        print(f"\n[Error] Authentication failed: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
