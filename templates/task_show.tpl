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
    <h1>$title</h1>
    <body>
        <b>Wann solltest Du Diese Aufgabe am besten beginnen:</b>
        <br>
        $when
        <p>
        <b>Dies sind die Schritte, um diese Aufgabe zu erledigen:</b>
        <br>
        $description
    <p>
    <b>Was willst du jetzt machen?</b>
    <br>
    Willst Du diese Aufgabe sp&auml;ter angehen, dann schließe einfach den Tab und scanne den QR code zu einem sp&auml;teren Zeitpunkt noch einmal.
    <p>
    Hast Du diese Aufgabe gerade erledigt, clicke <a href="do?id=$index&token=$token">hier</a>.
    <p>
    Willst Du diese Aufgabe nicht erledigen und einen Deiner Joker einsetzen, klicke <a href="veto?id=$index&token=$token">hier</a>.
    <br>
    Im Moment hast Du $used_vetoes Joker eingesetzt und kannst $remaining_vetoes Joker nutzen.
    </body>
</body>
</html>