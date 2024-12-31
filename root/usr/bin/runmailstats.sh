#!/bin/bash
#exec 1> >(logger -t $(basename $0)) 2>&1
yesterday_date=$(date -d "yesterday" +'%b %d')
echo "Processing for:"$yesterday_date
cd /var/log/qpsmtpd
cat *.log  qpsmtpd.log-???????? >/opt/mailstats/logs/current1 2>/dev/null
cd /var/log/sqpsmtpd
cat *.log sqpsmtpd.log-???????? >/opt/mailstats/logs/current2 2>/dev/null
cd /var/log/uqpsmtpd
cat *.log  uqpsmtpd.log-???????? >/opt/mailstats/logs/current3 2>/dev/null
cd /opt/mailstats/logs
cat current1 current2 current3  2>/dev/null | grep  "$yesterday_date" > current.log 
ls -l
perl /usr/bin/mailstats.pl /opt/mailstats/logs/current.log
# and run new python one - start by copying and decoding log files
python3 /usr/bin/mailstats.py
echo "Done"