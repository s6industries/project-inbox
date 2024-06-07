import os
import os.path
import base64

from dotenv import load_dotenv
from openai import OpenAI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


#
# OpenAI API Functions
#

KEEP = "KEEP"
DELETE = "DELETE"

def classify_email(email_content):
    client = OpenAI(
        api_key=os.environ['OPENAI_API_KEY'],  # this is also the default, it can be omitted
    )
    
    system_message = {
        "role": "system",
        "content": (
            "You are an email assistant. Your task is to classify emails as either 'keep' or 'delete'. "
            "Only keep emails that are critically important, contain valuable information, or hold sentimental value with good memories. "
            "If an email does not clearly meet these criteria, classify it as 'delete'. If unsure, lean towards delete."
        )
    }
    
    user_message = {
        "role": "user", 
        "content": (
            f"Classify the following email and only return either '{KEEP}' or '{DELETE}':\n\n{email_content}"
        )
    }
    
    # References:
    # https://platform.openai.com/docs/api-reference/making-requests
    # https://platform.openai.com/docs/api-reference/streaming
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            system_message,
            user_message
        ]
    )
    response = response.choices[0].message.content.strip()
    
    # Verify at least one label is specified
    assert KEEP in response or DELETE in response
    # Sanity check to make sure AI doesn't return both options
    assert not(KEEP in response and DELETE in response)

    if KEEP in response:
        return KEEP
    return DELETE


#
# Gmail API Functions
#

# If modifying these scopes, delete the file token.json.
# SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def get_api_service_obj():
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    service = build("gmail", "v1", credentials=creds)
    return service


def list_labels(service):
    try:
        # Call the Gmail API
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        if not labels:
            print("No labels found.")
            return None
        return labels
    except HttpError as error:
        # TODO: Handle errors from gmail API.
        print(f"An error occurred: {error}")


def create_label(service, label_name):
    label_body = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }
    
    try:
        label = service.users().labels().create(userId='me', body=label_body).execute()
        print(f"Label created: {label['name']} (ID: {label['id']})")
        return label
    except Exception as error:
        print(f"An error occurred: {error}")
        return None


def delete_label(service, label_id):
    try:
        service.users().labels().delete(userId='me', id=label_id).execute()
        print(f'Label with ID {label_id} deleted successfully.')
        return True
    except Exception as e:
        print(f'An error occurred: {e}')
        return False


def list_messages(service):
    try:
        # Call the Gmail API to list messages
        results = service.users().messages().list(userId='me', maxResults=10).execute()
        messages = results.get('messages', [])
        return messages
    except Exception as error:
        print(f"An error occurred: {error}")
        return None


def get_full_message(service, msg_id):
    message_data = {
        "headers": {},
        "body": "",
        "html_body": ""
    }

    try:
        # Fetch the full message using the Gmail API
        message = service.users().messages().get(userId="me", id=msg_id, format='full').execute()

        # Extract headers from the message payload
        headers = message['payload']['headers']
        for header in headers:
            message_data["headers"][header['name']] = header['value']

        # Check if the message payload contains parts
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    # Decode and store the plain text body of the email
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    message_data["body"] += body
                elif part['mimeType'] == 'text/html':
                    # Decode and store the HTML body of the email
                    html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    message_data["html_body"] += html_body
        else:
            # If no parts are found, decode and store the body of the email directly
            body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            message_data["body"] = body

    except HttpError as error:
        # Store the error in the dictionary if one occurs during the API call
        message_data["error"] = str(error)

    return message_data


def apply_label(service, msg_id, label_id):
    try:
        # Apply the label to the message
        message = service.users().messages().modify(
            # Hardcoding user_id to 'me' - currently do not have a use-case for another user_id
            userId="me",
            id=msg_id,
            body={'addLabelIds': [label_id]}
        ).execute()
        
        print(f"Label applied: {label_id} to message ID: {msg_id}")
        print("Updated Labels: ", message['labelIds'])
        return message
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def process_raw_email_message(raw_email):
    assert isinstance(raw_email["body"], str)
    
    print("\n===================================")
    print(f"Subject: {raw_email['headers']['Subject']}")
    print(f"Date: {raw_email['headers']['Date']}")
    print(f"From: {raw_email['headers']['From']}")
    print(f"Message length: {len(raw_email['body'])}")
    
    processed_email = {}
    processed_email["Subject"] = raw_email['headers']['Subject']
    processed_email["Date"] = raw_email['headers']['Date']
    processed_email["From"] = raw_email['headers']['From']
    processed_email["body"] = raw_email["body"]
    return repr(processed_email)


def get_email_labels(service, message_id):
    try:
        message = service.users().messages().get(userId='me', id=message_id, format='metadata').execute()
        return message.get('labelIds', [])
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


if __name__ == "__main__":
    load_dotenv()

    service = get_api_service_obj()
    
    # Check for "keep" and "delete" labels. Create them if not present.
    
    KEEP_LABEL = "keep"
    DELETE_LABEL = "delete"
        
    keep_label_id = None
    delete_label_id = None
    
    labels = list_labels(service)
    for label in labels:
        if KEEP_LABEL == label["name"]:
            keep_label_id = label["id"]
        elif DELETE_LABEL == label["name"]:
            delete_label_id = label["id"]

    if not keep_label_id:
        temp = create_label(service, KEEP_LABEL)
        keep_label_id = temp["id"]
    if not delete_label_id:
        temp = create_label(service, DELETE_LABEL)
        delete_label_id = temp["id"]

    # Loop through the messages and classify    
    messages = list_messages(service)
    print(f"Currently sorting: {len(messages)} messages")
    
    for message in messages:
        # Check if email already labeled
        label_ids = get_email_labels(service, message["id"])
        if delete_label_id in label_ids or keep_label_id in label_ids:
            continue
        
        raw_message_data = get_full_message(service, message['id'])
        message_data = process_raw_email_message(raw_message_data)
        response = classify_email(message_data)
                
        if KEEP in response:
            apply_label(service, message["id"], keep_label_id)
        elif DELETE in response:
            apply_label(service, message["id"], delete_label_id)
        
