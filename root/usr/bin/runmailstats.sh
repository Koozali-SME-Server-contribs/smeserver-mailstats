#!/bin/bash

# Validate date format (YYYY-MM-DD)
validate_date() {
    local date_regex="^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"
    if [[ ! $1 =~ $date_regex ]]; then
        echo "Error: Invalid date format. Use YYYY-MM-DD" >&2
        exit 1
    fi
}

# Set date (default: yesterday)
if [ -n "$1" ]; then
    run_date="$1"
    validate_date "$run_date"
else
    run_date=$(date -d "yesterday" +%F)
fi

# Run mailstats with validated date 
python3 /usr/bin/mailstats.py -d "$run_date"