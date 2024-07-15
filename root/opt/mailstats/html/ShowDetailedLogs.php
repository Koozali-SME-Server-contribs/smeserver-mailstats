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
chdir($directory);
foreach ($files as $file) {
    process_file($file, $input_param);
}
?>
