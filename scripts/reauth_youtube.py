"""
One-time re-consent for the channel token, adding:
  * yt-analytics.readonly -- watch time and retention per video, which the
    daily tuner (tuner.py) uses to lean the mix toward what works
  * youtube.force-ssl     -- lets the pipeline post the channel's own
    first comment under each upload

Run locally (opens the browser; sign in as the CHANNEL account and approve):
    python scripts/reauth_youtube.py
Then store the new token as the YOUTUBE_TOKEN_JSON repo secret, e.g.
    gh secret set YOUTUBE_TOKEN_JSON -R hashiraarchives/photo-reels < youtube_token.json
The token's contents are never printed.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402
import youtube_uploader as yu  # noqa: E402

SECRET = os.path.join(HERE, 'client_secret.json')
TOKEN = os.path.join(HERE, 'youtube_token.json')


def main():
    if not os.path.exists(SECRET):
        sys.exit(f"client_secret.json not found in {HERE}")
    flow = InstalledAppFlow.from_client_secrets_file(SECRET, yu.REAUTH_SCOPES)
    creds = flow.run_local_server(port=0, prompt='consent', access_type='offline',
                                  authorization_prompt_message='Approve in the browser window that opened.',
                                  success_message='Done -- you can close this tab and return to Claude.')
    with open(TOKEN, 'w', encoding='utf-8') as f:
        f.write(creds.to_json())
    granted = sorted(creds.scopes or [])
    print("Saved token. Granted scopes:")
    for s in granted:
        print("  ", s)
    missing = [s for s in yu.REAUTH_SCOPES if s not in granted]
    print("MISSING:", missing if missing else "none")


if __name__ == '__main__':
    main()
