import os
from io import BytesIO
from signage_lib import generate_pdf_bytes, generate_llm_and_original_pdfs
from gmail_service import get_gmail_service, get_message_content, get_attachment_data, create_message_with_multiple_attachments, send_message, mark_as_read
import json
import base64

try:
    import functions_framework
except Exception as e:
    print(f"Warning: Could not import functions_framework: {e}")
    class functions_framework:
        @staticmethod
        def http(func): return func
        @staticmethod
        def cloud_event(func): return func

from env_loader import load_env
load_env() # Load environment variables for local development

@functions_framework.http
def generate_signs_http(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`.
    """
    
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600'
    }

    if request.method == 'OPTIONS':
        return ('', 204, headers)

    if request.path == '/renew_watch':
        print("Received renew_watch request.")
        try:
            # Re-use the setup_watch logic logic or call gmail service directly
            # Since we have the token in env var, we can just call watch()
            token_json_str = os.environ.get('GMAIL_TOKEN_JSON')
            if not token_json_str:
                return ('GMAIL_TOKEN_JSON env var not set', 500, headers)
                
            service = get_gmail_service(token_info=json.loads(token_json_str))
            request_body = {
                'labelIds': ['INBOX'],
                'topicName': 'projects/super-home-automation/topics/gmail-watch'
            }
            service.users().watch(userId='me', body=request_body).execute()
            print("Watch renewed successfully via endpoint.")
            return ('Watch renewed successfully', 200, headers)
        except Exception as e:
            print(f"Error renewing watch: {e}")
            return (f"Error renewing watch: {str(e)}", 500, headers)

    if request.method != 'POST':
        return ('Only POST requests are accepted', 405, headers)

    # Check if file is in request.files
    if 'file' not in request.files:
        return ('No file part in the request', 400, headers)
    
    file = request.files['file']
    
    if file.filename == '':
        return ('No selected file', 400, headers)
    
    if file:
        try:
            # Read file into BytesIO
            file_content = file.read()
            excel_buffer = BytesIO(file_content)
            
            # Generate PDF
            pdf_buffer = generate_pdf_bytes(excel_buffer)
            
            if pdf_buffer is None:
                return ('No new products to print.', 200, headers)

            # Return PDF
            return (
                pdf_buffer.getvalue(),
                200,
                {
                    'Content-Type': 'application/pdf',
                    'Content-Disposition': 'attachment; filename="signs.pdf"',
                    **headers
                }
            )
        except Exception as e:
            return (f"Error processing file: {str(e)}", 500, headers)

    return ('Unknown error', 500, headers)

@functions_framework.cloud_event
def pubsub_handler(cloud_event):
    """
    Triggered from a message on a Cloud Pub/Sub topic.
    """
    import base64
    import json
    from gmail_service import get_gmail_service, get_message_content, get_attachment_data, create_message_with_multiple_attachments, send_message, mark_as_read
    from signage_lib import generate_llm_and_original_pdfs
    
    # 1. Decode Pub/Sub message
    pubsub_message = base64.b64decode(cloud_event.data["message"]["data"]).decode()
    event_data = json.loads(pubsub_message)
    
    print(f"Received event: {event_data}")
    
    if not event_data.get('historyId'):
        print("No historyId found in event.")
        return

    # 2. Authenticate
    token_json_str = os.environ.get('GMAIL_TOKEN_JSON')
    if not token_json_str:
        print("Error: GMAIL_TOKEN_JSON env var not set.")
        return
        
    service = get_gmail_service(token_info=json.loads(token_json_str))
    
    # 3. Find and process new messages
    results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD']).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No new unread messages.")
        return

    print(f"Found {len(messages)} unread messages. Checking for attachments...")

    for msg in messages:
        msg_id = msg['id']
        sender, subject = 'Unknown', 'No Subject'
        try:
            full_msg = get_message_content(service, 'me', msg_id)
            headers = full_msg.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            
            print(f"Checking email: {subject} from {sender}")
            
            # Find Excel attachment
            def find_excel(parts_list):
                for part in parts_list:
                    if part.get('filename') and (part['filename'].endswith('.xlsx') or part['filename'].endswith('.xls')):
                        return part.get('body', {}).get('attachmentId'), part['filename']
                    if 'parts' in part:
                        found_id, found_name = find_excel(part['parts'])
                        if found_id: return found_id, found_name
                return None, None

            excel_attachment_id, filename = find_excel(full_msg.get('payload', {}).get('parts', []))
            
            if excel_attachment_id:
                print(f"  Found Excel attachment: {filename}")
                data = get_attachment_data(service, 'me', msg_id, excel_attachment_id)
                excel_file = BytesIO(data)
                
                # Generate both PDFs and the Excel tracking file
                llm_pdf, original_pdf, llm_excel = generate_llm_and_original_pdfs(excel_file)
                
                if llm_pdf is None or original_pdf is None:
                    # Case: No products to print
                    reply_subject = f"Re: {subject}"
                    reply_body = "Hello,\n\nWe processed your Excel file, but found no new products to print (or all products were already up-to-date in the database).\n\nNo PDF signs were generated."
                    reply_msg = create_message_with_multiple_attachments(
                        sender='me', to=sender, subject=reply_subject, body=reply_body, attachments=[]
                    )
                    send_message(service, 'me', reply_msg)
                    print("  Reply sent: No products to print.")
                else:
                    # Prepare attachments for email
                    attachments = [
                        {'filename': 'llm_signs.pdf', 'data': llm_pdf.getvalue()},
                        {'filename': 'original_signs.pdf', 'data': original_pdf.getvalue()},
                        {'filename': 'generated_names.xlsx', 'data': llm_excel.getvalue()}
                    ]
                    
                    # Reply with attachments
                    reply_subject = f"Re: {subject}"
                    reply_body = (
                        "Here are your generated signs.\n\n"
                        "- 'llm_signs.pdf': Signs with names improved by the language model.\n"
                        "- 'original_signs.pdf': Signs with original names from your file.\n"
                        "- 'generated_names.xlsx': Excel file showing the final names used (including any forced original names)."
                    )
                    reply_msg = create_message_with_multiple_attachments(
                        sender='me', to=sender, subject=reply_subject, body=reply_body, attachments=attachments
                    )
                    
                    send_message(service, 'me', reply_msg)
                    print("  Reply sent with 3 attachments.")
                
            else:
                print("  No Excel attachment found. Ignoring email.")

            mark_as_read(service, 'me', msg_id)

        except Exception as e:
            print(f"Error processing message {msg_id}: {e}")
            try:
                error_body = f"An error occurred while processing your request:\n\n{str(e)}"
                reply_msg = create_message_with_multiple_attachments(
                    sender='me', to=sender, subject=f"Re: {subject}", body=error_body, attachments=[]
                )
                send_message(service, 'me', reply_msg)
                mark_as_read(service, 'me', msg_id)
            except Exception as reply_error:
                print(f"Critical: Could not send error reply: {reply_error}")
