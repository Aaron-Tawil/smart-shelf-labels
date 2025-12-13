import json
import os

def fix_env():
    # 1. Read token.json
    if not os.path.exists('token.json'):
        print("Error: token.json not found")
        return
    
    with open('token.json', 'r') as f:
        token_data = json.load(f)

    # 2. Read credentials.json
    if not os.path.exists('credentials.json'):
        print("Error: credentials.json not found")
        return
        
    with open('credentials.json', 'r') as f:
        creds_data = json.load(f)
        # Structure is usually {"installed": {"client_id": "...", ...}}
        installed = creds_data.get('installed', creds_data.get('web', {}))
        client_id = installed.get('client_id')
        client_secret = installed.get('client_secret')

    if not client_id or not client_secret:
        print("Error: Could not find client_id or client_secret in credentials.json")
        return

    # 3. Merge
    token_data['client_id'] = client_id
    token_data['client_secret'] = client_secret
    
    # 4. Write to env.yaml
    # We need to escape the JSON string for YAML if we put it in a single line, 
    # or just use a simple format.
    
    json_str = json.dumps(token_data)
    
    # Simple YAML format
    yaml_content = f"GMAIL_TOKEN_JSON: '{json_str}'"
    
    with open('env.yaml', 'w') as f:
        f.write(yaml_content)
        
    print("Success! Updated env.yaml with full credentials.")

if __name__ == "__main__":
    fix_env()
