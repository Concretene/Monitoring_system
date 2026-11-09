# Source - https://stackoverflow.com/a/13265765
# Posted by procleaf
# Retrieved 2026-08-03, License - CC BY-SA 3.0

#! /usr/bin/env bash

FILELIST=/tmp/filelist
MONITOR_DIR="/home/jessicamaldonado/OneDrive/Results/Controls 1/Logs"
DATASET_DIR="/home/jessicamaldonado/OneDrive/Documents/ws_concretene/python_scripts/Dataset"

[[ -f "$FILELIST" ]] || find "$MONITOR_DIR" -maxdepth 1 -type f -printf '%f\n' | sort > "$FILELIST"

while :; do
    cur_files=$(find "$MONITOR_DIR" -maxdepth 1 -type f -printf '%f\n' | sort)

    diff "$FILELIST" <(printf '%s\n' "$cur_files") || {
        echo "[$(date)] Change detected in $MONITOR_DIR"

        python3 "$DATASET_DIR/concrete_validation.py" --logs-dir "$MONITOR_DIR" &&
            python3 "$DATASET_DIR/dataset_materials_concrete.py"

        find "$MONITOR_DIR" -maxdepth 1 -type f -printf '%f\n' | sort > "$FILELIST"
    }

    echo "Waiting for changes."
    sleep 180
done

