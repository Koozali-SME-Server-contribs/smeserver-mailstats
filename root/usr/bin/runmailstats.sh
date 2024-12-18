#!/bin/bash
#exec 1> >(logger -t $(basename $0)) 2>&1
perl /usr/bin/mailstats.pl /var/log/qpsmtpd/*.log  /var/log/sqpsmtpd/*.log /var/log/uqpsmtpd/*.log
# and run new python one - start by copying and decoding log files
yesterday_date=$(date -d "yesterday" +'%b %d')
echo $yesterday_date
cd /var/log/qpsmtpd
cat *.log  >/opt/mailstats/logs/current1 2>/dev/null
cd /var/log/sqpsmtpd
cat *.log >/opt/mailstats/logs/current2 2>/dev/null
cd /var/log/uqpsmtpd
cat *.log  >/opt/mailstats/logs/current3 2>/dev/null
cd /opt/mailstats/logs
cat current1 current2 current3  2>/dev/null | grep  "$yesterday_date" > current.log 
ls -l
python3 /usr/bin/mailstats.py
echo "Done"
