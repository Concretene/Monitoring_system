# Source - https://stackoverflow.com/a/13265765
# Posted by procleaf
# Retrieved 2026-08-03, License - CC BY-SA 3.0

#! /usr/bin/env bash

FILELIST=/tmp/filelist
MONITOR_DIR="/home/jessicamaldonado/OneDrive/Results_mortar/Logs"

[[ -f "$FILELIST" ]] || find "$MONITOR_DIR" -maxdepth 1 -type f -printf '%f\n' | sort > "$FILELIST"

while :; do
    cur_files=$(find "$MONITOR_DIR" -maxdepth 1 -type f -printf '%f\n' | sort)

    diff "$FILELIST" <(printf '%s\n' "$cur_files") || {
        echo "[$(date)] Change detected in $MONITOR_DIR"

        # Run the Python program
        python3 "/home/jessicamaldonado/OneDrive/Documents/ws_concretene/python_scripts/Dataset/dataset_materials_mortar.py"
        
        printf '%s\n' "$cur_files" > "$FILELIST"
    }

    echo "Waiting for changes."
    sleep 180
done

