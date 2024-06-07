import openai
import os


import os
from dotenv import load_dotenv
from openai import OpenAI


def get_gpt_response(prompt):
    client = OpenAI(
        api_key=os.environ['OPENAI_API_KEY'],  # this is also the default, it can be omitted
    )
    
    # References:
    # https://platform.openai.com/docs/api-reference/making-requests
    # https://platform.openai.com/docs/api-reference/streaming
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    load_dotenv()
    user_input = input("Enter your message: ")
    response = get_gpt_response(user_input)
    print("GPT-3 response:", response)


# *** SAMPLE EMAIL SORTING CODE ***
# # Ensure you have set the environment variable for your API key
# # export OPENAI_API_KEY='your-api-key'
# openai.api_key = os.environ['OPENAI_API_KEY']

# def classify_email(email_content):
#     response = openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",
#         messages=[
#             {"role": "system", "content": "You are an email assistant. Classify emails as either 'not important/delete' or 'probably important/keep'."},
#             {"role": "user", "content": f"Classify the following email: {email_content}"}
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