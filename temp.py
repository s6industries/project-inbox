import json
import os


TRAINING_DATA_DIR = "training_data"

with open("training_input.txt", "r") as file:
    lines = file.readlines()

index = 0
while index < len(lines):
    line = lines[index].strip()
    if not line:
        index += 1
        continue
    
    parts = line.split(":")
    assert "id" == parts[0].strip().lower(), f"Error: {line=}"
    message_id = parts[1].strip()
    classification = lines[index+1].split(":")[1].strip().lower()
    reason = lines[index+2].split(":")[1].strip()
    print(f"{message_id=}, {classification=}, {reason=}")
    index += 3
    
    message_data = {}
    message_data["id"] = message_id
    message_data["classification"] = classification
    message_data["reason"] = reason
    
    with open(f"emails/{message_id}.json", "r") as file:
        data = json.load(file)
        message_data = message_data | data
    
    # print(json.dumps(message_data, indent=4))
    
    with open(f"{TRAINING_DATA_DIR}/{message_id}.json", "w") as file:
        json.dump(message_data, file, indent=4)

# build prompt
prompt = """
Hi, please help me categorize my email. Your task is to read the email content and classify it into one of the following categories: KEEP, DELETE, or UNSURE. Also provide a reason for your choice.

Categories:
* KEEP: Important emails that require attention or have sentimental value.
* DELETE: Unimportant emails that can be discarded or old emails that are no longer relevant.
* UNSURE: Emails that are ambiguous and need further review.

Example email format:

```
id: 1690b96f1d18385c
snippet: Orders received. Thank you From: Zion Perez [mailto:zion.perez@gmail.com] Sent: Wednesday, February 20, 2019 9:00 AM To: orders@alexander-tvl.com Subject: CPT Zion Perez - orders Sir/Ma&#39;am,
subject: RE: CPT Zion Perez - orders
to: zion.perez@gmail.com
from: Orders <orders@alexander-tvl.com>
date: Wed, 20 Feb 2019 09:47:09 -0600
num_attachments: 0
```

Example response format:

```
id: 1690b96f1d18385c
classification: delete
reason: The email is from 2019 and pertains to orders, which are likely outdated and no longer relevant.
```

In a separate message, I will send a training set of emails with their classifications for you to reference. Do you have any questions before I proceed?
"""

for filename in os.listdir(TRAINING_DATA_DIR):
    filepath = os.path.join(TRAINING_DATA_DIR, filename)
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
print("**********************")
print(prompt)
