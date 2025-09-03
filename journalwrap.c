#include <systemd/sd-journal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <errno.h>
#include <time.h>

#ifndef MAX_OUTPUT_BYTES
#define MAX_OUTPUT_BYTES (2 * 1000 * 1000) // 2 MB
#endif

static int append_bytes(char **buf, size_t *len, size_t *cap, const char *src, size_t n) {
    if (*len + n + 1 > *cap) {
        size_t newcap = (*cap == 0) ? 8192 : *cap;
        while (*len + n + 1 > newcap) {
            newcap *= 2;
            if (newcap > (size_t)(MAX_OUTPUT_BYTES + 65536)) {
                newcap = (size_t)(MAX_OUTPUT_BYTES + 65536);
                break;
            }
        }
        char *nbuf = realloc(*buf, newcap);
        if (!nbuf) return -1;
        *buf = nbuf; *cap = newcap;
    }
    memcpy(*buf + *len, src, n);
    *len += n;
    (*buf)[*len] = '\0';
    return 0;
}

static int append_cstr(char **buf, size_t *len, size_t *cap, const char *s) {
    return append_bytes(buf, len, cap, s, strlen(s));
}

static size_t min_size(size_t a, size_t b) { return a < b ? a : b; }

static void sanitize_text(char *s, size_t n) {
    for (size_t i = 0; i < n; i++) if (s[i] == '\0') s[i] = ' ';
}

static void format_ts(char *out, size_t outsz, uint64_t usec) {
    time_t sec = (time_t)(usec / 1000000ULL);
    struct tm tm;
    localtime_r(&sec, &tm);
    strftime(out, outsz, "%Y-%m-%d %H:%M:%S", &tm);
}

static const char* field_value(const void *data, size_t len, const char *key, size_t *vlen) {
    size_t klen = strlen(key);
    if (len < klen + 1) return NULL;
    const char *p = (const char *)data;
    if (memcmp(p, key, klen) != 0 || p[klen] != '=') return NULL;
    *vlen = len - (klen + 1);
    return p + klen + 1;
}

static int append_entry_line(sd_journal *j, char **buf, size_t *len, size_t *cap) {
    uint64_t usec = 0;
    (void)sd_journal_get_realtime_usec(j, &usec);
    char ts[32];
    format_ts(ts, sizeof(ts), usec);

    const void *data = NULL;
    size_t dlen = 0;
    const char *message = NULL;
    size_t mlen = 0;

    int r = sd_journal_get_data(j, "MESSAGE", &data, &dlen);
    if (r >= 0) message = field_value(data, dlen, "MESSAGE", &mlen);

    const char *ident = NULL;
    size_t ilen = 0;
    r = sd_journal_get_data(j, "SYSLOG_IDENTIFIER", &data, &dlen);
    if (r >= 0) {
        ident = field_value(data, dlen, "SYSLOG_IDENTIFIER", &ilen);
    } else if (sd_journal_get_data(j, "_COMM", &data, &dlen) >= 0) {
        ident = field_value(data, dlen, "_COMM", &ilen);
    }

    if (append_cstr(buf, len, cap, "[") < 0) return -1;
    if (append_cstr(buf, len, cap, ts) < 0) return -1;
    if (append_cstr(buf, len, cap, "] ") < 0) return -1;
    if (ident && ilen > 0) {
        if (append_bytes(buf, len, cap, ident, ilen) < 0) return -1;
        if (append_cstr(buf, len, cap, ": ") < 0) return -1;
    }

    if (message && mlen > 0) {
        char *tmp = malloc(mlen);
        if (!tmp) return -1;
        memcpy(tmp, message, mlen);
        sanitize_text(tmp, mlen);
        size_t to_copy = min_size(mlen, (size_t)(MAX_OUTPUT_BYTES > *len ? MAX_OUTPUT_BYTES - *len : 0));
        int ok = append_bytes(buf, len, cap, tmp, to_copy);
        free(tmp);
        if (ok < 0) return -1;
    } else {
        const char *keys[] = {"PRIORITY","SYSLOG_IDENTIFIER","_COMM","_EXE","_CMDLINE","MESSAGE"};
        for (size_t i = 0; i < sizeof(keys)/sizeof(keys[0]); i++) {
            if (sd_journal_get_data(j, keys[i], &data, &dlen) < 0) continue;
            if (append_cstr(buf, len, cap, (i == 0 ? "" : " ")) < 0) return -1;
            if (append_bytes(buf, len, cap, (const char*)data, min_size(dlen, (size_t)(MAX_OUTPUT_BYTES - *len))) < 0) return -1;
        }
    }

    if (*len < MAX_OUTPUT_BYTES) {
        if (append_cstr(buf, len, cap, "\n") < 0) return -1;
    }
    return 0;
}

static char* journal_get_by_pid_impl(int pid) {
    if (pid <= 0) { char *z = malloc(1); if (z) z[0] = '\0'; return z; }

    sd_journal *j = NULL;
    if (sd_journal_open(&j, SD_JOURNAL_LOCAL_ONLY) < 0) {
        char *z = malloc(1); if (z) z[0] = '\0'; return z;
    }

    char match[64];
    snprintf(match, sizeof(match), "_PID=%d", pid);
    if (sd_journal_add_match(j, match, 0) < 0) {
        sd_journal_close(j);
        char *z = malloc(1); if (z) z[0] = '\0'; return z;
    }

    sd_journal_seek_head(j);

    char *buf = NULL; size_t len = 0, cap = 0;
    int r;
    while ((r = sd_journal_next(j)) > 0) {
        if (len >= MAX_OUTPUT_BYTES) break;
        if (append_entry_line(j, &buf, &len, &cap) < 0) {
            free(buf); sd_journal_close(j); return NULL;
        }
    }

    if (len >= MAX_OUTPUT_BYTES) {
        const char *trunc = "[output truncated]\n";
        (void)append_bytes(&buf, &len, &cap, trunc, strlen(trunc));
    }

    if (!buf) { buf = malloc(1); if (!buf) { sd_journal_close(j); return NULL; } buf[0] = '\0'; }
    sd_journal_close(j);
    return buf;
}

#ifdef __GNUC__
__attribute__((visibility("default")))
#endif
char* journal_get_by_pid(int pid) { return journal_get_by_pid_impl(pid); }

#ifdef __GNUC__
__attribute__((visibility("default")))
#endif
void journal_free(char* p) { free(p); }

#ifdef BUILD_CLI
static int parse_pid(const char *s, int *out) {
    if (!s || !*s) return -1;
    char *end = NULL;
    errno = 0;
    long v = strtol(s, &end, 10);
    if (errno != 0 || end == s || *end != '\0' || v <= 0 || v > 0x7fffffffL) return -1;
    *out = (int)v; return 0;
}
int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "Usage: %s <pid>\n", argv[0]); return 2; }
    int pid = 0;
    if (parse_pid(argv[1], &pid) != 0) { fprintf(stderr, "Invalid pid\n"); return 2; }
    char *out = journal_get_by_pid_impl(pid);
    if (!out) { fprintf(stderr, "Out of memory or error\n"); return 1; }
    fputs(out, stdout);
    free(out);
    return 0;
}
#endif
