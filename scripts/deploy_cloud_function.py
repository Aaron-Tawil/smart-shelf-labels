import subprocess
import json
import os
import sys


def deploy():
    # Path to token.json
    token_path = "token.json"
    
    if not os.path.exists(token_path):
        print(f"Error: {token_path} not found.")
        return

    # --- AUTO-REFRESH LOGIC START ---
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.modify' 
        ]
        
        print(f"Checking credentials in {token_path}...")
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        if creds.expired and creds.refresh_token:
            print("Credentials expired. Refreshing before deployment...")
            creds.refresh(Request())
            print("Token refreshed.")
            
            # Save back to disk
            print(f"Saving new token to {token_path}...")
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())
            print("Token saved successfully.")
        else:
            print(f"Credentials are valid (Expiry: {creds.expiry}). Proceeding.")
            
    except ImportError:
        print("Warning: could not import google-auth libraries. Skipping auto-refresh.")
    except Exception as e:
        print(f"Warning: Auto-refresh failed: {e}. Proceeding with existing token.")
    # --- AUTO-REFRESH LOGIC END ---

    print(f"Reading {token_path}...")
    with open(token_path, 'r') as f:
        token_content = f.read().strip()
        
    # Validate JSON
    try:
        json.loads(token_content)
    except json.JSONDecodeError:
        print("Error: token.json is not valid JSON.")
        return

    # Create temporary env file
    env_file = "deploy_env.yaml"
    print(f"Creating {env_file}...")
    
    # Also update the persistent env.yaml for local development convenience
    if os.path.exists("env.yaml"):
        print("Updating local env.yaml with fresh token...")
        try:
            import yaml
            with open("env.yaml", 'r') as f:
                local_env = yaml.safe_load(f) or {}
            
            # Update the token
            local_env['GMAIL_TOKEN_JSON'] = json.loads(token_content)
            
            with open("env.yaml", 'w') as f:
                yaml.dump(local_env, f, default_flow_style=False)
        except Exception as e:
            print(f"Warning: Failed to update local env.yaml: {e}")

    with open(env_file, 'w') as f:
        # Use json.dumps to handle escaping of the token string automatically
        # It adds surrounding double quotes, so it is a valid JSON string, which is valid YAML
        escaped_token = json.dumps(token_content)
        f.write(f"GMAIL_TOKEN_JSON: {escaped_token}\n")
        
        # Read GEMINI_API_KEY from existing env.yaml if available
        try:
             import yaml
             if os.path.exists('env.yaml'):
                 with open('env.yaml', 'r') as env_f:
                     existing_env = yaml.safe_load(env_f)
                     if existing_env and 'GEMINI_API_KEY' in existing_env:
                         print("Found GEMINI_API_KEY in env.yaml, adding to deployment...")
                         gemini_key = json.dumps(existing_env['GEMINI_API_KEY'])
                         f.write(f"GEMINI_API_KEY: {gemini_key}\n")
                     else:
                         print("Warning: GEMINI_API_KEY not found in env.yaml. LLM features may fail.")
        except Exception as e:
            print(f"Warning: Could not read GEMINI_API_KEY from env.yaml: {e}")

    # Construct gcloud command
    cmd = [
        "gcloud", "functions", "deploy", "signage-bot",
        "--gen2",
        "--runtime=python311",
        "--region=us-central1",
        "--source=.",
        "--entry-point=pubsub_handler",
        "--trigger-topic=gmail-watch",
        "--project=super-home-automation",
        "--memory=512MiB",
        f"--env-vars-file={env_file}"
    ]
    
    print("Deploying Cloud Function 'signage-bot'...")
    print("This may take a few minutes...")
    
    try:
        # Run command
        subprocess.check_call(cmd, shell=True)
        print("Deployment successful!")
        
    except subprocess.CalledProcessError as e:
        print(f"Deployment failed with exit code {e.returncode}")
    except FileNotFoundError:
        print("Error: 'gcloud' command not found.")
    finally:
        # Cleanup
        if os.path.exists(env_file):
            os.remove(env_file)
            print(f"Removed {env_file}")

if __name__ == "__main__":
    deploy()
