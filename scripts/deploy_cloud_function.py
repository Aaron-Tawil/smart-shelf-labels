"""
Deploy Cloud Function to Google Cloud.
Uses Secret Manager for Gmail token (no longer via env vars).
"""
import subprocess
import json
import os
import sys


def deploy():
    # --- AUTO-REFRESH AND SYNC TO SECRET MANAGER ---
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google.cloud import secretmanager
        
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.modify' 
        ]
        
        token_path = "token.json"
        if os.path.exists(token_path):
            print(f"Checking credentials in {token_path}...")
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
            if creds.expired and creds.refresh_token:
                print("Credentials expired. Refreshing...")
                creds.refresh(Request())
                print(f"Token refreshed. New expiry: {creds.expiry}")
                
                # Save to local disk
                with open(token_path, 'w') as f:
                    f.write(creds.to_json())
                print("Saved refreshed token to disk.")
                
            # Sync to Secret Manager
            print("Syncing token to Secret Manager...")
            client = secretmanager.SecretManagerServiceClient()
            parent = "projects/super-home-automation/secrets/gmail-oauth-token"
            with open(token_path, 'r') as f:
                payload = f.read().encode("UTF-8")
            client.add_secret_version(request={"parent": parent, "payload": {"data": payload}})
            print("Token synced to Secret Manager.")
            
    except ImportError:
        print("Warning: Could not import required libraries. Skipping token sync.")
    except Exception as e:
        print(f"Warning: Token sync failed: {e}. Proceeding with deployment.")

    # Create env file with only GEMINI_API_KEY
    env_file = "deploy_env.yaml"
    print(f"Creating {env_file}...")
    
    with open(env_file, 'w') as f:
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
                        f.write("# No environment variables\n")
        except Exception as e:
            print(f"Warning: Could not read GEMINI_API_KEY from env.yaml: {e}")
            f.write("# No environment variables\n")

    # --- 1. DEPLOY PUBSUB FUNCTION (signage-bot) ---
    cmd_pubsub = [
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
    
    print("\n---------------------------------------------------")
    print("STEP 1: Deploying 'signage-bot' (Pub/Sub Trigger)...")
    print("---------------------------------------------------")
    
    try:
        subprocess.check_call(cmd_pubsub, shell=True)
        print("SUCCESS: 'signage-bot' deployed.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: 'signage-bot' deployment failed with exit code {e.returncode}")
        # Assuming we want to stop if the main bot fails? Or continue?
        # Let's stop to be safe.
        if os.path.exists(env_file): os.remove(env_file)
        return
    except FileNotFoundError:
        print("Error: 'gcloud' command not found.")
        return

    # --- 2. DEPLOY HTTP FUNCTION (gmail-watch-renewer) ---
    cmd_http = [
        "gcloud", "functions", "deploy", "gmail-watch-renewer",
        "--gen2",
        "--runtime=python311",
        "--region=us-central1",
        "--source=.",
        "--entry-point=generate_signs_http",
        "--trigger-http", # Explicitly HTTP
        "--project=super-home-automation",
        "--memory=512MiB",
        f"--env-vars-file={env_file}"
        # We KEEP authentication required for security.
        # User will need to configure Cloud Scheduler with OIDC token.
    ]

    print("\n---------------------------------------------------")
    print("STEP 2: Deploying 'gmail-watch-renewer' (HTTP Trigger)...")
    print("---------------------------------------------------")

    try:
        subprocess.check_call(cmd_http, shell=True)
        print("SUCCESS: 'gmail-watch-renewer' deployed.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: 'gmail-watch-renewer' deployment failed with exit code {e.returncode}")
    finally:
        if os.path.exists(env_file):
            os.remove(env_file)
            print(f"Removed {env_file}")

if __name__ == "__main__":
    deploy()
