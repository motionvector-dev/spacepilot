#!/usr/bin/env bash
# Build SpaceBar.app — the only supported way to run it.
#
# A bare SwiftPM executable has no Info.plist, so macOS SIGABRTs it the first
# time it reads a speech or microphone status ("attempted to access
# privacy-sensitive data without a usage description"). That is not something
# the app can catch or work around; it has to be a bundle. This assembles one.
#
#   native/SpaceBar/tools/make_app.sh
#
# Prints the `open` command when it is done.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
BUILD="$ROOT/.build"
APP="$BUILD/SpaceBar.app"
PLIST="$ROOT/Info.plist"
ENTITLEMENTS="$ROOT/SpaceBar.entitlements"

cd "$ROOT"

# ---------------------------------------------------------------- 1. build
echo "==> swift build -c release"
swift build -c release
BINARY="$(swift build -c release --show-bin-path)/SpaceBar"
[ -x "$BINARY" ] || { echo "no binary at $BINARY" >&2; exit 1; }

# ------------------------------------------- 2. the Swift 6 isolation gate
#
# Ten SIGTRAP reports on 2026-08-28 were one bug: a @MainActor-inferred
# completion handler invoked on TCC's XPC queue, trapping in
# swift_task_isCurrentExecutor before its first line ran. The callbacks now
# live in `nonisolated` methods so no check is emitted. This is what stops
# that regressing — it fails against the code as it was.
echo "==> checking voice callbacks carry no main-actor executor check"
OFFENDERS="$(
  otool -tV "$BINARY" 2>/dev/null \
    | awk '/^_\$s8SpaceBar/ { sym = $0 } /isCurrentExecutor/ { print sym }' \
    | sort -u \
    | while read -r sym; do xcrun swift-demangle <<<"$sym"; done \
    | grep -Ei 'installTap|startRecognition|startListening|setupAudioGraph|AVAudioPCMBuffer|SFSpeechRecogni' \
    || true
)"
if [ -n "$OFFENDERS" ]; then
  echo "FAIL: a voice callback is main-actor-isolated and will SIGTRAP off-main:" >&2
  echo "$OFFENDERS" >&2
  echo "Move the closure into a nonisolated method — see Sources/VoicePermissions.swift" >&2
  exit 1
fi
echo "    clean"

# ---------------------------------------------------- 3. verify the plist
echo "==> checking Info.plist"
for key in \
  CFBundleIdentifier \
  CFBundleName \
  CFBundlePackageType \
  LSUIElement \
  NSSpeechRecognitionUsageDescription \
  NSMicrophoneUsageDescription
do
  /usr/libexec/PlistBuddy -c "Print :$key" "$PLIST" >/dev/null 2>&1 \
    || { echo "FAIL: $PLIST has no $key" >&2; exit 1; }
done
for key in NSSpeechRecognitionUsageDescription NSMicrophoneUsageDescription; do
  value="$(/usr/libexec/PlistBuddy -c "Print :$key" "$PLIST")"
  [ -n "$value" ] || { echo "FAIL: $key is empty" >&2; exit 1; }
  echo "    $key: ${value:0:60}..."
done

# -------------------------------------------------------- 4. assemble it
echo "==> assembling $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BINARY" "$APP/Contents/MacOS/SpaceBar"
cp "$PLIST" "$APP/Contents/Info.plist"

# CFBundleExecutable is not in the checked-in plist because it names the built
# product, not the design. Added here so Launch Services can find the binary.
/usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string SpaceBar" \
  "$APP/Contents/Info.plist" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleExecutable SpaceBar" "$APP/Contents/Info.plist"

# SwiftPM emits resource bundles next to the binary. Copy any that exist.
BIN_DIR="$(dirname "$BINARY")"
shopt -s nullglob
for bundle in "$BIN_DIR"/*.bundle; do
  cp -R "$bundle" "$APP/Contents/Resources/"
  echo "    resource: $(basename "$bundle")"
done
shopt -u nullglob

# --------------------------------------------------------------- 5. sign
echo "==> ad-hoc codesign with entitlements"
codesign --force --sign - --entitlements "$ENTITLEMENTS" --deep "$APP"
codesign --verify --verbose=1 "$APP" 2>&1 | sed 's/^/    /'

# ---------------------------------------- 6. prove the bundle is readable
BUILT_SPEECH="$(/usr/libexec/PlistBuddy -c "Print :NSSpeechRecognitionUsageDescription" "$APP/Contents/Info.plist")"
BUILT_MIC="$(/usr/libexec/PlistBuddy -c "Print :NSMicrophoneUsageDescription" "$APP/Contents/Info.plist")"
[ -n "$BUILT_SPEECH" ] && [ -n "$BUILT_MIC" ] \
  || { echo "FAIL: usage strings did not survive assembly" >&2; exit 1; }

echo
echo "Built $APP"
echo
echo "Run it:"
echo
echo "  open \"$APP\""
echo
echo "SpaceBar is a menu bar app (LSUIElement), so it has no Dock icon and no"
echo "window — look for the ship glyph in the menu bar. The first press of Talk"
echo "is when macOS asks for Speech Recognition and then Microphone."
