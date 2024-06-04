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
# 2. Get data from SMEServer DB records
# 3. Other stats
# 4. Percentages for main table
# 5. Percentages and sort for Sub tables
#
from datetime import datetime, timedelta
import sys
from chameleon import PageTemplateFile,PageTemplate
import pkg_resources
import re
import ipaddress
import subprocess
import os
from collections import defaultdict


Mailstats_version = '1.2'

script_dir = os.path.dirname(os.path.abspath(__file__))
data_file_path = script_dir+'/../..'    #back to the top
now = datetime.now()
yesterday = now - timedelta(days=1)
formatted_yesterday = yesterday.strftime("%Y-%m-%d")
#html_page_path = data_file_path+"/home/e-smith/files/ibays/mesdb/html/mailstats/"
html_page_dir = data_file_path+"/opt/mailstats/html/"
template_dir = data_file_path+"/opt/mailstats/templates/"
logs_dir = data_file_path+"/opt/mailstats/logs/"

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
	try:
		main_part, microseconds = timestamp.split('.')
		# Truncate the last three digits of the microseconds
		truncated_microseconds = microseconds[:-3]
		# Combine the main part and truncated microseconds
		truncated_timestamp = f"{main_part}.{truncated_microseconds}"
	except Exception as e:
		print(f"{e} {timestamp}")
		raise ValueError
	# Remove the microseconds completely if they exist
	return truncated_timestamp.split('.')[0]

# def filter_yesterdays_entries(log_entries):
	# # Determine yesterday's date
	# yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).date()   
	# # Filter entries for yesterday's date
	# yesterday_entries = []
	# for timestamp, data in log_entries:
		# truncated_timestamp = truncate_microseconds(timestamp)
		# entry_date = datetime.datetime.strptime(truncated_timestamp, '%Y-%m-%d %H:%M:%S').date()
		# if entry_date == yesterday:
			# parsed_data = parse_data(data)
			# yesterday_entries.append((truncated_timestamp, parsed_data))
	
	# return yesterday_entries
	
def read_in_yesterday_log_file(file_path):
	# Read the file and split each line into a list - timestamp and the rest
	# Get current date and calculate yesterday's date
	log_entries = []
	skip_record_count = 0;
	with open(file_path, 'r') as file:
		for Line in file:
			#extract time stamp
			try:
				entry = split_timestamp_and_data(Line)
				# compare with yesterday
				timestamp_str = truncate_microseconds(entry[0])
			except ValueError as e:
				#print(f"ValueError {e} on timestamp create {timestamp_str}:{entry[0]} {entry[1]}")
				skip_record_count += 1
				continue
			# Parse the timestamp string into a datetime object
			# Ignoring extra microseconds 
			try:
				timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
			except ValueError as e:
				print(f"ValueError {e} on timestamp extract {timestamp_str}:{entry[1]}")
			if timestamp.date() == yesterday.date():
				log_entries.append((timestamp, entry[1]))
	return [log_entries,skip_record_count]
	
def filter_summary_records(log_entries):
	# Return just the summary records
	filtered_log_entries = []
	skipped_entry_count = 0
	for line in log_entries:
		#print(line)
		#quit()
		if '`' in line[1]:
			filtered_log_entries.append(line)
		else:
			skipped_entry_count += 1
	return [filtered_log_entries,skipped_entry_count]
	
def sort_log_entries(log_entries):
	# Sort the records, based on the timestamp
	sorted_entries = sorted(log_entries, key=lambda x: x[0])
	# and return a dictionary
	sorted_dict = {entry[0]: entry[1] for entry in sorted_entries}
	return sorted_dict
	

# def read_and_filter_yesterday_log(file_path):
	# # Read the file and split each line into a dictionary
	# log_entries = []
	# with open(file_path, 'r') as file:
		# for line in file:
			# if '`' in line:
				# parts = line.split(' ')
				# if parts:
					# # Combine parts to form the complete timestamp
					# timestamp = ' '.join(parts[:2])
					# data = ' '.join(parts[2:])  # The rest of the line after date and time
					# log_entries.append((timestamp, data))
	
	# # Filter the entries to keep only those from yesterday
	# filtered_entries = filter_yesterdays_entries(log_entries)
	
	# # Sort the filtered log entries based on the truncated timestamp
	# sorted_entries = sorted(filtered_entries, key=lambda x: datetime.datetime.strptime(x[0], '%Y-%m-%d %H:%M:%S'))
	
	# # Create a dictionary
	# sorted_dict = {entry[0]: entry[1] for entry in sorted_entries}
	
	# return sorted_dict

def parse_data(data):
	# Split data string into parts and map to named fields.
	# Adjust the field names and parsing logic according to your data format.
	# Split at the backtick - before it fields split at space, after, fields split at tab
	parts = data.split('`')
	#print(f"{parts[0]}:{parts[1]}")
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
			'sendurl': fields[4].strip() if len(fields) > 4 else None,     #1
			'sendurl1': fields[5].strip() if len(fields) > 5 else None,    #2
			'from-email': fields[6].strip() if len(fields) > 6 else None,  #3
			'error-reason': fields[6].strip() if len(fields) > 6 else None, #3
			'to-email': fields[7].strip() if len(fields) > 7 else None,		#4
			'error-plugin': fields[8].strip() if len(fields) > 8 else None,  #5
			'action1': fields[8].strip() if len(fields) > 8 else None,       #5
			'error-number' : fields[9].strip() if len(fields) > 9 else None, #6
			'sender': fields[10].strip() if len(fields) > 10 else None,      #7
			'error-msg' :fields[10].strip() if len(fields) > 10 else None,   #7
			'spam-status': fields[11].strip() if len(fields) > 11 else None, #8 
			'error-result': fields[11].strip() if len(fields) > 11 else None,#8
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

def initialize_2d_array(num_hours, column_headers_len,reporting_date):
	num_hours += 1  # Adjust for the zeroth hour
	# Initialize the 2D list with zeroes
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
	
def check_html2text_installed():
	try:
		# Check if html2text is installed by running 'which html2text'
		result = subprocess.run(
			['which', 'html2text'],
			check=True,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE
		)

		# If the command finds html2text, it will output the path
		html2text_path = result.stdout.decode('utf-8').strip()
		
		if not html2text_path:
			raise FileNotFoundError
		
		print(f"html2text is installed at: {html2text_path}")
		return True

	except subprocess.CalledProcessError:
		print("html2text is not installed. Please install it using your package manager.", file=sys.stderr)
		return False    

def html_to_text(input_file, output_file):
	if not check_html2text_installed():
		sys.exit(1)
	try:
		# Run the html2text command with -b0 --pad-tables parameters
		result = subprocess.run(
			['html2text', '-b0', '--pad-tables', input_file],
			check=True,  # Raise a CalledProcessError on non-zero exit
			stdout=subprocess.PIPE,  # Capture stdout
			stderr=subprocess.PIPE   # Capture stderr
		)

		# Write the stdout from the command to the output file
		with open(output_file, 'w', encoding='utf-8') as outfile:
			outfile.write(result.stdout.decode('utf-8'))

		print(f"Converted {input_file} to {output_file}")
	except subprocess.CalledProcessError as e:
		print(f"Error occurred: {e.stderr.decode('utf-8')}", file=sys.stderr)
		sys.exit(e.returncode)

def get_html2text_version():
	try:
		result = subprocess.run(['html2text', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
		# Ensure the result is treated as a string in Python 3.6+
		return result.stdout.strip()
	except subprocess.CalledProcessError as e:
		print(f"Error occurred while checking html2text version: {e}", file=sys.stderr)
		return None
 
def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
	"""
	Call in a loop to create a terminal progress bar
	@params:
		iteration   - Required : current iteration (Int)
		total       - Required : total iterations (Int)
		prefix      - Optional : prefix string (Str)
		suffix      - Optional : suffix string (Str)
		decimals    - Optional : positive number of decimals in percent complete (Int)
		length      - Optional : character length of bar (Int)
		fill        - Optional : bar fill character (Str)
		print_end   - Optional : end character (e.g. "\r", "\r\n") (Str)
	"""
	if total == 0:
		raise ValueError("Progress total is zero")
	percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
	filled_length = int(length * iteration // total)
	bar = fill * filled_length + '-' * (length - filled_length)
	print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
	# Print New Line on Complete
	if iteration == total:
		print()
 
def insert_string_after(original:str, to_insert:str, after:str) -> str:
	"""
	Insert to_insert into original after the first occurrence of after.
	
	:param original: The original string.
	:param to_insert: The string to be inserted.
	:param after: The set of characters after which the string will be inserted.
	:return: The new string with to_insert inserted after after.
	"""
	position = original.find(after)
	#print(position)
	
	if position == -1:
		# 'after' string is not found in 'original'
		return original
	#print(f"{len(after)}")
	# Position of the insertion point
	insert_pos = position + len(after)
	
	return original[:insert_pos] + to_insert + original[insert_pos:]
	
def split_timestamp_and_data(log_entry: str) -> list:
	"""
	Split a log entry into timestamp and the rest of the data.
	
	:param log_entry: The log entry as a string.
	:return: A list with two entries: [timestamp, rest_of_data].
	"""
	# The timestamp is always the first part, up to the first space after the milliseconds
	parts = log_entry.split(' ', 2)
	
	if len(parts) < 3:
		raise ValueError(f"The log entry format is incorrect {parts}")
	
	timestamp = ' '.join(parts[:2])
	rest_of_data = parts[2]
	#print(f"{timestamp} {rest_of_data}")
	
	return [timestamp, rest_of_data]
	
def render_sub_table(table_title,table_headers,found_values):
	# NeedNOTE: also need to compute the percentages here.
	template_path = template_dir+'mailstats-sub-table.html.pt'
	# Load the template
	with open(template_path, 'r') as template_file:
		template_content = template_file.read()
	# Create a Chameleon template instance
	try:
		template = PageTemplate(template_content)
		# Render the template with the 2D array data and column headers
		try:
			rendered_html = template(array_2d=found_values, column_headers=table_headers, title=table_title)
		except Exception as e:
			print(f"{table_title}: A chameleon controller render error occurred: {e}")
			raise ValueError
	except Exception as e:
		print(f"{table_title}: A chameleon controller template error occurred: {e}")
		raise ValueError
	return rendered_html
	  
if __name__ == "__main__":
	try:
		chameleon_version = pkg_resources.get_distribution("Chameleon").version
	except pkg_resources.DistributionNotFound:
		chameleon_version = "Version information not available"
	python_version = sys.version
	python_version = python_version[:8]
	current_datetime = datetime.now()
	formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M")

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
	hello_string = "Mailstats:"+Mailstats_version+' for '+DomainName+" at "+formatted_datetime+" for "+formatted_yesterday
	print(hello_string)
	version_string = "Chameleon:"+chameleon_version+" Python:"+python_version
	print(version_string)

	num_hours = 25  # Represents hours from 0 to 23 - adds extra one for column totals and another for percentages

	log_file = logs_dir+'current.log'
	log_entries,skip_count = read_in_yesterday_log_file(log_file)
	if len(log_entries) == 0:
		print(f"No records found in {data_file}")
		quit()
	else:
		print(f"Found {len(log_entries)} entries in log for for {formatted_yesterday} skipped {skip_count}")
	summary_log_entries,skip_count = filter_summary_records(log_entries)
	print(f"Found {len(summary_log_entries)} summary entries and skipped {skip_count} entries")
	sorted_log_dict = sort_log_entries(summary_log_entries)
	print(f"Sorted {len(sorted_log_dict)} entries")

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
	columnCounts_2d = initialize_2d_array(num_hours, columnHeaders_len,formatted_yesterday)
	
	virus_pattern = re.compile(r"Virus found: (.*)")
	found_viruses = defaultdict(int)
	
	found_qpcodes = defaultdict(int)
	qpcodes_pattern = re.compile(r".*(\(.*\)).*'")
	i = 0;
	sorted_len= len(sorted_log_dict)
	# Initial call to print the progress bar
	print_progress_bar(0, sorted_len, prefix='Progress:', suffix='Complete', length=50)
	for timestamp, data in sorted_log_dict.items():
		i += 1
		print_progress_bar(i, sorted_len, prefix='Scanning for main table:', suffix='Complete', length=50)
		#print(f"{i*100/len}%")
		# Count of in which hour it falls      
		#hour = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H')
		# Parse the timestamp string into a datetime object
		dt = timestamp
		hour = dt.hour
		# parse the data
		#print(data)
		parsed_data = parse_data(data)
		#print(f"parsed_data['action']:{parsed_data['action']}\n")
		
		# Increment Count in which headings it falls
		#Hourly count and column total
		columnCounts_2d[hour][Hour] += 1
		columnCounts_2d[ColTotals][Hour] += 1
		#Row Totals
		columnCounts_2d[hour][TOTALS] += 1
		#Total totals
		columnCounts_2d[ColTotals][TOTALS] += 1
		#Queued email
		if parsed_data['action'] == '(queue)':
			columnCounts_2d[hour][Ham] += 1
			columnCounts_2d[ColTotals][Ham] += 1
		#spamassasin
		if parsed_data['spam-status'].lower().startswith('yes'):
			#Extract other parameters from this string
			# example: Yes, score=10.3 required=4.0 autolearn=disable
			spam_pattern = r'score=([\d.]+)\s+required=([\d.]+)'
			match = re.search(spam_pattern, parsed_data['spam-status'])
			if match:
				score = float(match.group(1))
				required = float(match.group(2))
				#print(f"{parsed_data['spam-status']} / {score} {required}")
				if score >= SARejectLevel:
					columnCounts_2d[hour][DelSpam] += 1
					columnCounts_2d[ColTotals][DelSpam] += 1
				elif score >= required:
					columnCounts_2d[hour][QuedSpam] += 1
					columnCounts_2d[ColTotals][QuedSpam] += 1
		#Local send
		elif DomainName in parsed_data['sendurl']:
			columnCounts_2d[hour][Local] += 1
			columnCounts_2d[ColTotals][Local] += 1

		#Relay or webmail
		elif not is_private_ip(parsed_data['ip']) and is_private_ip(parsed_data['sendurl1']) and parsed_data['action1'] == 'queued':
			#Relay
			if parsed_data['action1'] == 'queued':
				columnCounts_2d[hour][Relay] += 1
				columnCounts_2d[ColTotals][Relay] += 1
		elif WebmailIP in parsed_data['sendurl1'] and not is_private_ip(parsed_data['ip']):
			#webmail
			columnCounts_2d[hour][WebMail] += 1
			columnCounts_2d[ColTotals][WebMail] += 1
			
		elif localhost in parsed_data['sendurl']:
			# but not if it comes from fetchmail
			if not FETCHMAIL in parsed_data['sendurl1']:
				# might still be from mailman here
				if MAILMAN in parsed_data['sendurl1']:
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
					if DMARCDomain in parsed_data['from-email']: #(index($DMARC_Report_emails,$logemail)>=0) or 
						#$localsendtotal++;
						#$DMARCSendCount++;
						localflag = 1;
					else:
						# ignore incoming localhost spoofs
						if not 'msg denied before queued' in parsed_data['error-msg']:
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
			
		#Now increment the column which the plugin name indicates
		if parsed_data['action'] == '(deny)' and parsed_data['error-plugin']:
			#print(f"Found plugin {parsed_data['error-plugin']}")
			if parsed_data['error-plugin']:
				row = search_2d_list(parsed_data['error-plugin'],columnPlugin)
				if not row == -1:
					#print(f"Found row: {row}")
					columnCounts_2d[hour][row] += 1
					columnCounts_2d[ColTotals][row] += 1
					# a few ad hoc extra extractons of data
					if row == Virus:
						match = virus_pattern.match(parsed_data['action1'])
						if match:
							found_viruses[match.group(1)] += 1
						else:
							found_viruses[parsed_data['action1']] += 1
					elif parsed_data['error-plugin'] == 'naughty':
						match = qpcodes_pattern.match(parsed_data['action1'])
						if match:
							rejReason = match.group(1)
							found_qpcodes[parsed_data['error-plugin']+"-"+rejReason] += 1
						else:
							found_qpcodes['Unknown'] += 1
					else:
						found_qpcodes[parsed_data['action1']] += 1

	print()
	
	# Now scan for the other lines in the log of interest
	found_countries = defaultdict(int)
	geoip_pattern = re.compile(r".*check_badcountries: GeoIP Country: (.*)")
	dmarc_pattern = re.compile(r".*dmarc: pass")
	total_countries = 0
	DMARCOkCount = 0
	# Pick up all log_entries = read_yesterday_log_file(data_file)
	#sorted_log_dict = sort_log_entries(log_entries)

	i = 0
	j = 0
	log_len = len(log_entries)
	print_progress_bar(0, log_len, prefix='Progress:', suffix='Complete', length=50)
	for data in log_entries:
		i += 1
		print_progress_bar(i, log_len, prefix='Scanning for sub tables:', suffix='Complete', length=50)
		#Pull out Geoip countries for analysis table
		if "check_badcountries: GeoIP Country" in data:
			j += 1
		match = geoip_pattern.match(data[1])
		if match:
			country = match.group(1)
			found_countries[country] += 1
			total_countries += 1
			continue
		#Pull out DMARC approvals
		match = dmarc_pattern.match(data[1])
		if match:
			DMARCOkCount += 1
			continue
			
	#print(f"J:{j} I:{i}")
	#Now apply the results to the chameleon template - main table
	# Path to the template file
	template_path = template_dir+'mailstats.html.pt'
	# Load the template
	with open(template_path, 'r') as template_file:
		template_content = template_file.read()
	# Create a Chameleon template instance
	template = PageTemplate(template_content)
	# Render the template with the 2D array data and column headers
	rendered_html = template(array_2d=columnCounts_2d, column_headers=columnHeaders, reporting_date=formatted_yesterday, title=hello_string, version=version_string)
	total_html = rendered_html

	#Now apply the results to the chameleon template - subservient tables
	#qpsmtd codes
	qpsmtpd_headers = ["Code",'Count','Percent','Reason']
	qpsmtpd_title = 'Qpsmtpd codes league table:'
	rendered_html = render_sub_table(qpsmtpd_title,qpsmtpd_headers,found_qpcodes)
	# Add it to the total 
	total_html = insert_string_after(total_html,rendered_html, "<!---Add in sub tables here -->")
	
	#Geoip Country codes
	geoip_headers  = ['Country','Count','Percent','Rejected?']
	geoip_title = 'Geoip results:'
	rendered_html = render_sub_table(geoip_title,geoip_headers,found_countries)
	# Add it to the total 
	total_html = insert_string_after(total_html,rendered_html, "<!---Add in sub tables here -->")
	
	#Add in navigation html - next/previous/see in browser
	day_format = "%Y-%m-%d"
	# Convert the time string to a datetime object
	date_obj = datetime.strptime(formatted_yesterday, day_format)
	# Compute the next date by adding one day
	next_date = date_obj + timedelta(days=1)
	# Compute the previous date by subtracting one day
	previous_date = date_obj - timedelta(days=1)
	# Convert the datetime objects back to strings in the desired format
	next_date_str = next_date.strftime(day_format)
	previous_date_str = previous_date.strftime(day_format)
	navigation_str_html = "<div class='linksattop'>\
<a class='prevlink' href='http://${DomainName}/mailstats/mailstats_for_${PreviousDate}.html'>Previous</a>\
<div class='divseeinbrowser'><a class='seeinbrowser' href='http://${DomainName}/mailstats/mailstats-${TodayDate}.html'>See in browser</a></div>\
<a class='nextlink' href='http://${DomainName}/mailstats/mailstats_for_${NextDate}.html'>Next</a>\
</div>"
	template = PageTemplate(navigation_str_html)
	Nav_str = template(PreviousDate=previous_date_str,NextDate=next_date_str,TodayDate=formatted_yesterday,DomainName=DomainName)
	# And insert it
	total_html = insert_string_after(total_html,Nav_str, "<!---Navigation here-->")

	# Write the rendered HTML to a file
	output_path = html_page_dir+'mailstats_for_'+formatted_yesterday
	output_path = output_path.replace(' ','_')
	with open(output_path+'.html', 'w') as output_file:
		output_file.write(total_html)
	#and create a text version if the local version of html2text is suffiicent
	if get_html2text_version() == '2019.9.26':
		html_to_text(output_path+'.html',output_path+'.txt')
	print(f"Rendered HTML saved to {output_path}.html/txt")
	


