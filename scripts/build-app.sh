#!/bin/bash
set -e

# Build the AI Humanizer as a macOS .app bundle.
# The .app is a thin wrapper that launches desktop.py via the project's venv.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="AI Humanizer"
APP_DIR="$ROOT/dist/${APP_NAME}.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo "Building ${APP_NAME}.app ..."

# ---- 1. Rebuild static frontend ----
echo "[1/4] Building frontend..."
cd "$ROOT/frontend"
npm run build --silent 2>/dev/null
rm -rf "$ROOT/backend/static"
cp -r out "$ROOT/backend/static"

# ---- 2. Create .app structure ----
echo "[2/4] Creating .app bundle..."
rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"

# Info.plist
cat > "$CONTENTS/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>AI Humanizer</string>
    <key>CFBundleDisplayName</key>
    <string>AI Humanizer</string>
    <key>CFBundleIdentifier</key>
    <string>com.aihumanizer.app</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ---- 3. Build app icon from SVG ----
echo "[3/5] Building app icon..."
SVG="$ROOT/assets/icon.svg"
if [ -f "$SVG" ]; then
    ICONSET="/tmp/AppIcon.iconset"
    rm -rf "$ICONSET"
    mkdir -p "$ICONSET"
    # Render SVG → PNG (uses cairosvg via the project venv)
    "$ROOT/backend/venv/bin/python" -c "
import cairosvg
cairosvg.svg2png(url='$SVG', write_to='/tmp/icon_1024.png', output_width=1024, output_height=1024)
" 2>/dev/null || qlmanage -t -s 1024 -o /tmp "$SVG" 2>/dev/null
    if [ -f /tmp/icon_1024.png ]; then
        for size in 16 32 64 128 256 512; do
            sips -z $size $size /tmp/icon_1024.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1
        done
        sips -z 1024 1024 /tmp/icon_1024.png --out "$ICONSET/icon_512x512@2x.png" >/dev/null 2>&1
        sips -z 512 512 /tmp/icon_1024.png --out "$ICONSET/icon_256x256@2x.png" >/dev/null 2>&1
        sips -z 256 256 /tmp/icon_1024.png --out "$ICONSET/icon_128x128@2x.png" >/dev/null 2>&1
        sips -z 64 64 /tmp/icon_1024.png --out "$ICONSET/icon_32x32@2x.png" >/dev/null 2>&1
        sips -z 32 32 /tmp/icon_1024.png --out "$ICONSET/icon_16x16@2x.png" >/dev/null 2>&1
        iconutil -c icns "$ICONSET" -o "$RESOURCES/AppIcon.icns"
        echo "  Icon built."
    else
        echo "  WARNING: Could not render SVG."
    fi
else
    echo "  No icon SVG found at $SVG, skipping."
fi

# ---- 4. Create launcher script ----
echo "[4/5] Creating launcher..."
cat > "$MACOS/launcher" << LAUNCHER
#!/bin/bash
# AI Humanizer launcher — runs inside the .app bundle
ROOT="$ROOT"
cd "\$ROOT/backend"
exec "\$ROOT/backend/venv/bin/python" desktop.py
LAUNCHER
chmod +x "$MACOS/launcher"

# ---- 5. Done ----
echo "[5/5] Done!"
echo ""
echo "App created at: $APP_DIR"
echo ""
echo "To run:  open \"$APP_DIR\""
echo "To move: drag it to /Applications"
