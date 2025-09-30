# $Id: smeserver-mailstats.spec,v 1.7 2021/04/02 11:11:44 brianr Exp $
# Authority: brianread
# Name: Brian Read 

Summary: Daily mail statistics for SME Server
%define name smeserver-mailstats
Name: %{name}
%define version 11.1
%define release 12
%define full_version %{version}.%{release})
Version: %{version}
Release: %{release}%{?dist}
License: GPL
Group: SME/addon
Source: %{name}-%{version}.tgz

%global _binaries_in_noarch_packages_terminate_build 0
%global debug_package %{nil}

BuildRoot: /var/tmp/%{name}-%{version}-%{release}-buildroot
BuildArchitectures: noarch
Requires: smeserver-release => 9.0
Requires: qpsmtpd >= 0.96
BuildRequires: e-smith-devtools >= 1.13.1-03
Requires: perl-Switch
BuildRequires:  python36
Requires:       python36
# These need the EPEL repo enabled
# So install as:  dnf install smeserver-mailstats --enablerepo=epel,smecontribs
Requires:	html2text
Requires:	python3-chameleon
Requires:  	python3-mysql
Requires:   	python3-matplotlib
Requires:	python3-pip
Requires:       systemd-libs
AutoReqProv: no

%description
A script that via cron.d e-mails mail statistics to admin on a daily basis.
See https://wiki.koozali.org/mailstats

%prep
%setup

%build
perl createlinks

%install
/bin/rm -rf $RPM_BUILD_ROOT
(cd root ; /usr/bin/find . -depth -print | /bin/cpio -dump $RPM_BUILD_ROOT)
chmod +x $RPM_BUILD_ROOT/usr/bin/runmailstats.sh

now=$(date +"%Y-%m-%d %H:%M:%S")
# Replace placeholders in the Python program using sed
perl -pi -e 'if (!$done && s/^Mailstats_version *=.*/Mailstats_version = '\''%{full_version}'\'/') { $done = 1 }' $RPM_BUILD_ROOT/usr/bin/mailstats.py
perl -pi -e 'if (!$done && s/^build_date_time *=.*/build_date_time = "'"$now"'"/) { $done = 1 }' $RPM_BUILD_ROOT/usr/bin/mailstats.py

/bin/rm -f %{name}-%{version}-filelist
/sbin/e-smith/genfilelist --file '/etc/mailstats/db.php' 'attr(0640, root, apache)' $RPM_BUILD_ROOT | grep -v "\.pyc" | grep -v "\.pyo"  > %{name}-%{version}-filelist

install -Dpm 0755 journalwrap %{buildroot}%{_bindir}/journalwrap


%pre
/usr/bin/pip3 install -q pymysql
/usr/bin/pip3 install -q numpy
/usr/bin/pip3 install -q pandas

%clean
/bin/rm -rf $RPM_BUILD_ROOT

%files -f %{name}-%{version}-filelist
%defattr(-,root,root)
#%attr(0640, root, apache) %config(noreplace) /etc/mailstats/db.php
%{_bindir}/journalwrap

#%{_libdir}/libjournalwrap.so


%post
/sbin/ldconfig
#Remove www from systemd-journal group as is potential security risk
gpasswd -d  www systemd-journal
# and set setuid bit for c wrapper called from log detail web page
chmod u+s /usr/bin/journalwrap

%postun
/sbin/ldconfig

%changelog
* Tue Sep 30 2025 Brian Read <brianr@koozali.org> 11.1-12.sme
- Fix httpd conf fragment and add in ValidFrom Ips [SME: 13204]

* Fri Sep 26 2025 Brian Read <brianr@koozali.org> 11.1-11.sme
- Fix version number extraction fro supplied string [SME: 13121]

* Fri Sep 12 2025 Brian Read <brianr@koozali.org> 11.1-10.sme
- Fix version and build date from spec file  [SME: 13121]

* Fri Sep 12 2025 Brian Read <brianr@koozali.org> 11.1-8.sme
- Remove www from systemd-journal group and setuid bit in journal wrapper [SME: 13121]

* Fri Sep 12 2025 Brian Read <brianr@koozali.org> 11.1-7.sme
- Truncate Geoip table and add other category [SME: 13121]
- Cope with blank data in action1 [SME: 13121]

* Thu Sep 04 2025 Brian Read <brianr@koozali.org> 11.1-6.sme
- Add favicon to mailstats table, summary and detailed pages [SME: 13121]
- Bring DB config reading for mailstats itself inline with php summary and detailed logs - using /etc/mailstats/db.php [SME: 13121]
- Remove DB config fields from the SM2 config panel {sme: 13121]
- Arrange for password to be generated and mailstats user to be set with limited permissions [SME: 13121]

* Tue Sep 02 2025 Brian Read <brianr@koozali.org> 11.1-5.sme
- Speed up Journal access [SME: 13121]
- Fix missing blacklist URL [SME: 13121]
- Add extra security to php show summary page [SME: 13121]
- Fix up CSS for Summary Page [SME: 13121]
- Get Detail logs page working and prettyfy [SME: 13121]
- Add in C wrapper source code to interrogate journal [SME: 13121]
- Get permission and ownership right for /etc/mailstats/db.php [SME: 13121]
- Refactor main table header into two tables side by side [SME: 13121]

* Mon Sep 01 2025 Brian Read <brianr@koozali.org> 11.1-4.sme
- More fixes for Journal bytes instead of characters [SME: 13117]

* Mon Sep 01 2025 Brian Read <brianr@koozali.org> 11.1-3.sme
- Sort out ASCII escape codes in return from journalctl API  [SME: 13117]
- Add in Status enabled t default for mailstats DB [SME: 13118]

* Sun Apr 06 2025 Brian Read <brianr@koozali.org> 11.1-2.sme
- First build on Koji - and Add in SM2 panel [SME: 13116]

* Mon Dec 30 2024 Brian Read <brianr@koozali.org> 11.1-1.sme
- Update mailstats.py to accomodate change in log format for SME11 [SME: 12841]

* Fri Jun 07 2024 Brian Read <brianr@koozali.org> 1.1-18.sme
- Pull in python re-write from SME11 dev [SME: ]

* Wed Feb 15 2023 Brian Read <brianr@bjsystems.co.uk> 1.1-17.sme
- Add-in-imap-authorisation-log-string [SME: 12327]

* Fri Apr 02 2021 Brian Read <brianr@bjsystems.co.uk> 1.1-16.sme
- Take out dot in cron file and also re-direct errors to syslog [SME: 11519]

* Wed Mar 24 2021 Brian Read <brianr@bjsystems.co.uk> 1.1-15.sme
- Add Update event to createlinks [SME: 10923]

* Thu Dec 17 2020 Brian Read <brianr@bjsystems.co.uk> 1.1-14.sme
- Add in perl-Switch as requirement [SME: 11044]

* Mon Oct 19 2020 Brian Read <brianr@bjsystems.co.uk> 1.1-13.sme
- More uninitialised data [SME: 11044]

* Thu Apr 16 2020 brian read <brianr@bjsystems.co.uk> 1.1-12.sme
- Sort out uninitialised variable on no data.

* Sun Jan 5 2020 brian read <brianr@bjsystems.co.uk> 1.1-11.sme
- [sme:10858][sme:10327] Sort out email truncate and generally cleanup code format and take out debug crud
- Also change perl script file name to mailstats.pl

* Fri Oct 18 2019 brian read <brianr@bjsystems.co.uk> 1.1-10.sme
- Add Update event to createlinks display of geoip [SME: 9888]

* Wed Oct 12 2016 brian read <brianr@bjsystems.co.uk> 1.1-9.sme
- [sme:9716][sme:9717] add email specific stats and enhance relay monitoring and add code for smeoptimizer
 
* Sun Jul 03 2016 Jean-Philipe Pialasse <tests@pialasse.com> 1.1-7.sme
- set Requires qpsmtpd >=0.96

* Sat Jul 02 2016 Jean-Philipe Pialasse <tests@pialasse.com> 1.1-6.sme
- make compatible with qpstmpd 0.96 and new plugins [SME: 9588]
- work in progress : html version of email
- code by Brian Read <brianr@bjsystems.co.uk>
- thanks to Michael Doerner for his extensive testing

* Sun Apr 10 2016 Jean-Philipe Pialasse <tests@pialasse.com> 1.1-5.sme
- account for all unknown qpsmtpd plugins [SME: 9434]
- extra for "unofficial" extra clamav signatures
- code by Brian Read <brianr@bjsystems.co.uk>
- (only small suggestions from JP Pialasse aka Unnilennium)

* Thu Jun 25 2015 stephane de Labrusse <stephdl@de-labrusse.fr> 1.1-4
- creates the "mailstats" user [SME: 8957]
- Fixed the problem with Spamassassin scores and tags.
- Also added Geoip league table [SME: 8656]
- code done by  Brian Read <brianr@bjsystems.co.uk>

* Sun Jun 14 2015 stephane de Labrusse <stephdl@de-labrusse.fr> 1.1-3
- added a random cron job
- spamfilter-stats-7-update
- code done by Brian Read <brianr@bjsystems.co.uk> and John Crisp <jcrisp@safeandsoundit.co.uk>

* Mon Jun 16 2014 JP Pialasse <tests@pialasse.com> 1.1-1.sme
- initial import to SME9 contribs

* Mon Sep 23 2013 JP Pialasse <tests@pialasse.com> 1.1-4.sme
- uninitialized value in sprintf [SME: 4747]
- patch  smeserver-mailstats-1.0-spamfilter.patch

* Sun Sep 09 2012 JP Pialasse <tests@pialasse.com> 1.1-2.sme
- Add Update event to createlinks Unexpected failure string in log file: auth::auth_cvm_unix_local see [SME 7089]

* Sat May 26 2012 Brian J read <brianr@bjsystems.co.uk> 1.0-1.sme
- Initial version
