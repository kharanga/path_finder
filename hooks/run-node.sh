#!/bin/sh
# Runs a Node script with the first node found: $CC_DASHBOARD_NODE, PATH, newest nvm install, Homebrew, /usr/local; exits 0 silently when none exists so a hook never fails a turn.

script="$1"
shift

pick_node() {
  if [ -n "$CC_DASHBOARD_NODE" ] && [ -x "$CC_DASHBOARD_NODE" ]; then
    printf '%s\n' "$CC_DASHBOARD_NODE"
    return
  fi
  if command -v node >/dev/null 2>&1; then
    command -v node
    return
  fi
  newest=""
  for candidate in "$HOME"/.nvm/versions/node/*/bin/node; do
    [ -x "$candidate" ] && newest="$candidate"
  done
  if [ -n "$newest" ]; then
    printf '%s\n' "$newest"
    return
  fi
  for candidate in /opt/homebrew/bin/node /usr/local/bin/node /usr/bin/node; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
}

node_bin="$(pick_node)"
[ -z "$node_bin" ] && exit 0
exec "$node_bin" "$script" "$@"
