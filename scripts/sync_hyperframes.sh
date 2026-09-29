#!/usr/bin/env bash
# Обновить вендоренные навыки HyperFrames до нужного коммита (по умолчанию main).
# Тянет только то, что перечислено в vendor/hyperframes/NOTICE.nd-video-studio.
set -euo pipefail
SHA="${1:-main}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy -u ALL_PROXY \
  gh api "repos/heygen-com/hyperframes/tarball/$SHA" > "$TMP/hf.tgz"
TOP="$(tar -tzf "$TMP/hf.tgz" | head -1 | cut -d/ -f1)"
mkdir -p "$TMP/x"
tar -xzf "$TMP/hf.tgz" -C "$TMP/x" --strip-components=1 \
  "$TOP/LICENSE" "$TOP/skills/hyperframes" "$TOP/skills/hyperframes-core" \
  "$TOP/skills/hyperframes-animation" "$TOP/skills/hyperframes-cli" \
  "$TOP/skills/hyperframes-keyframes" "$TOP/docs/concepts/determinism.mdx"
DEST="$ROOT/vendor/hyperframes"
cp "$DEST/NOTICE.nd-video-studio" "$TMP/x/"
rsync -a --delete "$TMP/x/" "$DEST/"
NEW="${TOP##*-}"
sed -i '' -E "s/на коммите [0-9a-f]+/на коммите $NEW/" "$DEST/NOTICE.nd-video-studio"
echo "vendor/hyperframes → $NEW"
