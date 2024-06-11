import os
import os.path
import base64
import json
import multiprocessing

from dotenv import load_dotenv
from openai import OpenAI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


DEBUG = 1

#
# OpenAI API Functions
#

KEEP = "KEEP"
DELETE = "DELETE"


def get_training_data_prompt(training_data_dir="training_data"):
    prompt = "Here is the training set of emails:\n\n"
    for filename in os.listdir(training_data_dir):
        filepath = os.path.join(training_data_dir, filename)
        # checking if it is a file
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r") as file:
            data = json.load(file)
        # add attachment count
        data["num_attachments"] = len(data["attachments"])
        del data["attachments"]
        for key, value in data.items():
            if key == "classification" or key == "reason": # print these last
                continue
            prompt += f"{key}: {value}\n"
        prompt += "classification: " + data["classification"] + "\n"
        prompt += "reason: " + data["reason"] + "\n"
        prompt += "\n"
    prompt += "In a separate message, I will send several emails to classify. Do you have any questions before I proceed?\n"
    return prompt


def build_initial_messages():
    system_message = {
        "role": "system",
        "content": (
            "You are an email categorization assistant. Your task is to read the email content "
            "and categorize it into one of the following categories: KEEP, DELETE, or UNSURE"
        )
    }

    with open("initial_prompt.md", "r") as file:
        initial_prompt_content = file.readlines()

    user_message1 = {
        "role": "user",
        "content": initial_prompt_content
    }
    
    gpt_response1 = {
        "role": "assistant",
        "content": "I understand the task. Please go ahead and send the training set of emails for reference."
    }
    
    user_message2 = {
        "role": "user", 
        "content": get_training_data_prompt()
    }
    
    gpt_response2 = {
        "role": "assistant",
        "content": "No questions. Please proceed with sending the emails to classify."
    }
    
    return [system_message, user_message1, gpt_response1, user_message2, gpt_response2]


# This function breaks down email data into fix sized chunks so that GPT can 
# be given an appropriately sized prompt
EMAILS_DIR = "emails"
def build_email_chunks(emails_dir=EMAILS_DIR, chunk_size=30000):
    chunks = []
    chunk = ""
    
    for filename in os.listdir(emails_dir):
        filepath = os.path.join(emails_dir, filename)

        if not os.path.isfile(filepath):
            continue
        
        with open(filepath, "r") as email_file:
            data = json.load(email_file)

        # add attachment count and delete attachments
        data["num_attachments"] = len(data.get("attachments", []))            
        data.pop("attachments", None)

        email_text = ""
        for key, value in data.items():
            email_text += f"{key}: {value}\n"
        email_text += "\n"

        if len(chunk) + len(email_text) > chunk_size:
            chunks.append(chunk)
            chunk = email_text
        else:
            chunk += email_text

    if len(chunk) > 0:
        chunks.append(chunk)
    return chunks


# def classify_emails():
#     email_chunks = build_email_chunks()
    
#     # The param `os.environ['OPENAI_API_KEY']` is also the default; it can be omitted
#     client = OpenAI(api_key=os.environ['OPENAI_API_KEY']) 
    
#     messages = build_initial_messages()
    
#     while True:
#         # Build list of emails
#         break

#     user_message = {
#         "role": "user", 
#         "content": f"Classify the following emails:\n\n{emails}"
#     }
    
#     # References:
#     # https://platform.openai.com/docs/api-reference/making-requests
#     # https://platform.openai.com/docs/api-reference/streaming
#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             system_message,
#             user_message1, gpt_response1,
#             user_message2, gpt_response2,
#         ],
#         temperature=0
#     )
#     response = response.choices[0].message.content.strip()
#     return response


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


label_id_cache = {}
def get_label_id(service, label_name):
    """
    Retrieve the ID of a specified label. If the label does not exist, create it.

    Parameters:
    service (obj): The Gmail API service instance.
    label_name (str): The name of the label to retrieve or create.

    Returns:
    str: The ID of the specified label.
    """
    # Check if the label ID is already in the cache
    if label_name in label_id_cache:
        return label_id_cache[label_name]
    
    # Retrieve all labels
    labels = list_labels(service)
    
    # Search for the label with the specified name
    for label in labels:
        if label["name"] == label_name:
            return label["id"]
    
    # Create the label if it does not exist
    new_label = create_label(service, label_name)
    
    # Check if the label creation was successful
    if 'id' in new_label:
        return new_label["id"]
    else:
        raise Exception(f"Failed to create label: {label_name}")


def delete_label(service, label_id):
    try:
        service.users().labels().delete(userId='me', id=label_id).execute()
        print(f'Label with ID {label_id} deleted successfully.')
        return True
    except Exception as e:
        print(f'An error occurred: {e}')
        return False


def list_messages(service, page_token=None, max_results=100):
    try:
        # Call the Gmail API to list messages
        results = service.users().messages().list(userId='me', maxResults=max_results, pageToken=page_token).execute()
        messages = results.get('messages', [])
        next_page_token = results.get('nextPageToken')
        return messages, next_page_token
    except Exception as error:
        print(f"An error occurred: {error}")
        return None


def get_full_message(service, msg_id):
    message_data = {
        "id": msg_id,
        "snippet": "",
        "headers": {},
        "body": "",
        "html_body": "",
        "attachments": [],
    }

    try:
        # Fetch the full message using the Gmail API
        message = service.users().messages().get(userId="me", id=msg_id, format='full').execute()
    except HttpError as error:
        # Store the error in the dictionary if one occurs during the API call
        message_data["error"] = str(error)
    
    
    message_data["snippet"] = message["snippet"]

    # Extract headers from the message payload
    headers = message['payload']['headers']
    for header in headers:
        message_data["headers"][header['name']] = header['value']

    # Check if the message payload contains parts
    if 'parts' in message['payload']:
        for part in message['payload']['parts']:
            if "attachmentId" in part["body"]:
                # Check if the part contains an attachment
                # TODO: consider weighing attachments for email sorting
                message_data["attachments"].append(part["body"]["attachmentId"])
            elif part['mimeType'] == 'text/plain':
                # Decode and store the plain text body of the email
                # Double check that we're dealing with a "data" part
                assert "data" in part["body"]
                body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                message_data["body"] += body
            elif part['mimeType'] == 'text/html':
                # Decode and store the HTML body of the email
                assert "data" in part["body"]
                html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                message_data["html_body"] += html_body
    else:
        # If no parts are found, decode and store the body of the email directly
        if "data" in message["payload"]["body"]:
            body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            message_data["body"] = body
        elif "attachmentId" in message["payload"]["body"]:
            message_data["attachments"].append(message['payload']['body']['attachmentId'])
    
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

    # Note: the Subject, From, and Date headers could all possibly differ.
    # For example, the "From" header could also be "FROM" or "Subject" could be "subject".
    # Need to account for these edge cases:
    headers = {
        "subject": "", 
        "to": "",
        "from": "", 
        "date": "",
        "cc": "",
    }
    alternatives = {
        "to" : "delivered-to"
    }
    for key in headers:
        for email_header in raw_email["headers"]:
            if key == email_header.lower():
                headers[key] = email_header
                break
            # Check for alternative/less-common subject headers, e.g. 'Delivered-To'
            if key in email_header.lower() and key in alternatives and alternatives[key] == email_header.lower():
                headers[key] = email_header
                break
    
    processed_email = {}
    processed_email["id"] = raw_email["id"]
    processed_email["snippet"] = raw_email["snippet"]

    print("\n===================================")
    print(f"ID: {processed_email['id']}")
    
    for key, value in headers.items():
        # Account for emails with an empty subject header
        if key == "subject" and not value:            
            processed_email[key] = "(no subject)"
            continue
        # Catch edge case where there is no one on the "to" line
        if key == "to" and not value:
            processed_email[key] = "(TO line empty)"
            continue
        # Empty 'cc' line is normal/expected
        if key == "cc" and not value:
            continue
        assert value, f"Error in header: {raw_email['id']=}, {key=}, {value=}, {raw_email['headers'].keys()=}"
        processed_email[key] = raw_email['headers'][value]
        print(f"{key}: {processed_email[key]}")
        

    # Note: avoid this GPT error code by truncating the message body
    # Error code: 400 - {'error': {'message': "This model's maximum context length is 16385 tokens.
    # processed_email["body"] = raw_email["body"][:15000]
    # print(f"Message length: {len(raw_email['body'])}")
    
    processed_email["attachments"] = raw_email["attachments"]
    print(f"Attachments: {processed_email['attachments']}")
    
    return processed_email


def get_email_labels(service, message_id):
    try:
        message = service.users().messages().get(userId='me', id=message_id, format='metadata').execute()
        return message.get('labelIds', [])
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


PAGE_TOKEN_FILENAME = "page_token.json"
def load_page_token():
    try:
        with open(PAGE_TOKEN_FILENAME, 'r') as json_file:
            data = json.load(json_file)
        print(f"Data successfully loaded from {PAGE_TOKEN_FILENAME}")
        assert "page_token" in data
        return data["page_token"]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def save_page_token(page_token):
    try:
        with open(PAGE_TOKEN_FILENAME, 'w') as json_file:
            data = { "page_token" : page_token }
            json.dump(data, json_file)
        print(f"Data successfully saved to {PAGE_TOKEN_FILENAME}")
    except Exception as e:
        print(f"An error occurred: {e}")


# def classify_and_label(service, message):
#     # Check if email is "starred" or already processed
#     label_ids = get_email_labels(service, message["id"])
#     if "STARRED" in label_ids:
#         return
#     processed_label_id = get_label_id(service, "_processed")
#     if processed_label_id in label_ids:
#         return
    
#     # Request full email, process, and classify the email
#     raw_message_data = get_full_message(service, message['id'])
#     message_data = process_raw_email_message(raw_message_data)
#     response = classify_email(repr(message_data))
#     if len(response) > 100:
#         raise Exception(f"Error: received unexpectedly long response: {response}")
    
#     # Apply response label
#     category_name = "_" + response.lower()
#     category_label_id = get_label_id(service, category_name)
#     apply_label(service, message["id"], category_label_id)
    
#     # Apply "_processed" label
#     apply_label(service, message["id"], processed_label_id)


def save_email_content(service, message, emails_dir="emails"):
    os.makedirs(emails_dir, exist_ok=True)
    filepath = f"{emails_dir}/{message['id']}.json"
    if os.path.exists(filepath):
        # Email already saved
        return
    
    raw_message = get_full_message(service, message['id'])
    processed_message = process_raw_email_message(raw_message)
    with open(filepath, 'w') as file:
        json.dump(processed_message, file, indent=4)


def main():
    load_dotenv()
    service = get_api_service_obj()

    # Loop through the emails and save them locally
    
    page_token = load_page_token()
    emails_sorted = 0
    max_results = 100 # Max value google will accept is 500
    while True:
        # Backup the current page_token to a json file
        save_page_token(page_token)
        
        # Query for emails
        messages, page_token = list_messages(service, page_token, max_results)        
        emails_sorted += len(messages)
        
        # Save emails
        if DEBUG:
            for message in messages:
                save_email_content(service, message)
        else: # else process asynchronously
            # Create a list of arguments to pass to save_email_content
            params = [(service, message) for message in messages]
            # Create a pool of worker processes to save emails asynchronously
            with multiprocessing.Pool() as pool:
                # Use starmap to pass multiple arguments to the function
                pool.starmap(save_email_content, params)
        
        if not page_token:
            break
    print(f"Successfully sorted {emails_sorted} emails")
        
    # # Consolidate contacts into a dict
    # contacts = {} # "email" : email_count
    # for filename in os.listdir(EMAILS_DIR):
    #     filepath = os.path.join(EMAILS_DIR, filename)

    #     if not os.path.isfile(filepath):
    #         continue
        
    #     with open(filepath, "r") as email_file:
    #         data = json.load(email_file)
    #         print(data)
    #         headers = ["cc", "to", "from"]
    #         for header in headers:
    #             if header in data:
    #                 contact_name = data[header]
    #                 contacts[contact_name] = contacts.get(contact_name, 0) + 1
    # with open("contacts.json", "w") as contacts_file:
    #     sorted_contacts = dict(sorted(contacts.items(), key=lambda item: item[1], reverse=True))
    #     json.dump(sorted_contacts, contacts_file, indent=4)

# TODO: update prompt, send new emails to gpt, save sorted email data to processed_emails folder, review
# TODO: then run on all emails


if __name__ == "__main__": # pragma: no cover
    main()