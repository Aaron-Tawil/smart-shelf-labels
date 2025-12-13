
import os
import yaml

def load_env():
    """
    Loads environment variables from env.yaml if it exists.
    This is for local development. In a deployed environment,
    variables should be set directly.
    """
    env_path = 'env.yaml'
    if os.path.exists(env_path):
        print("--- Loading environment variables from env.yaml for local development ---")
        with open(env_path, 'r') as f:
            env_vars = yaml.safe_load(f)
        if env_vars:
            for key, value in env_vars.items():
                if key not in os.environ:
                    os.environ[key] = str(value)
    
