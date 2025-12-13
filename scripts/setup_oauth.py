import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Scopes required for the bot
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify'
]

def setup_oauth():
    """
    Runs the OAuth flow to generate token.json.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    if not creds or not creds.valid:
        if not os.path.exists('credentials.json'):
            print("Error: 'credentials.json' not found.")
            print("Please download your OAuth Client ID JSON from GCP Console,")
            print("rename it to 'credentials.json', and place it in this folder.")
            return

        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0, prompt='consent', access_type='offline', authorization_prompt_message="")
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
        print("\nSuccess! 'token.json' has been created.")
        print("You can now use this token to authenticate your Cloud Function.")
        print("Content of token.json (keep this safe!):")
        print(creds.to_json())

if __name__ == '__main__':
    setup_oauth()
