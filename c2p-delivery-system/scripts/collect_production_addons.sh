#!/usr/bin/env bash
# Copy Odoo modules that exist only on this server into the repo's addons/,
# so production code stops living outside version control.
#
# Read-only with respect to Odoo and PostgreSQL: it copies files and nothing
# else. It does not commit — review the diff first, then commit yourself.
#
#   bash scripts/collect_production_addons.sh c2p_appointment c2p_master_agent c2p_proposal
#
# With no module names it collects every module on the addons path that the
# repo does not already carry.

set -euo pipefail

ODOO_CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="$REPO_ROOT/addons"

[[ -d "$DEST" ]] || { echo "No addons/ directory at $DEST" >&2; exit 1; }

# Build the search path from odoo.conf, falling back to the usual locations.
declare -a SEARCH=()
if [[ -r "$ODOO_CONF" ]]; then
  line="$(grep -E '^[[:space:]]*addons_path[[:space:]]*=' "$ODOO_CONF" | tail -1 || true)"
  if [[ -n "$line" ]]; then
    IFS=',' read -ra parts <<< "${line#*=}"
    for p in "${parts[@]}"; do
      p="$(echo "$p" | xargs)"           # trim
      [[ -d "$p" ]] && SEARCH+=("$p")
    done
  fi
fi
for p in /opt/odoo/addons /opt/odoo/custom-addons /mnt/extra-addons \
         /usr/lib/python3/dist-packages/odoo/addons; do
  [[ -d "$p" ]] && SEARCH+=("$p")
done
((${#SEARCH[@]})) || { echo "No addons path found (set ODOO_CONF)" >&2; exit 1; }

echo "Addons path:"
printf '  %s\n' "${SEARCH[@]}"
echo "Destination: $DEST"
echo

# A directory is a module when it has a manifest.
is_module() { [[ -f "$1/__manifest__.py" ]]; }

declare -a WANTED=("$@")
if ((${#WANTED[@]} == 0)); then
  for dir in "${SEARCH[@]}"; do
    for mod in "$dir"/*; do
      name="$(basename "$mod")"
      is_module "$mod" || continue
      [[ -d "$DEST/$name" ]] && continue
      WANTED+=("$name")
    done
  done
  # The stock Odoo addons are not ours to vendor; only take local-looking ones.
  filtered=()
  for name in "${WANTED[@]}"; do
    case "$name" in c2p_*|mumtaz_*|zaki_*) filtered+=("$name") ;; esac
  done
  WANTED=("${filtered[@]}")
fi

((${#WANTED[@]})) || { echo "Nothing to collect."; exit 0; }

copied=0 skipped=0 missing=0
for name in "${WANTED[@]}"; do
  src=""
  for dir in "${SEARCH[@]}"; do
    if is_module "$dir/$name"; then src="$dir/$name"; break; fi
  done
  if [[ -z "$src" ]]; then
    printf '%-22s NOT FOUND on the addons path\n' "$name"
    missing=$((missing+1)); continue
  fi
  if [[ -e "$DEST/$name" && "${FORCE:-0}" != "1" ]]; then
    # On disk is not the same as in git: a module can sit in the working tree
    # untracked or ignored, which is the state this script exists to find.
    if git -C "$REPO_ROOT" ls-files --error-unmatch "addons/$name" >/dev/null 2>&1; then
      state="tracked in git"
    elif git -C "$REPO_ROOT" check-ignore -q "addons/$name" 2>/dev/null; then
      state="ON DISK BUT GITIGNORED"
    else
      state="ON DISK BUT UNTRACKED"
    fi
    printf '%-22s %s — skipped (FORCE=1 to re-copy)\n' "$name" "$state"
    skipped=$((skipped+1)); continue
  fi
  rm -rf "$DEST/$name"
  # Copy source only, then strip caches and compiled files. cp is used rather
  # than rsync because rsync is not installed on every Odoo host.
  cp -a "$src" "$DEST/$name"
  find "$DEST/$name" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$DEST/$name" \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
  rm -rf "$DEST/$name/.git"
  printf '%-22s copied from %s\n' "$name" "$src"
  copied=$((copied+1))
done

echo
echo "Copied $copied, skipped $skipped, missing $missing."
echo "Review with:  git -C '$REPO_ROOT' status --short addons/"
echo "Nothing has been committed."
