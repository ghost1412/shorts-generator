"""Upload finished videos to a Google Drive folder.

    python -m engine.drive_upload recap_portrait.mp4 recap_landscape.mp4 --folder https://drive.google.com/drive/folders/<id>
    python main.py --mode TRIP ... --upload_drive https://drive.google.com/drive/folders/<id>

Set-up (once): create an OAuth client of type "Desktop app" in Google Cloud Console (APIs & Services -> enable "Google Drive API"),
download it as `client_secrets_drive.json` into the project folder (or point DRIVE_SECRETS_FILE at it). The first upload opens the
browser to sign in; the permission is saved in `token_drive.json` (both files are git-ignored). The scope is full Drive access
because Google only lets the narrower `drive.file` scope write into folders the app itself created, not into your own folder.
Nothing is uploaded unless you ask for it, and only the files you name are sent.
"""
import argparse
import mimetypes
import os
import re
import sys

SCOPES = ["https://www.googleapis.com/auth/drive"]


def folder_id(link_or_id):
    """The folder id from a Drive folder link (…/folders/<id>?usp=sharing, …?id=<id>) or the bare id; '' when there is none."""
    text = str(link_or_id or "").strip()
    m = re.search(r"/folders/([A-Za-z0-9_-]{10,})", text) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", text)
    if m:
        return m.group(1)
    return text if re.fullmatch(r"[A-Za-z0-9_-]{10,}", text) else ""


def files_to_send(paths):
    """The existing files among `paths` (folders are not walked), in the given order, without repeats."""
    seen, out = set(), []
    for p in paths or []:
        ap = os.path.abspath(p)
        if os.path.isfile(ap) and ap not in seen:
            seen.add(ap)
            out.append(ap)
    return out


def credentials(secrets_file=None, token_file=None):
    """Drive credentials from the saved token, refreshed or created with a browser sign-in when needed. None when they cannot be had."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    secrets_file = secrets_file or os.getenv("DRIVE_SECRETS_FILE") or "client_secrets_drive.json"
    token_file = token_file or os.getenv("DRIVE_TOKEN_FILE") or "token_drive.json"
    creds = None
    if os.path.isfile(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception as e:
            print(f"[Warning] Could not read {token_file}: {e}")
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            return creds
        except Exception as e:
            print(f"[Warning] The saved Drive permission could not be refreshed ({str(e)[:80]}); signing in again.")
    if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
        print("[Error] Google Drive sign-in needs a browser; it cannot run in CI. Create token_drive.json on your PC first.")
        return None
    if not os.path.isfile(secrets_file):
        print(f"[Error] Google Drive upload needs an OAuth client file ('{secrets_file}'). See the set-up steps at the top of engine/drive_upload.py.")
        return None
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        creds = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES).run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return creds
    except Exception as e:
        print(f"[Error] Google Drive sign-in failed: {str(e)[:120]}")
        return None


def upload(paths, folder, service=None, creds=None):
    """Upload `paths` into the Drive folder (link or id). Returns [{"name", "id", "link"}] for the files that went up; each failure
    is reported and does not stop the others."""
    fid = folder_id(folder)
    if not fid:
        print("[Error] That is not a Google Drive folder link or id (expected https://drive.google.com/drive/folders/<id>).")
        return []
    files = files_to_send(paths)
    if not files:
        print("[Warning] Nothing to upload: no such file(s).")
        return []
    if service is None:
        creds = creds or credentials()
        if not creds:
            return []
        from googleapiclient.discovery import build
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
    from googleapiclient.http import MediaFileUpload
    done = []
    for path in files:
        name = os.path.basename(path)
        try:
            media = MediaFileUpload(path, mimetype=mimetypes.guess_type(path)[0] or "application/octet-stream", resumable=True, chunksize=8 * 1024 * 1024)
            req = service.files().create(body={"name": name, "parents": [fid]}, media_body=media, fields="id,webViewLink", supportsAllDrives=True)
            resp = None
            while resp is None:
                status, resp = req.next_chunk()
                if status:
                    print(f"[Log] Drive: {name} {int(status.progress() * 100)}%")
            done.append({"name": name, "id": resp.get("id", ""), "link": resp.get("webViewLink", "")})
            print(f"[Success] Uploaded to Google Drive: {name} {resp.get('webViewLink', '')}")
        except Exception as e:
            print(f"[Error] Could not upload {name} to Google Drive: {str(e)[:160]}")
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description="Upload files to a Google Drive folder.")
    ap.add_argument("files", nargs="+", help="video (or any) files to upload")
    ap.add_argument("--folder", required=True, help="Drive folder link or id")
    a = ap.parse_args(argv)
    return 0 if len(upload(a.files, a.folder)) == len(files_to_send(a.files)) else 1


if __name__ == "__main__":
    sys.exit(main())
