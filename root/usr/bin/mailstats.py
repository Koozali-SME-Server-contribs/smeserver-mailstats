#
# Mailstats.py
#
#
# This script provides daily SpamFilter statistics.
#
# Re-written in python from Mailstats.pl (Perl) to conform to SME11 / Postfix / qpsmtpd log formats
# and html output added
#
import datetime
import datetime

def truncate_microseconds(timestamp):
    # Split timestamp into main part and microseconds
    main_part, microseconds = timestamp.split('.')
    # Truncate the last three digits of the microseconds
    truncated_microseconds = microseconds[:-3]
    # Combine the main part and truncated microseconds
    truncated_timestamp = f"{main_part}.{truncated_microseconds}"
    # Remove the microseconds completely if they exist
    return truncated_timestamp.split('.')[0]

def filter_yesterdays_entries(log_entries):
    # Determine yesterday's date
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).date()
    
    # Filter entries for yesterday's date
    yesterday_entries = []
    for timestamp, data in log_entries:
        truncated_timestamp = truncate_microseconds(timestamp)
        entry_date = datetime.datetime.strptime(truncated_timestamp, '%Y-%m-%d %H:%M:%S').date()
        if entry_date == yesterday:
            parsed_data = parse_data(data)
            yesterday_entries.append((truncated_timestamp, parsed_data))
    
    return yesterday_entries

def read_and_filter_yesterday_log(file_path):
    # Read the file and split each line into a dictionary
    log_entries = []
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.strip().split()
            if parts:
                # Combine parts to form the complete timestamp
                timestamp = ' '.join(parts[:2])
                data = ' '.join(parts[2:])  # The rest of the line after date and time
                log_entries.append((timestamp, data))
    
    # Filter the entries to keep only those from yesterday
    filtered_entries = filter_yesterdays_entries(log_entries)
    
    # Sort the filtered log entries based on the truncated timestamp
    sorted_entries = sorted(filtered_entries, key=lambda x: datetime.datetime.strptime(x[0], '%Y-%m-%d %H:%M:%S'))
    
    # Create a dictionary
    sorted_dict = {entry[0]: entry[1] for entry in sorted_entries}
    
    return sorted_dict

def parse_data(data):
    # Split data string into parts and map to named fields.
    # Adjust the field names and parsing logic according to your data format.
    parts = data.split('`')
    fields = parts[1].strip().split('\t') if len(parts) > 1 else []
    # Example mapping:
    return {
        'id': fields[0],
        'action': fields[1] if len(fields) > 0 else None,
        'logterse': fields[2] if len(fields) > 1 else None,
        'reversequote': fields[3] if len(fields) > 2 else None,
        'ip': fields[4] if len(fields) > 3 else None,
        'sendurl': fields[5] if len(fields) > 4 else None,
        'sendurl1': fields[6] if len(fields) > 5 else None,
        'error-plugin': fields[6] if len(fields) > 5 else None,
        'from-email': fields[7] if len(fields) > 6 else None,
        'error-reason': fields[7] if len(fields) > 6 else None,
        'to-email': fields[8] if len(fields) > 7 else None,
        'action1': fields[9] if len(fields) > 8 else None,
        'sendurl2': fields[10] if len(fields) > 9 else None,
        'spam-yes-no': fields[11] if len(fields) > 10 else None,
        'spam-score': fields[12] if len(fields) > 11 else None,
        'spam-score-reqd': fields[13] if len(fields) > 12 else None,
        'autolearn': fields[14] if len(fields) > 13 else None,
        'logterse': fields[15] if len(fields) > 14 else None,
        'logterse': fields[16] if len(fields) > 15 else None
        # Add more fields as necessary
    }


# Example usage
sorted_log_dict = read_and_filter_yesterday_log('/home/brianr/SME11Build/GITFiles/smecontribs/smeserver-mailstats/current.log')
#print(sorted_log_dict)

for timestamp, data in sorted_log_dict.items():
    print(f"{timestamp} IP = {data['ip']}")


