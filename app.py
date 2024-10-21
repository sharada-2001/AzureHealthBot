from flask import Flask, render_template, jsonify, request
import azure.cognitiveservices.speech as speechsdk
from openai import AzureOpenAI
import requests
import json
import time
import os

app = Flask(__name__)

AZURE_OPENAI_ENDPOINT = "https://talkyopenai.openai.azure.com/"  # Replace with your Azure OpenAI endpoint
AZURE_OPENAI_KEY = "e52149679a3f4d21a8056bfdf9ed3b1d"  # Replace with your Azure OpenAI API key
AZURE_OPENAI_MODEL = "gpt-35-turbo-16k" 

def speech_to_text():
    try:
        speech_key = "2fb4a8154ef84f4fbe501cc9b850bcd1"  # Replace with your Azure Speech key git
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
    except Exception as e:
        print(f"An error occurred during speech-to-text: {e}")
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

def check_health_intent(query):
    """Check if the query is health-related using basic keyword matching and OpenAI."""
    health_keywords = ["health", "symptom", "disease", "treatment", "medicine", "doctor"]
    if any(keyword in query.lower() for keyword in health_keywords):
        return True
    return get_openai_response(f"Is this query health-related? \"{query}\"").lower().startswith("yes")


def extract_text_from_adaptive_card(card):
    """Extracts text from an adaptive card content, excluding 'Source' and '_Additional names_'."""
    texts = []
    for item in card.get("body", []):
        if item.get("type") == "Container":
            for inner_item in item.get("items", []):
                if inner_item.get("type") == "TextBlock" and 'text' in inner_item:
                    text_content = inner_item['text']
                    # Exclude "Source" and "_Additional names_"
                    if not ("Source:" in text_content or "Additional names:" in text_content):
                        texts.append(text_content)
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
                if activity.get("from", {}).get("id") != "user1":  # Check for bot's response
                    if 'text' in activity:
                        return activity['text']  # Return the bot's text response

                    # Handle any attachments (e.g., rich cards or media)
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
                                    return '\n'.join(texts)  # Return the text extracted from the Adaptive Card

            # If no response was found from the Health Bot, fallback to Azure OpenAI
            print("No valid response from Health Bot. Falling back to Azure OpenAI.")
            return get_openai_response(keyword)  # Fallback to Azure OpenAI for the same keyword

        else:
            print(f"Error fetching conversation data: {response.status_code} - {response.text}")
            return "Error fetching conversation data."
    else:
        print(f"Error sending message to Health Bot: {response.status_code} - {response.text}")
        return "Error sending message to Health Bot."
 

def get_openai_response(user_query):
    """Fetches a response from Azure OpenAI for the given user query."""
    url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_MODEL}/chat/completions?api-version=2023-05-15"

    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_KEY,
    }

    payload = {
        "messages": [
            {"role": "user", "content": user_query}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            response_data = response.json()
            return response_data['choices'][0]['message']['content'].strip()
        else:
            print(f"Error in Azure OpenAI request: {response.status_code} - {response.text}")
            return "An error occurred while fetching information from Azure OpenAI."
    except Exception as e:
        print(f"Azure OpenAI request failed: {e}")
        return "An error occurred while fetching information from Azure OpenAI."

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/speech-to-text', methods=['POST'])
def handle_speech_to_text():
    # Call your speech_to_text function and return its output as JSON
    text = speech_to_text()
    return jsonify({"text": text})


@app.route('/get-health-info', methods=['POST'])
def handle_health_info():
    data = request.json
    if not data or not data.get('text'):
        return jsonify({"response": "No query provided. Please ask a health-related question."})

    token = get_direct_line_token()
    conversation_id = start_conversation(token)

    health_info = get_health_info(token, conversation_id, data['text'])

    if not health_info or "Sorry" in health_info or "I can't answer this" in health_info or "No response" in health_info:
        print("Health Bot failed, checking if the query is health-related...")
        if check_health_intent(data['text']):
            print("Query is health-related, querying OpenAI...")
            health_info = get_openai_response(data['text'])
        else:
            health_info = "This query is not health-related. Please ask a health-related question."

    return jsonify({"response": health_info})

@app.route('/text-to-speech', methods=['POST'])
def handle_text_to_speech():
    data = request.json
    text_to_speech(data['response'])
    return jsonify({"status": "done"})

# Main logic
if __name__ == "__main__":  
    app.run(debug=True)
