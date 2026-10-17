#!/bin/zsh
# Faktúrový agent – spustenie dvojklikom (Finder / plocha)
printf '\e[8;45;150t'                       # väčšie okno Terminálu
cd "$(dirname "$0")" 2>/dev/null || cd ~/faktury-agent
[ -f faktury.py ] || cd ~/faktury-agent
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate faktury
python faktury.py "$@"
echo
read "?Hotovo – Enter zavrie okno…"
osascript -e 'tell application "Terminal" to close front window' >/dev/null 2>&1 &
