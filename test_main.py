from dotenv import load_dotenv
import main as email_sorter
import random
import json
import os
import unittest
import tempfile


# def test_classify_email():
#     load_dotenv()
    
#     # Test with an email that should be deleted
#     email = "This is a super NOT important email.."
#     response = email_sorter.classify_email(email)
#     print(f"{email=}\n{response=}\n")
#     assert "DELETE" in response
    
#     # Test with an email that should be kept
#     email = "This is a super VERY important email.. definitely keep this one"
#     response = email_sorter.classify_email(email)
#     print(f"{email=}\n{response=}\n")
#     assert "KEEP" in response
    
#     # Test with an ambiguous email
#     email = "This is an ambiguous email. It could possibly be deleted. It could also possibly be important."
#     response = email_sorter.classify_email(email)
#     print(f"{email=}\n{response=}\n")
#     assert "KEEP" in response or "DELETE" in response


def test_list_labels():
    service = email_sorter.get_api_service_obj()
    labels = email_sorter.list_labels(service)    
    label_names = [label["name"] for label in labels]
    expected_labels = ["CHAT", "SENT", "INBOX", "IMPORTANT", "TRASH", "DRAFT", "SPAM", 
            "CATEGORY_FORUMS", "CATEGORY_UPDATES", "CATEGORY_PERSONAL", 
            "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "STARRED", "UNREAD"]
    for expected_label in expected_labels:
        assert expected_label in label_names


def test_create_and_delete_label():
    service = email_sorter.get_api_service_obj()
    randnum = random.randint(1000, 9999)
    label_name = "foo" + str(randnum)
    new_label = email_sorter.create_label(service, label_name)
    print(f"{new_label=}")
    assert new_label["name"] == label_name
    assert email_sorter.delete_label(service, new_label["id"])


def test_list_messages():
    service = email_sorter.get_api_service_obj()
    messages, _ = email_sorter.list_messages(service)
    assert messages

    test_message = {
        "Subject": "test email 001",
        "From": "testuser9448@gmail.com",
        "To": "testuser9448@gmail.com",
        "body": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
    }
    
    for message in messages:
        message_data = email_sorter.get_full_message(service, message['id'])

        if message_data["headers"]["Subject"] == test_message["Subject"]:
            assert test_message["From"] in message_data["headers"]["From"]
            assert test_message["To"] in message_data["headers"]["To"]
            
            # Remove the line breaks from the message
            message_body = message_data["body"].replace('\r\n', ' ').replace('\n', ' ').strip()
            assert test_message["body"] == message_body


def test_apply_label_to_message():
    service = email_sorter.get_api_service_obj()
    messages, _ = email_sorter.list_messages(service)
    assert messages

    # Create new random label
    randnum = random.randint(1000, 9999)
    label_name = "foo" + str(randnum)
    new_label = email_sorter.create_label(service, label_name)

    # Find test email 002
    for message in messages:
        message_data = email_sorter.get_full_message(service, message['id'])
        if message_data["headers"]["Subject"] == "test email 002":
            result_message = email_sorter.apply_label(service, message['id'], new_label['id'])
            assert new_label["id"] in result_message["labelIds"]
    
    # Clean-up: delete random label
    assert email_sorter.delete_label(service, new_label["id"])


def test_get_email_labels():
    service = email_sorter.get_api_service_obj()
    messages, _ = email_sorter.list_messages(service)
    print(messages)
    email_id = messages[0]["id"]
    labels = email_sorter.get_email_labels(service, email_id)
    print(f"Labels for email {email_id}: {labels}")
    assert "INBOX" in labels


def test_process_raw_email_message():
    service = email_sorter.get_api_service_obj()
    messages, _ = email_sorter.list_messages(service, max_results=10)
    
    for message in messages:
        raw_message = email_sorter.get_full_message(service, message['id'])
        processed_message = email_sorter.process_raw_email_message(raw_message)
        
        assert "subject" in processed_message
        assert "snippet" in processed_message
        assert "from" in processed_message
        assert "to" in processed_message
        print(processed_message.keys())


class TestBuildEmailChunks(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.TemporaryDirectory()
        
        # Create sample email files
        self.emails = [
            {
                "subject": "Test Email 1",
                "body": "This is the body of test email 1.",
                "attachments": ["file1.txt", "file2.txt"]
            },
            {
                "subject": "Test Email 2",
                "body": "This is the body of test email 2.",
                "attachments": ["file3.txt"]
            },
            {
                "subject": "Test Email 3",
                "body": "This is the body of test email 3.",
                "attachments": []
            }
        ]
        
        for i, email in enumerate(self.emails):
            with open(os.path.join(self.test_dir.name, f"email_{i}.json"), "w") as f:
                json.dump(email, f)
    
    def tearDown(self):
        self.test_dir.cleanup()


    def test_build_email_chunks(self):
        chunk_size = 300
        chunks = email_sorter.build_email_chunks(emails_dir=self.test_dir.name, chunk_size=chunk_size)
        
        # Test the output
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        
        # Verify the content of the chunks
        for chunk in chunks:
            assert len(chunk) <= chunk_size
            assert "subject:" in chunk
            assert "body:" in chunk
            assert "num_attachments:" in chunk
    
    def test_large_chunk_size(self):
        # Define a large chunk size to ensure all emails fit into one chunk
        chunk_size = 10000
        chunks = email_sorter.build_email_chunks(emails_dir=self.test_dir.name, chunk_size=chunk_size)
        assert len(chunks) == 1
    
    def test_small_chunk_size(self):
        # Define a small chunk size to ensure multiple chunks are created
        chunk_size = 100
        chunks = email_sorter.build_email_chunks(emails_dir=self.test_dir.name, chunk_size=chunk_size)
        assert len(chunks) > 1


def test_get_training_data_prompt():
    test_dir = tempfile.TemporaryDirectory()
    for i in range(20):
        email = {
            "id": str(random.randrange(10000, 99999)),
            "subject": f"Test Email {i}",
            "body": f"This is the body of test email {i}.",
            "classification": "delete",
            "reason": "This is a test email and likely not important",
            "attachments": []
        }
        with open(os.path.join(test_dir.name, f"email_{i}.json"), "w") as f:
            json.dump(email, f)

    prompt = email_sorter.get_training_data_prompt(training_data_dir=test_dir.name)
    assert "Here is the training set of emails:" in prompt
    assert prompt.count("id:") == len(os.listdir(test_dir.name))
    assert "Do you have any questions" in prompt
    test_dir.cleanup()


def test_main_func():
    test_message = {
        "subject": "test email 003",
        "snippet": "This email is used for pytest `test_main`. Do NOT delete this email."
    }
    email_sorter.main()
    
    # Currently all emails should be saved locally
    found_test_message = False
    EMAILS_DIR = "emails"
    for filename in os.listdir(EMAILS_DIR):
        filepath = os.path.join(EMAILS_DIR, filename)

        if not os.path.isfile(filepath):
            continue
        
        with open(filepath, "r") as file:
            data = json.load(file)
        
        if test_message["subject"] == data["subject"]:
            found_test_message = True
            assert test_message["snippet"] == data["snippet"]
    assert found_test_message
    
    
# def test_debug_message():
#     message_id = "16822b72a074cff9"
#     service = email_sorter.get_api_service_obj()
#     message = service.users().messages().get(userId="me", id=message_id, format='full').execute()    
#     raw_message = email_sorter.get_full_message(service, message_id)
#     print(json.dumps(raw_message, indent=4))