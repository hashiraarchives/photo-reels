#!/bin/sh
# Re-pack the private media bundle after adding/changing music or thumbnail
# bases. The key lives outside the repo (ASSETS_KEY secret on GitHub).
#   ASSETS_KEY_FILE=~/.aap_assets_key sh scripts/pack_assets.sh
set -e
tar czf /tmp/private_assets.tar.gz assets/*.mp3 "assets/channel logo.png" \
    assets/intro.mp4 assets/intro_voice assets/thumbnail_bases
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
    -pass file:"${ASSETS_KEY_FILE:?set ASSETS_KEY_FILE}" \
    -in /tmp/private_assets.tar.gz -out assets/bundle.enc
rm -f /tmp/private_assets.tar.gz
echo "assets/bundle.enc updated"
