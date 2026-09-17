#!/bin/sh
set -e

ZIP="https://github.com/Cillian-Cooke/hexshift/archive/refs/heads/main.zip"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/hexshift"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Hexshift needs Python 3.10+." >&2
  echo "Install it from https://www.python.org/downloads/ then run this again." >&2
  exit 1
fi

ver="$("$PY" -c 'import sys; print("%d.%d" % (sys.version_info.major, sys.version_info.minor))')"
major="${ver%%.*}"
minor="${ver#*.}"
if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 10 ]; }; then
  echo "Hexshift needs Python 3.10 or newer (found $("$PY" -V))." >&2
  exit 1
fi

echo "Installing Hexshift into $DEST ..."
mkdir -p "$DEST"
if ! "$PY" -m venv "$DEST/venv" 2>/dev/null; then
  echo "Could not create a virtual environment." >&2
  echo "On Debian/Ubuntu/Mint: sudo apt install python3-venv python3-pip" >&2
  echo "Then run this command again." >&2
  exit 1
fi

PIP="$DEST/venv/bin/pip"
PYTHON="$DEST/venv/bin/python"
"$PIP" install --upgrade pip >/dev/null
"$PIP" install --upgrade "$ZIP"

mkdir -p "$HOME/.local/bin"
ln -sf "$DEST/venv/bin/hexshift" "$HOME/.local/bin/hexshift"

if [ "$(uname -s)" = "Linux" ]; then
  apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  mkdir -p "$apps"
  icon="$("$PYTHON" -c 'import hexshift, os; print(os.path.join(os.path.dirname(hexshift.__file__), "icons", "tray.svg"))')"
  cat > "$apps/hexshift.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Hexshift
Comment=Hexagonal territory game
Exec=$PYTHON -m hexshift
Icon=$icon
Terminal=false
Categories=Game;
StartupNotify=false
EOF
fi

echo
echo "Hexshift is installed. Launching..."
echo "Later you can run:  hexshift    or    $PYTHON -m hexshift"
exec "$PYTHON" -m hexshift "$@"
