import os
import base64
import json
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

# Secret Manager Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "super-home-automation")
SECRET_ID = os.environ.get("GCP_SECRET_ID", "gmail-oauth-token")

def load_token_from_secret():
    """Load the Gmail token from Google Cloud Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        token_json = response.payload.data.decode("UTF-8")
        print(f"Loaded token from Secret Manager (expiry: {json.loads(token_json).get('expiry', 'unknown')})")
        return json.loads(token_json)
    except json.JSONDecodeError as e:
        print(f"Error decoding token from Secret Manager: {e}")
        # Log a snippet relative safely
        snippet = token_json[:50] if 'token_json' in locals() and token_json else "Empty or None"
        print(f"Snippet of invalid token data: {snippet}...")
        return None
    except Exception as e:
        print(f"Error loading token from Secret Manager: {e}")
        return None

def save_token_to_secret(token_info):
    """Save the Gmail token to Google Cloud Secret Manager as a new version."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}"
        payload = json.dumps(token_info).encode("UTF-8")
        response = client.add_secret_version(
            request={"parent": parent, "payload": {"data": payload}}
        )
        print(f"Saved refreshed token to Secret Manager: {response.name}")
        return True
    except Exception as e:
        print(f"Error saving token to Secret Manager: {e}")
        return False

def get_gmail_service(token_json_path=None, token_info=None, use_secret_manager=False):
    """
    Returns an authenticated Gmail service object.
    Can use a local token.json file, a dictionary of token info, or Secret Manager.
    If token is refreshed and use_secret_manager is True, persists the new token.
    """
    creds = None
    
    # Try Secret Manager first if enabled
    if use_secret_manager:
        token_info = load_token_from_secret()
        if not token_info:
            raise Exception("Could not load token from Secret Manager")
    
    if token_info:
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    elif token_json_path and os.path.exists(token_json_path):
        creds = Credentials.from_authorized_user_file(token_json_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired, refreshing...")
            creds.refresh(Request())
            print(f"Token refreshed. New expiry: {creds.expiry}")
            
            # Persist refreshed token to Secret Manager
            if use_secret_manager:
                new_token_info = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": list(creds.scopes),
                    "expiry": creds.expiry.isoformat() + "Z" if creds.expiry else None,
                }
                save_token_to_secret(new_token_info)
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
