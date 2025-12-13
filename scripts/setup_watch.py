import sys
import os

# Add parent directory to path to allow importing gmail_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gmail_service import get_gmail_service

def setup_watch(topic_name):
    """
    Tells Gmail to push notifications to the specified Pub/Sub topic.
    """
    try:
        service = get_gmail_service(token_json_path='token.json')
        
        request = {
            'labelIds': ['INBOX'],
            'topicName': topic_name
        }
        
        response = service.users().watch(userId='me', body=request).execute()
        print(f"Watch setup successful: {response}")
        
    except Exception as e:
        print(f"Error setting up watch: {e}")

if __name__ == "__main__":
    # Hardcoded topic for convenience
    topic = "projects/super-home-automation/topics/gmail-watch"
    print(f"Setting up watch for topic: {topic}")
    setup_watch(topic)
