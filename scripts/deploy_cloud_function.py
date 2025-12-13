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
    with open(env_file, 'w') as f:
        # Simple YAML format: key: 'value'
        # We assume token_content doesn't contain single quotes, or we escape them
        clean_token = token_content.replace("'", "''") 
        f.write(f"GMAIL_TOKEN_JSON: '{clean_token}'\n")
        
        # Read GEMINI_API_KEY from existing env.yaml if available
        try:
             import yaml
             if os.path.exists('env.yaml'):
                 with open('env.yaml', 'r') as env_f:
                     existing_env = yaml.safe_load(env_f)
                     if existing_env and 'GEMINI_API_KEY' in existing_env:
                         print("Found GEMINI_API_KEY in env.yaml, adding to deployment...")
                         f.write(f"GEMINI_API_KEY: '{existing_env['GEMINI_API_KEY']}'\n")
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
