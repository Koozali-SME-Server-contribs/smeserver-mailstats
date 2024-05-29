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
import sys
from chameleon import PageTemplateFile,PageTemplate
import pkg_resources

Mailstats_version = '1.2'

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
            if '`' in line:
                parts = line.split(' ')
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
    # Split at the backtick - before it fields split at space, after, fields split at tab
    parts = data.split('`')
    #print(parts[0],parts[1])
    fields1 = parts[0].strip().split() if len(parts) > 0 else []
    fields2 = parts[1].split('\t') if len(parts) > 1 else []
    # then merge them
    fields = fields1 + fields2
#    if fields[8] != 'queued':
#    i = 0
#    print(f"len:{len(fields)}")
#    for part in fields:
#        print(f"{i}: {part}")
#        i  = i +1
#    quit()
    # and mapping:
    try:
        return_dict = {
            'id': fields[0] if len(fields) > 0 else None,
            'action': fields[1] if len(fields) > 1 else None,
            'logterse': fields[2] if len(fields) > 2 else None,
            'ip': fields[3] if len(fields) > 3 else None,
            'sendurl': fields[4] if len(fields) > 4 else None,
            'sendurl1': fields[5] if len(fields) > 5 else None,
            'from-email': fields[6] if len(fields) > 6 else None,
            'error-reason': fields[6] if len(fields) > 6 else None,
            'to-email': fields[7] if len(fields) > 7 else None,
            'error-plugin': fields[8] if len(fields) > 8 else None,
            'action1': fields[8] if len(fields) > 8 else None,
            'error-number' : fields[9] if len(fields) > 9 else None,
            'sender': fields[10] if len(fields) > 10 else None,
            'error-msg' :fields[10] if len(fields) > 10 else None,
            'spam-status': fields[11] if len(fields) > 11 else None,
            'error-result': fields[11] if len(fields) > 11 else None,
            # Add more fields as necessary
        }
    except:
        #print(f"error:len:{len(fields)}")
        return_dict = {}    
    return return_dict

if __name__ == "__main__":
    try:
        chameleon_version = pkg_resources.get_distribution("Chameleon").version
    except pkg_resources.DistributionNotFound:
        chameleon_version = "Version information not available"
    python_version = sys.version
    python_version = python_version[:8]
    current_datetime = datetime.datetime.now()
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M")
    hello_string = "Mailstats version:"+Mailstats_version+" Chameleon version:"+chameleon_version+" On Python:"+python_version+" at "+formatted_datetime
    print(hello_string)
    sorted_log_dict = read_and_filter_yesterday_log('/home/brianr/SME11Build/GITFiles/smecontribs/smeserver-mailstats/current.log')
    #print(sorted_log_dict)
    i = 1
    for timestamp, data in sorted_log_dict.items():
        if data['action'] == '(deny)':
            error = data['error-plugin']
            msg = data['error-msg']
        else:
            error = ""
            msg = ""
        print(f"{i}: {timestamp} IP = {data['ip']} Result:{data['action']} {error} {msg}" )
        i = i + 1


