#!/bin/bash
exec 1> >(logger -t $(basename $0)) 2>&1
perl /usr/bin/mailstats.pl /var/log/qpsmtpd/\@* /var/log/qpsmtpd/current /var/log/sqpsmtpd/\@* /var/log/sqpsmtpd/current
