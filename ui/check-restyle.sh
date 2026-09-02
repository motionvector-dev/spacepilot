#!/usr/bin/env bash
# What is left to convert, and where. Run from the repo root.
#
# Counts are not the point — the point is that anything remaining should be
# something a person decided to keep, not something a sweep missed.
set -uo pipefail
cd "$(dirname "$0")/src" || exit 1

HUES='(emerald|cyan|purple|amber|rose|blue|violet|sky|indigo|red|green|orange|yellow|teal|fuchsia)-[0-9]{2,3}'
HEX='#[0-9a-fA-F]{6}'

printf '%-34s %7s %7s\n' AREA HUES HEX
printf '%-34s %7s %7s\n' '---' '----' '---'
total_h=0; total_x=0
for d in components/cockpit components/studio components/create components/oven components/docs pages hooks lib; do
  [ -d "$d" ] || continue
  h=$(grep -rhoE "$HUES" "$d" 2>/dev/null | wc -l | tr -d ' ')
  x=$(grep -rhoE "$HEX" "$d" 2>/dev/null | wc -l | tr -d ' ')
  total_h=$((total_h + h)); total_x=$((total_x + x))
  [ "$h" = 0 ] && [ "$x" = 0 ] && continue
  printf '%-34s %7s %7s\n' "$d" "$h" "$x"
done
printf '%-34s %7s %7s\n' TOTAL "$total_h" "$total_x"

echo
echo "Files still carrying a hue class:"
grep -rlE "$HUES" . 2>/dev/null | sed 's|^\./|  |' | head -25 || echo "  none"
