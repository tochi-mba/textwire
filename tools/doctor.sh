#!/bin/sh
# `make doctor`: what this machine has, what it is missing, and the command that fixes each gap.
# Safe to run any number of times; it changes nothing.
#
# Exit status 1 when something the server needs is missing. The Android tools only warn, because
# the server and the simulator work without them.

failed=0

row() {
    printf '  %-5s %-22s %s\n' "$1" "$2" "$3"
}

need() {
    # need <name> <command> <fix>
    if command -v "$2" >/dev/null 2>&1; then
        row ok "$1" "$(command -v "$2")"
    else
        row fail "$1" "$3"
        failed=1
    fi
}

want() {
    # want <name> <command> <fix>
    if command -v "$2" >/dev/null 2>&1; then
        row ok "$1" "$(command -v "$2")"
    else
        row warn "$1" "$3"
    fi
}

echo "Tools"
need git git "install Git (winget install Git.Git)"
need make make "install GNU Make (winget install ezwinports.make)"
need uv uv "install uv (winget install astral-sh.uv, or https://docs.astral.sh/uv/)"
want java java "install JDK 17 for the Android build (winget install EclipseAdoptium.Temurin.17.JDK)"
want adb adb "install Android platform-tools to put the app on a phone"

if command -v java >/dev/null 2>&1; then
    version=$(java -version 2>&1 | head -n 1)
    case "$version" in
        *\"17*|*\"2[0-9]*) row ok "jdk version" "$version" ;;
        *) row warn "jdk version" "$version; the Android build needs 17 or newer" ;;
    esac
fi

sdk="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"
if [ -n "$sdk" ] && [ -d "$sdk/platforms/android-36" ]; then
    row ok "android sdk" "$sdk (platform 36)"
elif [ -n "$sdk" ]; then
    row warn "android sdk" "$sdk has no platform 36: sdkmanager \"platforms;android-36\" \"build-tools;36.0.0\""
else
    row warn "android sdk" "set ANDROID_HOME to an SDK with platform 36 (see docs/ONBOARDING.md)"
fi

if command -v adb >/dev/null 2>&1; then
    devices=$(adb devices 2>/dev/null | awk 'NR > 1 && $2 == "device" { print $1 }' | tr '\n' ' ')
    if [ -n "$devices" ]; then
        row ok "phone" "$devices"
    else
        row warn "phone" "no device authorised over adb (only needed to install the app)"
    fi
fi

echo
echo "Server"
if command -v uv >/dev/null 2>&1; then
    (cd server && uv run --quiet python -m textwire doctor) || failed=1
else
    row fail "server" "install uv first"
    failed=1
fi

exit $failed
