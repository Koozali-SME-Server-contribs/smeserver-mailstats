<?php
// Security headers
header('Content-Type: text/html; charset=UTF-8');
header("Content-Security-Policy: default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; object-src 'none'; frame-ancestors 'none'");
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('Permissions-Policy: geolocation=(), microphone=(), camera=()');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') {
    header('Strict-Transport-Security: max-age=31536000; includeSubDomains');
}

function e($s) {
    return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

// Configuration: env first, then fallback to optional file
$servername = getenv('MAILSTATS_DB_HOST') ?: 'localhost';
$username   = getenv('MAILSTATS_DB_USER') ?: '';
$password   = getenv('MAILSTATS_DB_PASS') ?: '';
$dbname     = getenv('MAILSTATS_DB_NAME') ?: '';

if ($username === '' || $password === '' || $dbname === '') {
    $cfgPath = '/etc/mailstats/db.php'; // optional fallback config file
    if (is_readable($cfgPath)) {
		ob_start();
			$cfg = include $cfgPath;
		ob_end_clean();
        $servername = $cfg['host'] ?? $servername;
        $username   = $cfg['user'] ?? $username;
        $password   = $cfg['pass'] ?? $password;
        $dbname     = $cfg['name'] ?? $dbname;
    }
}

if ($username === '' || $password === '' || $dbname === '') {
    error_log('DB credentials missing (env and config file).');
    http_response_code(500);
    exit('Service temporarily unavailable.');
}

// Input validation: id
$id = isset($_GET['id']) ? filter_var($_GET['id'], FILTER_VALIDATE_INT) : null;
if ($id === false || $id === null || $id < 1) {
    http_response_code(400);
    exit('Invalid id');
}

// DB connect with exceptions
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
try {
    $conn = new mysqli($servername, $username, $password, $dbname);
    $conn->set_charset('utf8mb4');
} catch (mysqli_sql_exception $e) {
    error_log('DB connect failed: ' . $e->getMessage());
    http_response_code(500);
    exit('Service temporarily unavailable.');
}

// Fetch the record and extract PID from JSON logData
try {
    $stmt = $conn->prepare('SELECT id, logData FROM SummaryLogs WHERE id = ?');
    $stmt->bind_param('i', $id);
    $stmt->execute();
    $res = $stmt->get_result();
    $row = $res->fetch_assoc();
    $stmt->close();
} catch (mysqli_sql_exception $e) {
    error_log('Query failed: ' . $e->getMessage());
    http_response_code(500);
    exit('Service temporarily unavailable.');
}

if (!$row) {
    http_response_code(404);
    exit('Record not found');
}

$logData = $row['logData'];
$pid = null;
$data = json_decode($logData, true, 512, JSON_INVALID_UTF8_SUBSTITUTE);
if (is_array($data)) {
    foreach (['id','pid', 'PID', 'Pid', 'process_id', 'ProcessId'] as $k) {
        if (isset($data[$k]) && (is_int($data[$k]) || ctype_digit((string)$data[$k]))) {
            $pid = (int)$data[$k];
            break;
        }
    }
}

if (!$pid || $pid < 1) {
    http_response_code(422);
    exit('PID not found in this record');
}

// Journal retrieval using C wrapper
define('FFI_LIB', 'libjournalwrap.so');         // adjust if needed
define('WRAPPER_BIN', '/usr/bin/journalwrap'); // fallback executable path
define('MAX_OUTPUT_BYTES', 2_000_000); // 2MB safety cap

function getJournalByPidViaFFI(int $pid): ?string {
    if (!extension_loaded('FFI')) {
        return null;
    }
    try {
        // Adjust the function signatures to match your wrapper
        $ffi = FFI::cdef("
            char* journal_get_by_pid(int pid);
            void journal_free(char* p);
        ", FFI_LIB);
        $cstr = $ffi->journal_get_by_pid($pid);
        if ($cstr === null) {
            return '';
        }
        $out = FFI::string($cstr);
        $ffi->journal_free($cstr);
        return $out;
    } catch (Throwable $e) {
        error_log('FFI journal wrapper failed: ' . $e->getMessage());
        return null;
    }
}

function getJournalByPidViaExec(int $pid): ?string {
    // Fallback to an external wrapper binary (must be safe and not use shell)
    $cmd = WRAPPER_BIN . ' ' . (string)$pid;

    $descriptorspec = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];
    $pipes = [];
    $proc = proc_open($cmd, $descriptorspec, $pipes, null, null, ['bypass_shell' => true]);

    if (!\is_resource($proc)) {
        error_log('Failed to start journal wrapper binary');
        return null;
    }

    fclose($pipes[0]); // no stdin

    stream_set_blocking($pipes[1], false);
    stream_set_blocking($pipes[2], false);

    $stdout = '';
    $stderr = '';
    $start = microtime(true);
    $timeout = 10.0; // seconds
    $readChunk = 65536;

    while (true) {
        $status = proc_get_status($proc);
        $running = $status['running'];

        $read = [$pipes[1], $pipes[2]];
        $write = null;
        $except = null;
        $tv_sec = 0;
        $tv_usec = 300000; // 300ms
        stream_select($read, $write, $except, $tv_sec, $tv_usec);

        foreach ($read as $r) {
            if ($r === $pipes[1]) {
                $chunk = fread($pipes[1], $readChunk);
                if ($chunk !== false && $chunk !== '') {
                    $stdout .= $chunk;
                }
            } elseif ($r === $pipes[2]) {
                $chunk = fread($pipes[2], $readChunk);
                if ($chunk !== false && $chunk !== '') {
                    $stderr .= $chunk;
                }
            }
        }

        if (!$running) {
            break;
        }

        if ((microtime(true) - $start) > $timeout) {
            proc_terminate($proc);
            $stderr .= "\n[terminated due to timeout]";
            break;
        }

        if (strlen($stdout) + strlen($stderr) > MAX_OUTPUT_BYTES) {
            proc_terminate($proc);
            $stderr .= "\n[terminated due to output size limit]";
            break;
        }
    }

    foreach ($pipes as $p) {
        if (is_resource($p)) {
            fclose($p);
        }
    }
    $exitCode = proc_close($proc);

    if ($exitCode !== 0 && $stderr !== '') {
        error_log('journal wrapper stderr: ' . $stderr);
    }

    return $stdout;
}

$logs = getJournalByPidViaFFI($pid);
if ($logs === null) {
    $logs = getJournalByPidViaExec($pid);
}
if ($logs === null) {
    http_response_code(500);
    exit('Unable to read journal for this PID');
}

// Safety cap to avoid rendering gigantic outputs
if (strlen($logs) > MAX_OUTPUT_BYTES) {
    $logs = substr($logs, 0, MAX_OUTPUT_BYTES) . "\n[output truncated]";
}

// Done with DB
$conn->close();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Log details for PID <?= e($pid) ?> (record <?= e($id) ?>)</title>
    <link rel="stylesheet" type="text/css" href="css/mailstats.css" />
    <link rel="icon" type="image/x-icon" href="favicon.ico">

</head>
<body>
    <div class="mailstats-detail">
        <div class="detail-container">
            <h1>Log details for PID <?= e($pid) ?> (record <?= e($id) ?>)</h1>
            <p><a href="javascript:history.back()">Back</a></p>
            <pre class="log"><?= e($logs) ?></pre>
        </div>
    </div>
</body>
</html>