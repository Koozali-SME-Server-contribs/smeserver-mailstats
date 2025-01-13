#!/bin/bash
#exec 1> >(logger -t $(basename $0)) 2>&1
perl /usr/bin/mailstats.pl /var/log/qpsmtpd/\@* /var/log/qpsmtpd/current /var/log/sqpsmtpd/\@* /var/log/sqpsmtpd/current
# and run new python one - start by copying and decoding log files
yesterday_date=$(date -d "yesterday" +'%mm %d')
#cd /var/log/qpsmtpd
#cat \@*  current >/opt/mailstats/logs/current1 2>/dev/null
#cd /var/log/sqpsmtpd
#cat \@*  current >/opt/mailstats/logs/current2 2>/dev/null
cd /opt/mailstats/logs
#cat current1 current2  2>/dev/null |  /usr/local/bin/tai64nlocal | grep  "$yesterday_date" > current1.log 
python3 /usr/bin/mailstats-convert-log-sme10-to-sme11.py
yesterday_date=$(date -d "yesterday" +'%b %d')
cat output_log.txt | grep "$yesterday_date" | sort >current.log
ls -l
python3 /usr/bin/mailstats.py
echo "Done"