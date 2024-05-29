#
# Mailstats.py
#
#
# This script provides daily SpamFilter statistics.
#
# Re-written in python from Mailstats.pl (Perl) to conform to SME11 / Postfix / qpsmtpd log formats
# and html output added
#
# Todo
# 1. Make "yesterday" parameterised
#
import datetime
import sys
from chameleon import PageTemplateFile,PageTemplate
import pkg_resources
import re
import ipaddress

Mailstats_version = '1.2'

# Column numbering
Hour = 0
WebMail = 1
Local = 2
MailMan = 3
Relay = 4
DMARC = 5
Virus = 6
RBLDNS = 7
Geoip = 8
NonConf = 9
RejLoad = 10
Karma = 11
DelSpam = 12
QuedSpam = 13
Ham = 14
TOTALS = 15
PERCENT = 16
ColTotals = 24

def is_private_ip(ip):
	try:
		# Convert string to an IPv4Address object
		ip_addr = ipaddress.ip_address(ip)
	except ValueError:
		return False
	# Define private IP ranges
	private_ranges = [
		ipaddress.ip_network('10.0.0.0/8'),
		ipaddress.ip_network('172.16.0.0/12'),
		ipaddress.ip_network('192.168.0.0/16'),
	]

	# Check if the IP address is within any of these ranges
	for private_range in private_ranges:
		if ip_addr in private_range:
			return True

	return False

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
            'id': fields[0].strip() if len(fields) > 0 else None,
            'action': fields[1].strip() if len(fields) > 1 else None,
            'logterse': fields[2].strip() if len(fields) > 2 else None,
            'ip': fields[3].strip() if len(fields) > 3 else None,
            'sendurl': fields[4].strip() if len(fields) > 4 else None,
            'sendurl1': fields[5].strip() if len(fields) > 5 else None,
            'from-email': fields[6].strip() if len(fields) > 6 else None,
            'error-reason': fields[6].strip() if len(fields) > 6 else None,
            'to-email': fields[7].strip() if len(fields) > 7 else None,
            'error-plugin': fields[8].strip() if len(fields) > 8 else None,
            'action1': fields[8].strip() if len(fields) > 8 else None,
            'error-number' : fields[9].strip() if len(fields) > 9 else None,
            'sender': fields[10].strip() if len(fields) > 10 else None,
            'error-msg' :fields[10].strip() if len(fields) > 10 else None,
            'spam-status': fields[11].strip() if len(fields) > 11 else None,
            'error-result': fields[11].strip() if len(fields) > 11 else None,
            # Add more fields as necessary
        }
    except:
        #print(f"error:len:{len(fields)}")
        return_dict = {}    
    return return_dict

def count_entries_by_hour(log_entries):
    hourly_counts = defaultdict(int)
    for entry in log_entries:
        # Extract hour from the timestamp
        timestamp = entry['timestamp']
        hour = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H')
        hourly_counts[hour] += 1
    return hourly_counts

def initialize_2d_array(num_hours, column_headers_len):
    num_hours += 1
    return [[0] * column_headers_len for _ in range(num_hours)]

def search_2d_list(target, data):
    """
    Search for a target string in a 2D list of variable-length lists of strings.

    :param target: str, the string to search for
    :param data: list of lists of str, the 2D list to search
    :return: int, the row number where the target string is found, or -1 if not found
    """
    for row_idx, row in enumerate(data):
        if target in row:
            return row_idx
    return -1  # Return -1 if not found

    
if __name__ == "__main__":
	try:
		chameleon_version = pkg_resources.get_distribution("Chameleon").version
	except pkg_resources.DistributionNotFound:
		chameleon_version = "Version information not available"
	python_version = sys.version
	python_version = python_version[:8]
	current_datetime = datetime.datetime.now()
	formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M")
	yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).date()
	formatted_yesterday = yesterday.strftime("%Y-%m-%d %H:%M")

	hello_string = "Mailstats version:"+Mailstats_version+" Chameleon version:"+chameleon_version+" On Python:"+python_version+" at "+formatted_datetime
	print(hello_string)
	num_hours = 24  # Represents hours from 0 to 23 - adds extra one for column totals
	sorted_log_dict = read_and_filter_yesterday_log('/home/brianr/SME11Build/GITFiles/smecontribs/smeserver-mailstats/current.log')
	columnHeaders = ['Count','WebMail','Local','MailMan','Relay','DMARC','Virus','RBL/DNS','Geoip.','Non.Conf.','Karma','Rej.Load','Del.Spam','Qued.Spam?','  Ham','TOTALS','PERCENT']
	# dict for each colum identifying plugin that increments count
	columnPlugin = [''] * 17
	columnPlugin[Hour] = [] 
	columnPlugin[WebMail] = []
	columnPlugin[Local] = [] 
	columnPlugin[MailMan] = []
	columnPlugin[DMARC] = ['dmarc'] 
	columnPlugin[Virus] = ['pattern_filter', 'virus::pattern_filter','virus::clamav'] 
	columnPlugin[RBLDNS] = ['rhsbl', 'dnsbl','uribl']
	columnPlugin[Geoip] = ['check_badcountries'] 
	columnPlugin[NonConf] = ['check_earlytalker','check_relay','check_norelay', 'require_resolvable_fromhost'
                             ,'check_basicheaders','check_badmailfrom','check_badrcptto_patterns'
                             ,'check_badrcptto','check_spamhelo','check_goodrcptto extn','rcpt_ok'
                             ,'check_goodrcptto','check_smtp_forward','count_unrecognized_commands','tls','auth::auth_cvm_unix_local'
                             ,'auth::auth_imap', 'earlytalker','resolvable_fromhost','relay','headers','mailfrom','badrcptto','helo'
                             ,'check_smtp_forward','sender_permitted_from']
	columnPlugin[RejLoad] = ['loadcheck']
	columnPlugin[DelSpam] = []
	columnPlugin[QuedSpam] = []
	columnPlugin[Ham] = [] 
	columnPlugin[TOTALS] = []
	columnPlugin[PERCENT] = []
	columnPlugin[Karma] = ['karma']
            
	columnHeaders_len = len(columnHeaders)
	columnCounts_2d = initialize_2d_array(num_hours, columnHeaders_len)
	
	#From SMEServer DB
	DomainName = 'bjsystems.co.uk' #  $cdb->get('DomainName')->value;
	RHSenabled = True  #( $cdb->get('qpsmtpd')->prop('RHSBL') eq 'enabled' );
	DNSenabled = True  #( $cdb->get('qpsmtpd')->prop('DNSBL') eq 'enabled' );
	SARejectLevel = 12  #$cdb->get('spamassassin')->prop('RejectLevel');
	SATagLevel = 4  #$cdb->get('spamassassin')->prop('TagLevel');
	
	FetchmailIP = '127.0.0.200';       #Apparent Ip address of fetchmail deliveries
	WebmailIP = '127.0.0.1';           #Apparent Ip of Webmail sender
	localhost = 'localhost';           #Apparent sender for webmail
	FETCHMAIL = 'FETCHMAIL';    #Sender from fetchmail when Ip address not 127.0.0.200 - when qpsmtpd denies the email
	MAILMAN = "bounces";        #sender when mailman sending when orig is localhost
	DMARCDomain="dmarc"; 				#Pattern to recognised DMARC sent emails (this not very reliable, as the email address could be anything)
	DMARCOkPattern="dmarc: pass";  #Pattern to use to detect DMARC approval


	i = 1
	for timestamp, data in sorted_log_dict.items():

		if data['action'] == '(deny)':
			error = data['error-plugin']
			msg = data['error-msg']
			print(f"{i}: {timestamp} IP = {data['ip']} Result:{data['action']} {error} {msg}" )
		else:
			error = ""
			msg = ""
		i += 1

		# Count of in which hour it falls      
		#hour = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H')
		# Parse the timestamp string into a datetime object
		dt = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
		hour = dt.hour

		# Increment Count in which headings it falls
		#Hourly count and column total
		columnCounts_2d[hour][Hour] += 1
		columnCounts_2d[ColTotals][Hour] += 1
		#Row Totals
		columnCounts_2d[hour][TOTALS] += 1
		#Total totals
		columnCounts_2d[ColTotals][TOTALS] += 1
		#Queued email
		if data['action'] == '(queue)':
			columnCounts_2d[hour][Ham] += 1
			columnCounts_2d[ColTotals][Ham] += 1
		#spamassasin
		if data['spam-status'].lower().startswith('yes'):
			#Extract other parameters from this string
			# example: Yes, score=10.3 required=4.0 autolearn=disable
			spam_pattern = r'score=([\d.]+)\s+required=([\d.]+)'
			match = re.search(spam_pattern, data['spam-status'])
			if match:
				score = float(match.group(1))
				required = float(match.group(2))
				print(f"{data['spam-status']} / {score} {required}")
				if score >= SARejectLevel:
					columnCounts_2d[hour][DelSpam] += 1
					columnCounts_2d[ColTotals][DelSpam] += 1
				elif score >= required:
					columnCounts_2d[hour][QuedSpam] += 1
					columnCounts_2d[ColTotals][QuedSpam] += 1
		#Local send
		elif DomainName in data['sendurl']:
			columnCounts_2d[hour][Local] += 1
			columnCounts_2d[ColTotals][Local] += 1

		#Relay or webmail
		elif not is_private_ip(data['ip']) and is_private_ip(data['sendurl1']) and data['action1'] == 'queued':
			#Relay
			if data['action1'] == 'queued':
				columnCounts_2d[hour][Relay] += 1
				columnCounts_2d[ColTotals][Relay] += 1
		elif WebmailIP in data['sendurl1'] and not is_private_ip(data['ip']):
			#webmail
			columnCounts_2d[hour][WebMail] += 1
			columnCounts_2d[ColTotals][WebMail] += 1
			
		elif localhost in data['sendurl']:
			# but not if it comes from fetchmail
			if not FETCHMAIL in data['sendurl1']:
				# might still be from mailman here
				if MAILMAN in data['sendurl1']:
					#$mailmansendcount++;
					#$localsendtotal++;
					columnCounts_2d[hour][MailMan] += 1
					columnCounts_2d[ColTotals][MailMan] += 1
					#$counts{$abshour}{$CATMAILMAN}++;
					#$localflag = 1;
				else:
					#Or sent to the DMARC server
					#check for email address in $DMARC_Report_emails string
					#my $logemail = $log_items[4];
					if DMARCDomain in data['from-email']: #(index($DMARC_Report_emails,$logemail)>=0) or 
						#$localsendtotal++;
						#$DMARCSendCount++;
						localflag = 1;
					else:
						# ignore incoming localhost spoofs
						if not 'msg denied before queued' in data['error-msg']:
							#Webmail
							#$localflag = 1;
							#$WebMailsendtotal++;
							columnCounts_2d[hour][WebMail] += 1
							columnCounts_2d[ColTotals][WebMail] += 1
							#$WebMailflag = 1;
			else:
				#$localflag = 1;
				#$WebMailsendtotal++;
				#$WebMailflag = 1;
				columnCounts_2d[hour][WebMail] += 1
				columnCounts_2d[ColTotals][WebMail] += 1
			
		if data ['action'] == '(deny)' and data['error-plugin']:
			print(f"Found plugin {data['error-plugin']}")
			if data['error-plugin']:
				row = search_2d_list(data['error-plugin'],columnPlugin)
				if not row == -1:
					print(f"Found row: {row}")
					columnCounts_2d[hour][row] += 1
					columnCounts_2d[ColTotals][row] += 1

			
	#Now increment the column which the plugin name indicates
			
	#Now apply the results to the chameleon template

	# Path to the template file
	template_path = '/home/brianr/SME11Build/GITFiles/smecontribs/smeserver-mailstats/mailstats.html.pt'

	# Load the template
	with open(template_path, 'r') as template_file:
		template_content = template_file.read()

	# Create a Chameleon template instance
	template = PageTemplate(template_content)

	# Render the template with the 2D array data and column headers
	rendered_html = template(array_2d=columnCounts_2d, column_headers=columnHeaders, reporting_date=formatted_yesterday)

	# Write the rendered HTML to a file
	output_path = '/home/brianr/SME11Build/GITFiles/smecontribs/smeserver-mailstats/mailstats_for_'+formatted_yesterday+'.html'
	with open(output_path, 'w') as output_file:
		output_file.write(rendered_html)

	print(f"Rendered HTML saved to {output_path}")
    
