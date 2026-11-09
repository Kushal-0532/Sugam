#!/usr/bin/env bash
# Build android/glow into android/glow/build/glow.apk with plain SDK tools (no Gradle).
set -euo pipefail
SDK=${ANDROID_HOME:-$HOME/Android}; BT=$SDK/build-tools/34.0.0; JAR=$SDK/platforms/android-34/android.jar
cd "$(dirname "$0")/../android/glow"; rm -rf build; mkdir -p build/classes
javac -g:none --release 8 -Xlint:-options -cp "$JAR" -d build/classes $(find src -name '*.java')
"$BT/d8" --lib "$JAR" --min-api 26 --output build $(find build/classes -name '*.class')
"$BT/aapt2" link -o build/base.apk --manifest AndroidManifest.xml -I "$JAR"
(cd build && zip -qj base.apk classes.dex)
"$BT/zipalign" -f 4 build/base.apk build/aligned.apk
[ -f debug.keystore ] || keytool -genkeypair -keystore debug.keystore -storepass android -keypass android \
  -alias k -keyalg RSA -keysize 2048 -validity 3650 -dname "CN=glow" >/dev/null 2>&1
"$BT/apksigner" sign --ks debug.keystore --ks-pass pass:android --out build/glow.apk build/aligned.apk
echo built android/glow/build/glow.apk
