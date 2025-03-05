from itsdangerous import URLSafeTimedSerializer
from flask import current_app
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
        return email
    except:
        return False

def send_confirmation_email(email, confirmation_url):
    # Email settings
    sender_email = os.getenv('MAIL_USERNAME')
    sender_password = os.getenv('MAIL_PASSWORD')

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Confirm Your VideoVault Account"
    msg['From'] = sender_email
    msg['To'] = email

    # Create HTML version of the email
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2563EB; margin-bottom: 20px;">Welcome to VideoVault!</h1>

            <p>Thank you for registering with VideoVault. To complete your registration and access all features, please confirm your email address by clicking the button below:</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{confirmation_url}" style="background-color: #2563EB; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">Confirm Email Address</a>
            </div>

            <p>Or copy and paste this link into your browser:</p>
            <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px;">{confirmation_url}</p>

            <p>This link will expire in 1 hour for security reasons.</p>

            <p>If you did not create an account with VideoVault, please ignore this email.</p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                <p style="color: #666; font-size: 12px;">
                    © 2024 VideoVault. All rights reserved.<br>
                    This is an automated message, please do not reply.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    # Create plain text version of the email
    text = f"""
    Welcome to VideoVault!

    Thank you for registering with VideoVault. To complete your registration and access all features, please confirm your email address by clicking the link below:

    {confirmation_url}

    This link will expire in 1 hour for security reasons.

    If you did not create an account with VideoVault, please ignore this email.

    © 2024 VideoVault. All rights reserved.
    This is an automated message, please do not reply.
    """

    # Attach parts
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)

    # Send email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, msg.as_string())
        return True
    except Exception as e:
        # # # # # # print(f"Error sending email: {str(e)}")
