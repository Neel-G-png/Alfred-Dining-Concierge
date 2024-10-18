import time
import os
import logging
import json
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import re
from dotenv import load_dotenv
import os

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

dynamodb = boto3.resource('dynamodb')


def get_slots(intent_request):
    return intent_request['sessionState']['intent']['slots']

def get_slot(intent_request, slot_name):
    slots = get_slots(intent_request)
    if slots and slot_name in slots and slots[slot_name] and 'value' in slots[slot_name]:
        return slots[slot_name]['value']['interpretedValue']
    return None

def push_to_sqs(QueueURL, message, sessionAttributes):
    sqs = boto3.client('sqs', region_name='us-east-1')
    try:
        response = sqs.send_message(
            QueueUrl=QueueURL,
            DelaySeconds=0,
            MessageAttributes={
                'sessionAttributes': {
                    'DataType': 'String',
                    'StringValue': json.dumps(sessionAttributes)
                },
                'sessionId': {
                    'DataType': 'String',
                    'StringValue': message['sessionId']
                },
                'Cuisine': {
                    'DataType': 'String',
                    'StringValue': message['Cuisine']
                },
                'location': {
                    'DataType': 'String',
                    'StringValue': message['location']
                },
                'email': {
                    'DataType': 'String',
                    'StringValue': message['email']
                },
                'diningTime': {
                    'DataType': 'String',
                    'StringValue': message['diningTime']
                },
                'NumberOfGuests': {
                    'DataType': 'Number',
                    'StringValue': message['NumberOfGuests']
                }
            },
            MessageBody=json.dumps(message)
        )
        

    except ClientError as e:
        logging.error(e)
        return None
    return response

def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'ElicitSlot',
                'slotToElicit': slot_to_elicit
            },
            'intent': {
                'name': intent_name,
                'slots': slots,
                'state': 'InProgress'
            },
            'sessionAttributes': session_attributes
        },
        'messages': [message]
    }

def build_validation_result(is_valid, violated_slot, message_content):
    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {
            'contentType': 'PlainText',
            'content': message_content
        }
    }

def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

def validate_parameters(dining_time, cuisine_type, location, num_people, email_addr):
    # Valid locations and cuisines
    valid_locations = ['manhattan', 'new york', 'nyc']
    valid_cuisines = ['indian', 'italian', 'mexican']
    
    # Validate email address
    if not email_addr:
        return build_validation_result(False, 'email', 'Please provide your email address.')
    elif not is_valid_email(email_addr):
        return build_validation_result(False, 'email', 'Please provide a valid email address.')

    # Validate location
    if not location:
        return build_validation_result(False, 'location', 'What city or city area are you looking to dine in?')
    elif location.lower() not in valid_locations:
        return build_validation_result(False, 'location', 'Please provide a valid city (New York, Manhattan, or NYC).')

    # Validate cuisine type
    if not cuisine_type:
        return build_validation_result(False, 'Cuisine', 'What type of cuisine would you like to try?')
    elif cuisine_type.lower() not in valid_cuisines:
        return build_validation_result(False, 'Cuisine', f'Sorry, we do not support {cuisine_type}. Please select from Italian, Mexican, or Indian.')

    # Validate dining time
    if not dining_time:
        return build_validation_result(False, 'diningTime', 'At what time would you prefer to dine? Please provide a valid dining time(xx am/pm).')

    # Validate number of guests
    if not num_people:
        return build_validation_result(False, 'NumberOfGuests', 'How many people will be dining with you?')
    elif not num_people.isdigit() or int(num_people) <= 0:
        return build_validation_result(False, 'NumberOfGuests', 'Please provide a valid number of guests greater than zero.')

    

    # If all validations pass
    return build_validation_result(True, None, None)


def get_restaurants(intent_request):
    slots = get_slots(intent_request)
    source = intent_request['invocationSource']

    if source == 'DialogCodeHook':
        # Extract slot values
        email_addr = get_slot(intent_request, 'email')
        location = get_slot(intent_request, 'location')
        cuisine = get_slot(intent_request, 'Cuisine')
        dining_time = get_slot(intent_request, 'diningTime')
        num_people = get_slot(intent_request, 'NumberOfGuests')
        use_history = get_slot(intent_request, 'use_history')
        
        #If we have a valid email address we will check for the email id in the Dynamodb for recent suggestions
        table = dynamodb.Table("session_history")
        user_history = table.query(KeyConditionExpression=Key('sessionId').eq(intent_request['sessionId']))
        if user_history['Count'] and not use_history:
            print(f"Your History {user_history}")
            return elicit_slot(
                            intent_request['sessionState'].get('sessionAttributes', {}),
                           intent_request['sessionState']['intent']['name'],
                           slots,
                           'use_history',
                           {'contentType': 'PlainText','content': 'Welcome back!! Are you in for the usual?'}


        if email_addr and is_valid_email(email_addr) and not use_history:
            table = dynamodb.Table("history")
            user_history = table.query(KeyConditionExpression=Key('email_id').eq(email_addr))
            if user_history['Count']:
                return elicit_slot(
                                intent_request['sessionState'].get('sessionAttributes', {}),
                               intent_request['sessionState']['intent']['name'],
                               slots,
                               'use_history',
                               {'contentType': 'PlainText','content': 'Welcome back!! Are you in for the usual?'}
                               )
            else:
                #No History available
                pass
        if use_history == 'Yes' and not email_addr:
            table = dynamodb.Table("session_history")
            user_history = table.query(KeyConditionExpression=Key('sessionId').eq(intent_request['sessionId']))['Items'][0]
            last_loc = user_history['location']
            last_cuisine = user_history['cuisine']
            last_dining_time = user_history['time']
            last_party_size = user_history['party_size']
            last_sessionId = user_history['sessionId']
            last_email = user_history['email_id']
            
            slot_dict = {
                    'diningTime': last_dining_time,
                    'Cuisine': last_cuisine,
                    'location': last_loc,
                    'NumberOfGuests': last_party_size,
                    'email': last_email,
                    'email': email_addr
                    'sessionId':last_sessionId
                }
        if use_history == 'Yes' and email_addr:
            table = dynamodb.Table("session_history")
            user_history = table.scan(KeyConditionExpression=Key('sessionId').eq(intent_request['sessionId']))['Items'][0]
            last_loc = user_history['location']
            last_cuisine = user_history['cuisine']
            last_dining_time = user_history['time']
            last_party_size = user_history['party_size']
            last_sessionId = user_history['sessionId']
            last_email = user_history['email_id']
            
            slot_dict = {
                    'diningTime': last_dining_time,
                    'Cuisine': last_cuisine,
                    'location': last_loc,
                    'NumberOfGuests': last_party_size,
                    'email': last_email,
                    'sessionId':last_sessionId
                }
    

            # Send data to SQS queue
            res = push_to_sqs(os.getenv("sqs_url"),
                      slot_dict, intent_request['sessionState'].get('sessionAttributes', {}))
            
            text = f"Awesome! Sending recommendations based on your last choice. Cuisine: {last_cuisine} and Location: {last_loc}"
            
            #User wants to get recommendation based on usual choices
            response = {
                    'sessionState': {
                        'dialogAction': {
                            'type': 'Close'
                        },
                        'intent': {
                            'name': intent_request['sessionState']['intent']['name'],
                            'slots': intent_request['sessionState']['intent']['slots'],
                            'state': 'Fulfilled'
                        },
                        'sessionAttributes': intent_request['sessionState'].get('sessionAttributes', {})
                    },
                    'messages': [{
                        'contentType': 'PlainText',
                        'content': text
                    }],
                    'sessionId': intent_request['sessionId']
                }
            return response
            

        # Validate the inputs
        validation_result = validate_parameters(dining_time, cuisine, location, num_people, email_addr)

        if not validation_result['isValid']:
            # Set the invalid slot to None to re-prompt the user
            slots[validation_result['violatedSlot']] = None
            # Elicit the invalid slot again
            return elicit_slot(intent_request['sessionState'].get('sessionAttributes', {}),
                               intent_request['sessionState']['intent']['name'],
                               slots,
                               validation_result['violatedSlot'],
                               validation_result['message'])

        # If all slots are valid, continue to fulfillment
        intent_request['sessionState']['intent']['state'] = 'ReadyForFulfillment'
        # return {
        #     'sessionState': intent_request['sessionState'],
        #     'messages': []
        # }

    # elif source == 'FulfillmentCodeHook':
        # Fulfill the intent after validation
        # Prepare the message for SQS
    slot_dict = {
        'diningTime': dining_time,
        'Cuisine': cuisine,
        'location': location,
        'NumberOfGuests': num_people,
        'email': email_addr,
        'sessionId':intent_request['sessionId']
    }
    

    # Send data to SQS queue
    res = push_to_sqs(os.getenv("sqs_url"),
                      slot_dict, intent_request['sessionState'].get('sessionAttributes', {}))

    # Build fulfillment message
    if res:
        text = f"You're all set! Expect my recommendations at {email_addr} for your group of {num_people} to dine at {dining_time} in {location}!"
    else:
        text = "Sorry, there was an error processing your request. Please try again later."

    # Construct the close response
    response = {
        'sessionState': {
            'dialogAction': {
                'type': 'Close'
            },
            'intent': {
                'name': intent_request['sessionState']['intent']['name'],
                'slots': intent_request['sessionState']['intent']['slots'],
                'state': 'Fulfilled'
            },
            'sessionAttributes': intent_request['sessionState'].get('sessionAttributes', {})
        },
        'messages': [{
            'contentType': 'PlainText',
            'content': text
        }],
        'sessionId': intent_request['sessionId']
    }
    return response

def dispatch(intent_request):
    intent_name = intent_request['sessionState']['intent']['name']
    if intent_name == 'DiningSuggestionsIntent':
        return get_restaurants(intent_request)
    else:
        raise Exception(f"Intent {intent_name} not supported")

def lambda_handler(event, context):
    return dispatch(event)
