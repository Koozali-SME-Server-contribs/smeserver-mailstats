# $Id: smeserver-mailstats.spec,v 1.8 2023/02/15 09:40:09 brianr Exp $
# Authority: brianread
# Name: Brian Read 

Summary: Daily mail statistics for SME Server
%define name smeserver-mailstats
Name: %{name}
%define version 1.1
%define release 18
Version: %{version}
Release: %{release}%{?dist}
License: GPL
Group: SME/addon
Source: %{name}-%{version}.tar.xz

BuildRoot: /var/tmp/%{name}-%{version}-%{release}-buildroot
BuildArchitectures: noarch
Requires: smeserver-release => 9.0
Requires: qpsmtpd >= 0.96
BuildRequires: e-smith-devtools >= 1.13.1-03
Requires: perl-Switch

%description
A script that via cron.d e-mails mail statistics to admin on a daily basis.
See http://www.contribs.org/bugzilla/show_bug.cgi?id=819

%changelog
* Sun Jul 09 2023 cvs2git.sh aka Brian Read <brianr@koozali.org> 1.1-18.sme
- Roll up patches and move to git repo [SME: 12338]

* Sun Jul 09 2023 BogusDateBot
- Eliminated rpmbuild "bogus date" warnings due to inconsistent weekday,
  by assuming the date is correct and changing the weekday.

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

%prep
%setup

%build
perl createlinks

%install
/bin/rm -rf $RPM_BUILD_ROOT
(cd root ; /usr/bin/find . -depth -print | /bin/cpio -dump $RPM_BUILD_ROOT)
chmod +x $RPM_BUILD_ROOT/usr/bin/runmailstats.sh
/bin/rm -f %{name}-%{version}-filelist
/sbin/e-smith/genfilelist $RPM_BUILD_ROOT > %{name}-%{version}-filelist

%clean
/bin/rm -rf $RPM_BUILD_ROOT

%files -f %{name}-%{version}-filelist
%defattr(-,root,root)
