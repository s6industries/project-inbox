from dotenv import load_dotenv
import main


def test_classify_email():
    load_dotenv()
    
    # Test with an email that should be deleted
    email = "This is a super NOT important email.."
    response = main.classify_email(email)
    print(f"{email=}\n{response=}\n")
    assert "DELETE" in response
    
    # Test with an email that should be kept
    email = "This is a super VERY important email.. definitely keep this one"
    response = main.classify_email(email)
    print(f"{email=}\n{response=}\n")
    assert "KEEP" in response
    
    # Test with an ambiguous email
    email = "This is an ambiguous email. It could possibly be deleted. It could also possibly be important."
    response = main.classify_email(email)
    print(f"{email=}\n{response=}\n")
    assert "KEEP" in response