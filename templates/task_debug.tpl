<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Page</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        .task-list {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <h1>Debug information</h1>
    <body>
    <pre>
    Protocol-version: $protocol
    URL: $url
    Server: $server
    Request_Path: $request_path
    </pre>
    <br>
    $request_data
    <p>
    $task_data
    <p>
    $config_data
    </body>
</body>
</html>