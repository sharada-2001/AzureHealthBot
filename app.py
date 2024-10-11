import azure.cognitiveservices.speech as speechsdk
import requests
import json
import time

# Azure Speech-to-Text setup
def speech_to_text():
    speech_key = "2fb4a8154ef84f4fbe501cc9b850bcd1"  # Replace with your Azure Speech key 
    service_region = "eastus"  # Replace with your service region
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)

    print("Say something related to health...")
    result = speech_recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print("Recognized: {}".format(result.text))
        return result.text
    else:
        print("Speech not recognized.")
        return None

# Text-to-Speech conversion
def text_to_speech(text):
    speech_key = "2fb4a8154ef84f4fbe501cc9b850bcd1"  # Replace with your Azure Speech key 
    service_region = "eastus"  # Replace with your service region
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    time.sleep(1)  # Delay to avoid throttling
    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized for text.")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"Speech synthesis canceled: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print(f"Error details: {cancellation_details.error_details}")

# Generate Direct Line token for secure bot access
def get_direct_line_token():
    token_url = "https://directline.botframework.com/v3/directline/tokens/generate"
    subscription_key = "SU63qzzJYqA.DThJ_Bsbavyo1k_2Nf9iZvcn52pi97vHmQdAejZD5xU"  # Replace with your Direct Line Secret

    headers = {
        "Authorization": f"Bearer {subscription_key}"
    }

    response = requests.post(token_url, headers=headers)
    if response.status_code == 200:
        token = response.json().get("token")
        print("Direct Line token generated successfully.")
        return token
    else:
        print(f"Failed to retrieve Direct Line token: {response.status_code} - {response.text}")
        return None

# Start conversation with Azure Health Bot
def start_conversation(token):
    health_bot_url = "https://directline.botframework.com/v3/directline/conversations"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.post(health_bot_url, headers=headers)
    if response.status_code == 201:
        conversation_id = response.json().get("conversationId")
        print(f"Conversation started. Conversation ID: {conversation_id}")
        return conversation_id
    else:
        print(f"Failed to start conversation: {response.status_code} - {response.text}")
        return None
def extract_text_from_adaptive_card(card):
    """Extracts text from an adaptive card content."""
    texts = []
    for item in card.get("body", []):
        if item.get("type") == "Container":
            for inner_item in item.get("items", []):
                if inner_item.get("type") == "TextBlock" and 'text' in inner_item:
                    texts.append(inner_item['text'])
                elif inner_item.get("type") == "ActionSet":
                    # Handle actions that might show another card
                    for action in inner_item.get("actions", []):
                        if action.get("type") == "Action.ShowCard":
                            # Recursively extract from the nested card
                            nested_texts = extract_text_from_adaptive_card(action.get("card", {}))
                            texts.extend(nested_texts)
    return texts

def get_health_info(token, conversation_id, keyword):
    url = f"https://directline.botframework.com/v3/directline/conversations/{conversation_id}/activities"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "type": "message",
        "from": {"id": "user1"},
        "text": keyword
    }

    # Send the message to the bot
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("Message sent to Health Bot.")
        
        # Increase delay for bot processing time
        time.sleep(3)  # Adjust delay time as needed for the bot to respond

        # Fetch activities again to check for bot response
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            activities = data.get("activities", [])

            # Look for the bot's response after the user's message
            for activity in reversed(activities):
                if activity.get("from", {}).get("id") != "user1":  # Bot's response

                    # Check if the bot response has text
                    if 'text' in activity:
                        return activity['text']

                    # Check for any attachments (e.g., rich cards or media)
                    elif 'attachments' in activity:
                        for attachment in activity['attachments']:
                            print("Attachment content:")
                            print(json.dumps(attachment, indent=4))  # Print the entire attachment content

                            content_type = attachment.get('contentType', '')
                            content = attachment.get('content', {})

                            # Handle Adaptive Card
                            if content_type == "application/vnd.microsoft.card.adaptive":
                                texts = extract_text_from_adaptive_card(content)
                                if texts:
                                    return '\n'.join(texts)  # Join the texts with a new line

                        return "Bot response with attachment received, but no readable text found in the content."

            return "No response received from Health Bot."
        else:
            print(f"Error fetching conversation data: {response.status_code} - {response.text}")
            return "Error fetching conversation data."
    else:
        print(f"Error sending message to Health Bot: {response.status_code} - {response.text}")
        return "Error sending message to Health Bot."
# Main logic
if __name__ == "__main__":
    speech_text = speech_to_text()

    if speech_text:
        token = get_direct_line_token()
        if token:
            conversation_id = start_conversation(token)
            if conversation_id:
                health_info = get_health_info(token, conversation_id, speech_text)
                print(f"Health information: {health_info}")
                text_to_speech(health_info)
