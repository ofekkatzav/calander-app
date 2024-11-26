import requests

def test_sendgrid_email():
    try:
        sendgrid_api_key = "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"  # החלף עם ה-API Key שלך
        sender_email = "t.166calander@outlook.com"  # כתובת המייל שלך (מאומתת)
        recipient_email = "t.166calander@outlook.com"  # כתובת לנמען

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {sendgrid_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "personalizations": [
                {"to": [{"email": recipient_email}]}
            ],
            "from": {"email": sender_email},
            "subject": "בדיקת שליחת מייל",
            "content": [{"type": "text/plain", "value": "המייל הזה נשלח לצורך בדיקה."}]
        }

        response = requests.post(url, headers=headers, json=data)
        print(f"Response status code: {response.status_code}")
        print(response.text)
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    test_sendgrid_email()


   
