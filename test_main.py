from dotenv import load_dotenv
import main


def test_main():
    load_dotenv()
    prompt = "Say this is a test"
    response = main.get_gpt_response(prompt)
    print("GPT-3 response:", response)
    assert "this is a test" in response.lower()