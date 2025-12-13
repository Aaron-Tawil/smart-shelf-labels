import os
import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.message import EmailMessage
from io import BytesIO

# Scopes required for the bot
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify' # To remove UNREAD label
]

def get_gmail_service(token_json_path=None, token_info=None):
    """
    Returns an authenticated Gmail service object.
    Can use a local token.json file or a dictionary of token info (for Cloud Function).
    """
    creds = None
    
    if token_info:
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    elif token_json_path and os.path.exists(token_json_path):
        creds = Credentials.from_authorized_user_file(token_json_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("No valid credentials found. Run setup_oauth.py locally first.")

    return build('gmail', 'v1', credentials=creds)

def get_message_content(service, user_id, msg_id):
    """Retrieves the full message content."""
    return service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()

def get_attachment_data(service, user_id, msg_id, attachment_id):
    """Retrieves attachment data."""
    attachment = service.users().messages().attachments().get(
        userId=user_id, messageId=msg_id, id=attachment_id
    ).execute()
    data = base64.urlsafe_b64decode(attachment['data'])
    return data

def create_message_with_multiple_attachments(sender, to, subject, body, attachments):
    """
    Creates an EmailMessage object with multiple attachments and encodes it for Gmail API.
    `attachments` should be a list of dicts, e.g., [{'filename': 'file1.pdf', 'data': b'...'}]
    """
    message = EmailMessage()
    message.set_content(body)
    message['To'] = to
    message['From'] = sender
    message['Subject'] = subject

    if attachments:
        for attachment in attachments:
            attachment_bytes = attachment.get('data')
            filename = attachment.get('filename')
            if attachment_bytes and filename:
                message.add_attachment(
                    attachment_bytes,
                    maintype='application',
                    subtype='pdf', # Assuming all attachments are PDFs
                    filename=filename
                )

    # Encode the message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': encoded_message}

def create_message_with_attachment(sender, to, subject, body, attachment_bytes, filename):
    """
    Creates an EmailMessage object and encodes it for Gmail API.
    This is now a wrapper around create_message_with_multiple_attachments.
    """
    attachments = []
    if attachment_bytes and filename:
        attachments.append({'filename': filename, 'data': attachment_bytes})
    
    return create_message_with_multiple_attachments(sender, to, subject, body, attachments)

def send_message(service, user_id, message):
    """Sends the message."""
    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                   .execute())
        print(f"Message Id: {message['id']}")
        return message
    except Exception as error:
        print(f"An error occurred: {error}")
        return None

def mark_as_read(service, user_id, msg_id):
    """Removes the UNREAD label."""
    service.users().messages().modify(
        userId=user_id,
        id=msg_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()
