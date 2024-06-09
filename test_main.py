from dotenv import load_dotenv
import main as email_sorter
import random


def test_classify_email():
    load_dotenv()
    
    # Test with an email that should be deleted
    email = "This is a super NOT important email.."
    response = email_sorter.classify_email(email)
    print(f"{email=}\n{response=}\n")
    assert "DELETE" in response
    
    # Test with an email that should be kept
    email = "This is a super VERY important email.. definitely keep this one"
    response = email_sorter.classify_email(email)
    print(f"{email=}\n{response=}\n")
    assert "KEEP" in response
    
    # Test with an ambiguous email
    email = "This is an ambiguous email. It could possibly be deleted. It could also possibly be important."
    response = email_sorter.classify_email(email)
    print(f"{email=}\n{response=}\n")
    assert "KEEP" in response or "DELETE" in response


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
        
        assert "body" in processed_message
        assert "subject" in processed_message
        assert "from" in processed_message
        assert "to" in processed_message
        print(processed_message.keys())