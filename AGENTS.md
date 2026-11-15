# AGENTS.md

SME Server (Koozali) contrib RPM for daily mail statistics. It packages a Python analysis engine, a web UI, a Server Manager panel, and a setuid C wrapper that reads `systemd-journal`. Packaged content is staged under `root/`; the RPM is built from `smeserver-mailstats.spec`.

## Packaging model / critical gotchas

- **The installed content comes from the source tarball, not `root/` directly.** `smeserver-mailstats.spec` sets `Source: %{name}-%{version}.tgz` (`smeserver-mailstats-11.1.tgz`), and `%install` copies from the extracted tarball. The tarball's top level mirrors this repo: `root/`, plus `createlinks` and `journalwrap`.
- **Regenerate the tgz after changing anything under `root/`.** `*.tgz` is gitignored, so it is never kept in sync automatically. As of Nov 2026 the checked-in tgz is **stale**: it lacks the 11.1-16/17 changes already present in `root/` (CSP header in `templates/etc/httpd/conf/httpd.conf/100mailstats`, MariaDB user fix in `templates/etc/e-smith/sql/init/99mailstats`, Firefox autofill CSS/JS fixes). A Koji build will ship the old code unless you rebuild the tarball.
- **`journalwrap` is a prebuilt binary, not compiled by rpm.** Source is `journalwrap.c` (includes `<systemd/sd-journal.h>`, links libsystemd; needs `systemd-devel`). `%install` copies the prebuilt `journalwrap` binary from the extracted tarball; a committed copy lives in `additional/journalwrap`. After editing `journalwrap.c`, recompile and refresh both the tgz and `additional/journalwrap`. Do not rely on `%build` to compile it.
- **Version/date lines in `mailstats.py` are fake on purpose.** `Mailstats_version = '11.1.10.el8.sme)'` and `build_date_time = "2025-..."` are sed-replaced by the spec during `%install` (see `%install`). Don't "fix" them.
- **Never commit the `11_1-*_el8_sme/` directories** — they are Koji build outputs, kept out via `*el8*` in `.gitignore`.
- **Not buildable standalone.** The `Makefile` fetches and includes `common/Makefile.common` from the SME contribs CVS module; building requires that module/network access plus the e-smith devtooling.

## Layout

- `root/etc/e-smith/` — e-smith templating and config wiring:
  - `db/configuration/defaults/mailstats/` and `db/configuration/migrate/80DBPass` — `mailstats` config record; a random DB password is auto-generated on migration (don't trust the placeholder `db.php`).
  - `templates/etc/e-smith/sql/init/99mailstats` — DB + `mailstats` user setup, `templates/etc/httpd/conf/httpd.conf/100mailstats` — httpd fragment, `templates/etc/mailstats/db.php/10DBDetails` — generates `/etc/mailstats/db.php` from the config record.
  - `createlinks` (Perl) wires these templates into event `smeserver-mailstats-update` and restarts `httpd` and `mysql`.
- `root/opt/mailstats/` — web app: `html/ShowDetailedLogs.php`, `html/showSummaryLogs.php`, css/js, Chameleon templates.
- `root/usr/bin/` — `mailstats.py` (main engine; reads qpsmtpd journal logs), `runmailstats.sh` (daily driver, Python `yesterday`), `runallmailstats.sh` (backfill from earliest journal date), `mailstats-convert-log-sme10-to-sme11.py`, legacy `mailstats.pl` (old Perl version, still shipped).
- `root/usr/share/smanager/` — Server Manager panel: Mojolicious controllers (`Controller/Mailstats*.pm`), `.ep` templates, I18N lex.
- `additional/journalwrap` — committed prebuilt setuid binary used for detailed-log journal access.

## Runtime wiring

- `/etc/cron.d/mailstats` runs `runmailstats.sh` daily at 00:00 with a random sleep offset; it calls `python3 /usr/bin/mailstats.py -d <date>`.
- The web pages read DB creds from env vars (`MAILSTATS_DB_*`) with fallback to `/etc/mailstats/db.php` (generated at template-expansion time from the `mailstats` config record).

## Testing

- No unit test suite exists. Verify by building the RPM and installing on an SME Server (or in Koji); `mailstats.py` needs a real qpsmtpd + `systemd-journal` environment.
