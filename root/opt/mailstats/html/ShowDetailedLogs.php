<?php
header('Content-Type: text/plain');

$input_param = isset($_GET['id']) ? $_GET['id'] : '9999';

// Set the directory and file names
$directory = "/opt/mailstats/logs";
$files = ['current1', 'current2'];

function process_file($file_path, $input_param) {
    $file = fopen($file_path, 'r');
    $match = "/ $input_param /";
    $endmatch = "/cleaning up after $input_param/";
    while (($line = fgets($file)) !== false) {
        // Check if the line contains the input_parameter
        if (preg_match($match,$line) === 1) {
            echo $line;
        } elseif (preg_match($endmatch,$line) === 1) {
            echo $line;
            exit();
        }
    }
    fclose($file);
}

function tai64nToDate($tai64n) {
    // Check if the input TAI64N string is valid
    if (preg_match('/^@([0-9a-f]{8})([0-9a-f]{8})$/', $tai64n, $matches)) {
        // First part: seconds since epoch
        $sec_hex = $matches[1];
        // Second part: nanoseconds in hex
        $nsec_hex = $matches[2];

        // Convert hex to decimal
        $seconds = hexdec($sec_hex);
        $nanoseconds = hexdec($nsec_hex);
        
        // Calculate the full timestamp in seconds
        $timestamp = $seconds + ($nanoseconds / 1e9);  // Nanoseconds to seconds
        
        // Format timestamp to 'Y-m-d H:i:s'
        return date('Y-m-d H:i:s', $timestamp);
    } else {
        throw new InvalidArgumentException("Invalid TAI64N format.");
    }
}
chdir($directory);
foreach ($files as $file) {
    process_file($file, $input_param);
}
?>
