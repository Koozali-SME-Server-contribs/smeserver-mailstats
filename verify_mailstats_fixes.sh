#!/bin/bash
# verify_mailstats_fixes.sh
# Checks the two smeserver-mailstats fixes on a test box:
#   1) Bug 13827  - CREATE grant for mailstats_rw (self-heal table creation)
#   2) 80DBPass   - CSPRNG password generator: correct length/alphabet, no literal-
#                    breaking chars; special characters (present or not) are
#                    tolerated by the quoting in the SQL init / db.php.
# Read-only by default; pass --run to also execute the nightly job.
set -u

DB_NAME="mailstats"
DB_USER="mailstats_rw"
DB_PHP="/etc/mailstats/db.php"
RUN_JOB=0

for arg in "$@"; do
    case "$arg" in
        --run) RUN_JOB=1 ;;
        *) echo "usage: $0 [--run]"; exit 1 ;;
    esac
done

echo "======================================================"
echo " 1) Password generator fix (80DBPass)"
echo "======================================================"

# Alphabet used by the generator (mirror of 80DBPass: no $ @ ' \ backtick).
ALPHABET='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!%^&*?_-+='

# Extract the password from db.php ignoring any template header/preamble.
PASS=""
if [ -f "$DB_PHP" ]; then
    PASS=$(sed -n "s/.*'pass' => '\([^']*\)'.*/\1/p" "$DB_PHP" | head -n1)
fi

if [ -z "$PASS" ]; then
    echo "WARNING: could not extract password from $DB_PHP"
else
    echo "db.php password length   : ${#PASS}"
    echo "db.php password (masked) : ${PASS:0:2}...${PASS: -2}"

    # 1) Length must be 16.
    if [ "${#PASS}" -eq 16 ]; then
        echo "RESULT: pass - length is 16"
    else
        echo "RESULT: FAIL - expected length 16, got ${#PASS}"
    fi

    # 2) Every character must come from the generator's alphabet.
    bad=0
    for (( i=0; i<${#PASS}; i++ )); do
        c="${PASS:$i:1}"
        if [[ "$ALPHABET" != *"$c"* ]]; then
            echo "  RESULT: FAIL - char outside generator alphabet: $c"
            bad=1
        fi
    done
    [ "$bad" = "0" ] && echo "RESULT: pass - all chars are from the generator alphabet"

    # 3) Only chars that truly break the single-quoted PHP/SQL literals must be absent.
    HAZARDS=( $'\\' $'`' $'\x27' )   # backslash, backtick, single quote
    found=0
    for ch in "${HAZARDS[@]}"; do
        if [[ "$PASS" == *"$ch"* ]]; then
            echo "  RESULT: FAIL - password contains a literal-breaking char: $ch"
            found=1
        fi
    done
    [ "$found" = "0" ] && echo "RESULT: pass - no literal-breaking chars (' \\ backtick)"

    # Informational: whether this password happens to contain special chars.
    # Either outcome is acceptable - the quoting makes both safe, and a purely
    # alphanumeric password is valid (~5% probability from the random draw).
    if [[ "$PASS" =~ [^A-Za-z0-9] ]]; then
        echo "INFO: this password contains special char(s) (optional, not required)"
    else
        echo "INFO: this password is alphanumeric-only (valid; quoting still applies)"
    fi
fi

echo
echo "Config DB property (e-smith):"
if [ -x /sbin/e-smith/db ]; then
    /sbin/e-smith/db configuration getprop mailstats DBPass 2>/dev/null \
        | sed 's/\(^.\{2\}\).*\(.\{2\}$\)/\1...\2/' \
        | sed 's/^/  db.php pass /'
else
    echo "  /sbin/e-smith/db not present - skip"
fi

echo
echo "======================================================"
echo " 2) Bug 13827 - CREATE grant + table"
echo "======================================================"
echo "Grants for $DB_USER@localhost:"
mariadb -e "SHOW GRANTS FOR '$DB_USER'@'localhost';" 2>&1 || echo "  (could not query grants)"
echo
echo "Tables in $DB_NAME:"
mariadb -e "SHOW TABLES FROM $DB_NAME;" 2>&1 | sed 's/^/  /'
echo
echo "Functional CREATE test as $DB_USER (expect no 1142):"
if [ -n "$PASS" ]; then
    mariadb -u "$DB_USER" -p"$PASS" "$DB_NAME" \
        -e "CREATE TABLE IF NOT EXISTS _granttest (id INT); DROP TABLE _granttest;" 2>&1 \
        && echo "  RESULT: pass  - CREATE works" \
        || echo "  RESULT: FAIL  - CREATE denied (see error above)"
else
    echo "  skip (no password available)"
fi

if [ "$RUN_JOB" = "1" ]; then
    echo
    echo "======================================================"
    echo " 3) End-to-end nightly job"
    echo "======================================================"
    /usr/bin/runmailstats.sh && echo "runmailstats.sh completed"
    echo "Recent 'create command denied' in journals:"
    journalctl --since today 2>/dev/null | grep -i "create command denied" && echo "  ^ found (BAD)" || echo "  none found (good)"
fi

echo
echo "Done."
