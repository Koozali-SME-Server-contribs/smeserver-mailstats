#!/bin/bash
exec 1> >(logger -t $(basename $0)) 2>&1
perl /usr/bin/mailstats.pl /var/log/qpsmtpd/\@* /var/log/qpsmtpd/current /var/log/sqpsmtpd/\@* /var/log/sqpsmtpd/current
# and run new python one - start by copying and decoding log files
cd /var/log/qpsmtpd
cat \@*  current >/opt/mailstats/logs/current1 2>/dev/null
cd /var/log/sqpsmtpd
cat \@*  current >/opt/mailstats/logs/current2 2>/dev/null
cd /opt/mailstats/logs
ls -l
cat current1 current2  2>/dev/null | tai64nlocal > current.log 
python3 /usr/bin/mailstats.py
echo "Done"

