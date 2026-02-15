"""
We send mails to notify a user about tasks being found, shown, done, or vetoed.
"""

from email.message import EmailMessage
from smtplib import SMTP
from config import read_config


def send_notification_email(user_email, subject, body):
    """
    Sends a notification email to the specified user.

    :param user_email: The email address of the user to notify.
    :param subject: The subject of the email.
    :param body: The body content of the email.
    :param smtp_server: The SMTP server to use for sending the email.
    :param smtp_port: The port of the SMTP server.
    """
    config = read_config()
    msg = EmailMessage()
    server = SMTP(config["email"]["smtp_server"], config["email"]["smtp_port"])
    server.starttls()
    server.login(config["email"]["smtp_username"], config["email"]["smtp_password"])
    msg["From"] = config["email"]["from_address"]
    msg["To"] = user_email
    msg["Subject"] = subject
    msg.set_content(body)
    print(f"Sending email to {user_email} with subject '{subject}'")
    server.send_message(msg)
    server.quit()
