"""
One-time setup script to upload the Gmail token to Secret Manager.
Run this once before deploying the Cloud Function.
"""
import json
import os

PROJECT_ID = "super-home-automation"
SECRET_ID = "gmail-oauth-token"

def setup_secret():
    from google.cloud import secretmanager
    
    token_path = "token.json"
    if not os.path.exists(token_path):
        print(f"Error: {token_path} not found.")
        return False
    
    with open(token_path, 'r') as f:
        token_content = f.read().strip()
    
    # Validate JSON
    try:
        json.loads(token_content)
    except json.JSONDecodeError:
        print("Error: token.json is not valid JSON.")
        return False
    
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{PROJECT_ID}"
    
    # Try to create the secret (will fail if it already exists, which is fine)
    try:
        client.create_secret(
            request={
                "parent": parent,
                "secret_id": SECRET_ID,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        print(f"Created secret: {SECRET_ID}")
    except Exception as e:
        if "ALREADY_EXISTS" in str(e):
            print(f"Secret '{SECRET_ID}' already exists. Adding new version...")
        else:
            print(f"Error creating secret: {e}")
            return False
    
    # Add the token as a new version
    secret_name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}"
    payload = token_content.encode("UTF-8")
    
    response = client.add_secret_version(
        request={"parent": secret_name, "payload": {"data": payload}}
    )
    print(f"Added secret version: {response.name}")
    print("Setup complete! You can now deploy the Cloud Function.")
    return True

if __name__ == "__main__":
    # First, refresh the token if needed
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.modify' 
        ]
        
        print("Checking local token...")
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        if creds.expired and creds.refresh_token:
            print("Token expired. Refreshing...")
            creds.refresh(Request())
            with open("token.json", 'w') as f:
                f.write(creds.to_json())
            print(f"Token refreshed. New expiry: {creds.expiry}")
        else:
            print(f"Token is valid. Expiry: {creds.expiry}")
            
    except Exception as e:
        print(f"Warning: Could not refresh token: {e}")
    
    setup_secret()
