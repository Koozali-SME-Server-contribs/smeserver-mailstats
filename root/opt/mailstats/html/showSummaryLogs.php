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
$result_count = $result->num_rows;

function generateLogDataTable($logData) {
    $data = json_decode($logData, true);
    if (is_null($data)) {
        return "Invalid JSON data";
    }
    
    //// Remove entries with the key "logterse"
    //if (isset($data['logterse'])) {
        //unset($data['logterse']);
    //}

    // Remove entries with the key "logterse" and remove entries with empty values
    foreach ($data as $key => $value) {
        if ($key === 'logterse' || empty($value)) {
            unset($data[$key]);
        }
    }

    // Handle adjacent duplicates by merging keys
    $mergedData = [];
    $previousValue = null;
    foreach ($data as $key => $value) {
        if ($value === $previousValue) {
            // Merge the current key with the previous key
            end($mergedData);
            $lastKey = key($mergedData);
            $newKey = "$lastKey/$key";
            $mergedData[$newKey] = $value;
            // Remove the old entry
            unset($mergedData[$lastKey]);
        } else {
            // Otherwise, add a new entry
            $mergedData[$key] = $value;
        }
        $previousValue = $value;
    }

        
    $keys = array_keys($mergedData);
    $values = array_values($mergedData);
    
    $output = '<table class="stripes" style="border-collapse: collapse; width:95%;overflow-x:auto; margin: 0.6% auto 0.6% auto;"><tbody>';
    #$output = '<table class="stripes" style="border-collapse: collapse; width:95%;overflow-x:auto; margin:2%"><tbody>';

    // Divide keys and values into sets of 6
    $chunks = array_chunk($keys, 6);
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
			$val = htmlspecialchars($values[$chunkIndex * 6+ $i]);
			if ($key == 'id'){
				$output .= '<td>' . "<a href='./ShowDetailedLogs.php?id=".$val."'</a>".$val."</td>";
			} else {
				$output .= '<td>' . $val . '</td>';
			}
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
   	<link rel='stylesheet' type='text/css' href='css/mailstats.css' />
    <title>Summary Logs</title>
<!--    <style>
        table {
            xxwidth: 100%;
            xxborder-collapse: collapse;
        }
        table, th, td {
            xxborder: 1px solid black;
        }
        th, td {
            xxpadding: 8px;
            xxtext-align: left;
        }
    </style>
-->
</head>
<body>
	<div style="width:100%;overflow-x:auto;font-size:0.726cqw">"
    <h1>Summary Logs for Date: <?= htmlspecialchars($date) ?> <?= $hour == 99 ? 'for All Hours' : 'and Hour: ' . htmlspecialchars($hour) ?></h1>
    <h3>Found <?= $result_count ?> records.</h3>
    <table style="border-collapse:collapse;width:98%">
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
    </div>
    <?php
    // Close the connection
    $stmt->close();
    $conn->close();
    ?>
</body>
</html>
