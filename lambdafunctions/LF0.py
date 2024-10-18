import json
import uuid
import boto3
import logging
from datetime import datetime
from dotenv import load_dotenv
import os


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def get_lex_reply(session_id, user_input):
    client = boto3.client('lexv2-runtime')
    
    # Set your Lex V2 bot details
    bot_id = os.getenv('bot_id')
    bot_alias_id = os.getenv('bot_alias_id')
    locale_id = os.getenv('locale_id')
    
    try:
        # Call the Lex V2 bot
        response = client.recognize_text(
            botId=bot_id,
            botAliasId=bot_alias_id,
            localeId=locale_id,
            sessionId=session_id,  # Use dynamic session ID
            text=user_input
        )
        
        # Extract the bot's response
        bot_response = response['messages'][0]['content'] if response['messages'] else 'No response from bot'
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'bot_response': bot_response,
                'intent': response.get('sessionState', {}).get('intent', {}).get('name', 'No intent detected')
            })
        }
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def lambda_handler(event, context):
    # Generate or retrieve a unique session ID (e.g., use user ID if available)
    # If there's no session ID in the event, create a new one
    session_id = event['messages'][0]['unstructured'].get('sessionId', str(uuid.uuid4()))  # Use existing session ID or generate a new one
    print(f"This is from frontend: {event}")
    user_input = event['messages'][0]['unstructured']['text']
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    # Get Lex's response using the dynamic session ID
    lex_reply = get_lex_reply(session_id, user_input)

    # Parse Lex's response
    lex_reply = json.loads(lex_reply['body'])
    
    response = {
        "messages": [
            {
                "type": "unstructured",
                "unstructured": {
                    "id": session_id,  # Use session_id instead of unique_id
                    "text": lex_reply['bot_response'],
                    "timestamp": timestamp
                }
            }
        ]
    }

    # Log the response for debugging
    print("Response Body:", response)

    return response
