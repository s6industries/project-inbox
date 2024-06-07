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

def classify_email(email_content):
    client = OpenAI(
        api_key=os.environ['OPENAI_API_KEY'],  # this is also the default, it can be omitted
    )
    
    # References:
    # https://platform.openai.com/docs/api-reference/making-requests
    # https://platform.openai.com/docs/api-reference/streaming
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an email assistant. Classify emails as either 'keep' or 'delete'."},
            {"role": "user", "content": f"Classify the following email and only return either 'KEEP' or 'DELETE':\n\n{email_content}"}
        ]
    )
    return response.choices[0].message.content.strip()


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
    user_id = "me"
    message_data = {
        "headers": {},
        "body": "",
        "html_body": ""
    }

    try:
        # Fetch the full message using the Gmail API
        message = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()

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
    # Hardcoding user_id to 'me' - currently do not have a use-case for another user_id
    user_id = "me"
    try:
        # Apply the label to the message
        message = service.users().messages().modify(
            userId=user_id,
            id=msg_id,
            body={'addLabelIds': [label_id]}
        ).execute()
        
        print(f"Label applied: {label_id} to message ID: {msg_id}")
        print("Updated Labels: ", message['labelIds'])
        return message
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


# *** SAMPLE EMAIL SORTING CODE ***
# # Ensure you have set the environment variable for your API key
# # export OPENAI_API_KEY='your-api-key'
# openai.api_key = os.environ['OPENAI_API_KEY']

# def classify_email(email_content):
#     response = openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",
#         messages=[
#             {"role": "system", "content": "You are an email assistant. Classify emails as either 'important' or 'delete'."},
#             {"role": "user", "content": f"Classify the following email and only return either 'IMPORTANT' or 'DELETE':\n\n{email_content}"}
#         ]
#     )
#     classification = response.choices[0].message['content'].strip()
#     return classification

# if __name__ == "__main__":
#     # Example list of emails in plain text
#     emails = [
#         "Subject: Meeting Reminder\nHi, just a reminder about the meeting tomorrow at 10 AM.",
#         "Subject: Sale Now On!\nDon't miss our big sale! Up to 50% off on selected items.",
#         "Subject: Project Update\nPlease find attached the latest updates on the project."
#     ]

#     for email in emails:
#         result = classify_email(email)
#         print(f"Email: {email}\nClassification: {result}\n")