#!/bin/bash

# Extract the earliest date from the journalctl header for qpsmtpd service
earliest_date=$(journalctl -u qpsmtpd | head -n 1 | sed -n 's/.*Logs begin at [A-Za-z]* \([0-9-]*\).*/\1/p')

# Get yesterday's date
yesterday=$(date -d 'yesterday' +%F)

current_date="$earliest_date"

# Loop from earliest date to yesterday
while [[ "$current_date" < "$yesterday" || "$current_date" == "$yesterday" ]]; do
  runmailstats.sh "$current_date"
  current_date=$(date -I -d "$current_date + 1 day")
done
