<?php
// Set security headers (must be sent before output)
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

// Helper for safe HTML encoding
function e($s) {
    return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

// Configuration: read DB credentials from environment
$servername = getenv('MAILSTATS_DB_HOST') ?: '';
$username   = getenv('MAILSTATS_DB_USER') ?: '';
$password   = getenv('MAILSTATS_DB_PASS') ?: '';
$dbname     = getenv('MAILSTATS_DB_NAME') ?: '';

// Otherwise try config in /etc/mailstats
if ($username === '' || $password === '' || $dbname === '') {
    $cfgPath = '/etc/mailstats/db.php';
    if (is_readable($cfgPath)) {
		ob_start();
			$cfg = include $cfgPath;
		ob_end_clean();
        $servername = $cfg['host'] ?? $servername ?: 'localhost';
        $username   = $cfg['user'] ?? $username;
        $password   = $cfg['pass'] ?? $password;
        $dbname     = $cfg['name'] ?? $dbname;
    }
}

// Fail fast if credentials are not provided via environment
if ($username === '' || $password === '' || $dbname === '') {
    error_log('Configuration error: DB credentials not set via environment.');
    http_response_code(500);
    exit('Service temporarily unavailable.');
}

// Robust input handling
$defaultDate = date('Y-m-d', strtotime('-1 day'));
$date = isset($_GET['date']) ? $_GET['date'] : $defaultDate;
if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
    http_response_code(400);
    exit('Invalid date');
}

// hour: allow 0–23 or special 99 meaning “all hours”
$hour = isset($_GET['hour']) ? filter_var($_GET['hour'], FILTER_VALIDATE_INT) : 99;
if ($hour === false || ($hour !== 99 && ($hour < 0 || $hour > 23))) {
    http_response_code(400);
    exit('Invalid hour');
}

// Pagination
$page = isset($_GET['page']) ? filter_var($_GET['page'], FILTER_VALIDATE_INT) : 1;
if ($page === false || $page < 1) { $page = 1; }
$pageSize = isset($_GET['page_size']) ? filter_var($_GET['page_size'], FILTER_VALIDATE_INT) : 50;
if ($pageSize === false) { $pageSize = 50; }
// Bound page size to prevent huge result sets
if ($pageSize < 1) { $pageSize = 1; }
if ($pageSize > 100) { $pageSize = 100; }
$limit = $pageSize;
$offset = ($page - 1) * $pageSize;

// Use mysqli with exceptions and UTF-8
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
try {
    $conn = new mysqli($servername, $username, $password, $dbname);
    $conn->set_charset('utf8mb4');
} catch (mysqli_sql_exception $e) {
    error_log('DB connect failed: ' . $e->getMessage());
    http_response_code(500);
    exit('Service temporarily unavailable.');
}

// Build WHERE clause and bind parameters safely
$where = 'Date = ?';
$bindTypesCount = 's';
$bindValuesCount = [$date];

if ($hour !== 99) {
    $where .= ' AND Hour = ?';
    $bindTypesCount .= 'i';
    $bindValuesCount[] = $hour;
}

// Count query for total rows (for display/pagination info)
try {
    $sqlCount = "SELECT COUNT(*) AS total FROM SummaryLogs WHERE $where";
    $stmtCount = $conn->prepare($sqlCount);
    $stmtCount->bind_param($bindTypesCount, ...$bindValuesCount);
    $stmtCount->execute();
    $resultCount = $stmtCount->get_result();
    $rowCount = $resultCount->fetch_assoc();
    $totalRows = (int)$rowCount['total'];
    $stmtCount->close();
} catch (mysqli_sql_exception $e) {
    error_log('Count query failed: ' . $e->getMessage());
    http_response_code(500);
    exit('Service temporarily unavailable.');
}

// Data query with ORDER and LIMIT/OFFSET
try {
    $sql = "SELECT id, logData FROM SummaryLogs WHERE $where ORDER BY id DESC LIMIT ? OFFSET ?";
    // Bind types: existing where types + limit (i) + offset (i)
    $bindTypesData = $bindTypesCount . 'ii';
    $bindValuesData = $bindValuesCount;
    $bindValuesData[] = $limit;
    $bindValuesData[] = $offset;

    $stmt = $conn->prepare($sql);
    $stmt->bind_param($bindTypesData, ...$bindValuesData);
    $stmt->execute();
    $result = $stmt->get_result();
} catch (mysqli_sql_exception $e) {
    error_log('Data query failed: ' . $e->getMessage());
    http_response_code(500);
    exit('Service temporarily unavailable.');
}

function generateLogDataTable($logData) {
    // Defensive decode with substitution for invalid UTF-8
    $data = json_decode($logData, true, 512, JSON_INVALID_UTF8_SUBSTITUTE);

    if (!is_array($data)) {
        return '<em>Invalid JSON data</em>';
    }

    // Remove entries with key 'logterse' and entries with empty values
    foreach ($data as $key => $value) {
        if ($key === 'logterse' || $value === '' || $value === null) {
            unset($data[$key]);
        }
    }

    // Merge adjacent duplicates by value
    $mergedData = [];
    $previousValue = null;
    foreach ($data as $key => $value) {
        // Normalize non-scalar values for display
        if (is_array($value) || is_object($value)) {
            $value = json_encode($value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        }
        $valueStr = (string)$value;

        if ($valueStr === $previousValue) {
            end($mergedData);
            $lastKey = key($mergedData);
            $newKey = $lastKey . '/' . $key;
            $mergedData[$newKey] = $valueStr;
            unset($mergedData[$lastKey]);
        } else {
            $mergedData[$key] = $valueStr;
        }
        $previousValue = $valueStr;
    }

    // Optional truncation to keep rendering safe
    $maxValueLen = 500;
    foreach ($mergedData as $k => $v) {
        if (mb_strlen($v, 'UTF-8') > $maxValueLen) {
            $mergedData[$k] = mb_substr($v, 0, $maxValueLen, 'UTF-8') . '…';
        }
    }

    $keys = array_keys($mergedData);
    $values = array_values($mergedData);

	$output = '<table class="mailstats-summary stripes"><tbody>';

    // Divide keys and values into sets of 6
    $chunks = array_chunk($keys, 6);
    foreach ($chunks as $chunkIndex => $chunk) {
        $output .= '<tr>';
        foreach ($chunk as $key) {
            $output .= '<th>' . e($key) . '</th>';
        }
        $output .= '</tr><tr>';
        foreach ($chunk as $i => $key) {
            $val = $values[$chunkIndex * 6 + $i];
            $output .= '<td>' . e($val) . '</td>';
        }
        $output .= '</tr>';
    }

    $output .= '</tbody></table>';
    return $output;
}

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Summary Logs</title>
    <link rel="stylesheet" type="text/css" href="css/mailstats.css" />
    <link rel="icon" type="image/x-icon" href="favicon.ico">
</head>
<body>
    <div class="mailstats-summary">
        <div class="summary-container">
            <h1>
                Summary Logs for Date: <?= e($date) ?>
                <?= $hour === 99 ? ' (All Hours)' : ' at Hour: ' . e($hour) ?>
            </h1>
            <?php
                $startRow = $totalRows > 0 ? ($offset + 1) : 0;
                $endRow = min($offset + $limit, $totalRows);
            ?>
            <h3>Found <?= e($totalRows) ?> records. Showing <?= e($startRow) ?>–<?= e($endRow) ?>.</h3>
            
            <table class="summary-table">
                <thead>
                    <tr>
                        <th>Id</th>
                        <th>Details</th>
                        <th>Log Data</th>
                    </tr>
                </thead>
                <tbody>
                    <?php if ($result && $result->num_rows > 0): ?>
                        <?php while ($row = $result->fetch_assoc()): ?>
                            <?php
                                $id = (int)$row['id'];
                                $detailUrl = './ShowDetailedLogs.php?id=' . rawurlencode((string)$id);
                            ?>
                            <tr>
                                <td><?= e($id) ?></td>
                                <td><a href="<?= e($detailUrl) ?>">View details</a></td>
                                <td><?= generateLogDataTable($row['logData']) ?></td>
                            </tr>
                        <?php endwhile; ?>
                    <?php else: ?>
                        <tr>
                            <td colspan="3">No records found for the specified date and hour.</td>
                        </tr>
                    <?php endif; ?>
                </tbody>
            </table>

            <?php
                // Pagination
                $baseParams = [
                    'date' => $date,
                    'hour' => $hour,
                    'page_size' => $pageSize
                ];
                $prevPage = $page > 1 ? $page - 1 : null;
                $nextPage = ($offset + $limit) < $totalRows ? $page + 1 : null;
            ?>
            <div class="pagination">
                <?php if ($prevPage !== null): ?>
                    <?php
                        $paramsPrev = $baseParams; $paramsPrev['page'] = $prevPage;
                        $urlPrev = '?' . http_build_query($paramsPrev, '', '&', PHP_QUERY_RFC3986);
                    ?>
                    <a href="<?= e($urlPrev) ?>">&laquo; Previous</a>
                <?php endif; ?>
                <?php if ($nextPage !== null): ?>
                    <?php
                        $paramsNext = $baseParams; $paramsNext['page'] = $nextPage;
                        $urlNext = '?' . http_build_query($paramsNext, '', '&', PHP_QUERY_RFC3986);
                    ?>
                    <?php if ($prevPage !== null): ?> | <?php endif; ?>
                    <a href="<?= e($urlNext) ?>">Next &raquo;</a>
                <?php endif; ?>
            </div>
        </div>
    </div>

    <?php
        if (isset($stmt) && $stmt instanceof mysqli_stmt) { $stmt->close(); }
        if (isset($conn) && $conn instanceof mysqli) { $conn->close(); }
    ?>
</body>
</html>