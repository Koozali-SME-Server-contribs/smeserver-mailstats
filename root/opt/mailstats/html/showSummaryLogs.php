<?php
// Database configuration
$servername = "localhost";
$username = "mailstats";
$password = "mailstats";
$dbname = "mailstats";

// Default date to yesterday
$date = isset($_GET['date']) ? $_GET['date'] : date('Y-m-d', strtotime('-1 day'));

// Default hour to 99 (means all the hours)
$hour = isset($_GET['hour']) ? $_GET['hour'] : 99;

// Create connection
$conn = new mysqli($servername, $username, $password, $dbname);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// Prepare and execute the query
if ($hour == 99){
	$sql = "SELECT * FROM SummaryLogs WHERE Date = ?";
	$stmt = $conn->prepare($sql);
	$stmt->bind_param("s", $date);
} else {
	$sql = "SELECT * FROM SummaryLogs WHERE Date = ? AND Hour = ?";
	$stmt = $conn->prepare($sql);
	$stmt->bind_param("si", $date, $hour);
}
$stmt->execute();
$result = $stmt->get_result();

function generateLogDataTable($logData) {
    $data = json_decode($logData, true);
    if (is_null($data)) {
        return "Invalid JSON data";
    }
    
    $keys = array_keys($data);
    $values = array_values($data);
    
    $output = '<table border="1" style="border-collapse: collapse; width: 41%;overflow-x:auto;font-size:1cqw"><tbody>';

    // Divide keys and values into sets of 6
    $chunks = array_chunk($keys, 7);
    foreach ($chunks as $chunkIndex => $chunk) {
        if ($chunkIndex > 0) {
            // Add spacing between different sets
            #$output .= '<tr><td colspan="6" style="height: 1em;"></td></tr>';
        }
        
        $output .= '<tr>';
        foreach ($chunk as $key) {
            $output .= '<th>' . htmlspecialchars($key) . '</th>';
        }
        $output .= '</tr><tr>';
        foreach ($chunk as $i => $key) {
            $output .= '<td>' . htmlspecialchars($values[$chunkIndex * 7 + $i]) . '</td>';
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
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        table, th, td {
            border: 1px solid black;
        }
        th, td {
            padding: 8px;
            text-align: left;
        }
    </style>
</head>
<body>
    <h1>Summary Logs for Date: <?= htmlspecialchars($date) ?> <?= $hour == 99 ? 'for All Hours' : 'and Hour: ' . htmlspecialchars($hour) ?></h1>
    <table>
        <thead>
            <tr>
                <th>Id</th>
                <!--<th>Date</th>-->
                <!--<th>Hour</th>-->
                <th>Log Data</th>
            </tr>
        </thead>
        <tbody>
            <?php if ($result->num_rows > 0): ?>
                <?php while($row = $result->fetch_assoc()): ?>
                    <tr>
                        <td><?= htmlspecialchars($row['id']) ?></td>
                        <td><?= generateLogDataTable($row['logData']) ?></td>
                    </tr>
                <?php endwhile; ?>
            <?php else: ?>
                <tr>
                    <td colspan="4">No records found for the specified date and hour.</td>
                </tr>
            <?php endif; ?>
        </tbody>
    </table>
    <?php
    // Close the connection
    $stmt->close();
    $conn->close();
    ?>
</body>
</html>
