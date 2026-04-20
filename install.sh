#!/usr/bin/env bash
# trimmix installer for Ubuntu 22.04+
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/qazi0/trimmix/main/install.sh | bash
#
# Environment overrides:
#   TRIMMIX_REPO  : git URL to clone from (default: GitHub qazi0/trimmix)
#   TRIMMIX_REF   : branch or tag to install (default: main)
set -euo pipefail

REPO="${TRIMMIX_REPO:-https://github.com/qazi0/trimmix.git}"
REF="${TRIMMIX_REF:-main}"
DIR="$HOME/.local/share/trimmix"
BIN="$HOME/.local/bin/trimmix"

say() { printf '==> %s\n' "$*"; }

say "Installing apt dependencies (requires sudo)"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git \
    python3 \
    python3-venv \
    wl-clipboard \
    ydotool \
    ydotoold

say "Fetching trimmix into $DIR"
mkdir -p "$(dirname "$DIR")" "$HOME/.local/bin"
if [ -d "$DIR/.git" ]; then
    git -C "$DIR" fetch --quiet origin
    git -C "$DIR" reset --quiet --hard "origin/$REF"
else
    git clone --quiet --depth 1 --branch "$REF" "$REPO" "$DIR"
fi

say "Creating virtualenv"
rm -rf "$DIR/.venv"
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --quiet --upgrade pip
"$DIR/.venv/bin/pip" install --quiet "$DIR"
ln -sf "$DIR/.venv/bin/trimmix" "$BIN"

say "Enabling ydotoold user service"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/ydotoold.service" <<'EOF'
[Unit]
Description=ydotool daemon

[Service]
ExecStart=/usr/bin/ydotoold
Restart=on-failure

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now ydotoold

# /dev/uinput access: ACL should already grant it via the GNOME session on
# modern Ubuntu; if not, fall back to the input group.
if ! getfacl /dev/uinput 2>/dev/null | grep -q "user:$USER:rw"; then
    say "WARNING: $USER lacks /dev/uinput ACL. If autopaste fails:"
    say "  sudo usermod -aG input $USER    # then log out and back in"
fi

if ! printf ':%s:' "$PATH" | grep -q ":$HOME/.local/bin:"; then
    say "WARNING: $HOME/.local/bin is not in PATH. Add to ~/.bashrc or ~/.zshrc:"
    say "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

"$BIN" --version

cat <<EOF

Installed at $BIN

Add GNOME keyboard shortcuts (Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts):
  $BIN --paste --terminal --quiet   # pastes into terminals
  $BIN --paste --quiet              # pastes into editors, browsers, Slack, etc.
EOF
