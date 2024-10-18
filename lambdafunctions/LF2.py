import random
import logging
import boto3
import json
from botocore.exceptions import ClientError
from opensearchpy import OpenSearch
import requests
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv
import os

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def get_sqs_client():
    sqs = boto3.client('sqs', region_name='us-east-1')
    queue_URL = sqs.get_queue_url(QueueName=os.getenv("sqs_name"))
    return sqs, queue_URL
    
def delete_sqs_msg(sqs, queue_URL, msg):
    try:
        sqs.delete_message(
            QueueUrl=queue_URL['QueueUrl'], ReceiptHandle=msg['ReceiptHandle']
        )
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": e})
        }
    return "successful"
    
def get_sqs_data(sqs, queue_URL):
    try:
        response = sqs.receive_message(
            QueueUrl=queue_URL['QueueUrl'],
            AttributeNames=['All'],
            MessageAttributeNames=['All'],
            MaxNumberOfMessages=10,
            VisibilityTimeout=3,
            WaitTimeSeconds=5
        )
        polled_msgs = []
        if "Messages" in response:
            for msg in response['Messages']:
                polled_msgs.append({
                    "MessageAttributes": msg['MessageAttributes'],
                    "ReceiptHandle": msg['ReceiptHandle']
                })

        return polled_msgs

    except ClientError as e:
        logging.error(e)
        return []

def get_os_client():
    host = os.getenv("opensearch_host")
    port = 443
    auth = (os.getenv("opensearch_username"), os.getenv("opensearch_password")) 
    client = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_auth=auth, 
        use_ssl=True,
        verify_certs=True,
        ssl_assert_hostname=False,
        ssl_show_warn=False
    )
    return client

def save_history(dynamodb, user_slots):
    email, cuisine, location, time, party_size, sessionId  = user_slots
    try:
        hist_table = dynamodb.Table("session_history")
        hist_table.put_item(Item = {
            "email_id" : email,
            "cuisine" : cuisine,
            "location" : location,
            "time" : time,
            "party_size" : party_size,
            "sessionId" : sessionId
        })

    except ClientError as e:
        print("Error occurred:", e.response['Error']['Message'])

def lambda_handler(event, context):
    # Initialize SQS Client
    sqs, queue_URL = get_sqs_client()
    
    # Initialize OpenSearch Client
    client = get_os_client()
    
    # Poll msgs from sqs
    sqs_messages = get_sqs_data(sqs, queue_URL)
    
    # Initialize dynamodb client and ses client
    dynamodb = boto3.resource('dynamodb')
    sesClient = boto3.client('ses', region_name='us-east-1')
    table = dynamodb.Table("yelp-restaurants")
    
    # Loop over all the msgs 
    for msg in sqs_messages:
        # Get user slots
        cuisine = msg['MessageAttributes']['Cuisine']['StringValue']
        location = msg['MessageAttributes']['location']['StringValue']
        time = msg['MessageAttributes']['diningTime']['StringValue']
        email = msg['MessageAttributes']['email']['StringValue']
        party_size = msg['MessageAttributes']['NumberOfGuests']['StringValue']
        sessionId = msg['MessageAttributes']['sessionId']['StringValue']
        
        #saving preference in history table in Dynamodb
        save_history(dynamodb, (email, cuisine, location, time, party_size, sessionId))
        
        
        index_name = 'restaurants'
        try:
            res = client.search(
                index=index_name,
                body={
                    "query": {
                        "match": {"Cuisine" : cuisine}
                    }
                }
            )

            data = res
            hits = data["hits"]["hits"]
            if not hits:
                raise Exception("No Recommendations Found!!!")
            business_id = [hit['_id'] for hit in hits]
            
            random.shuffle(business_id)
            
            res0 = table.query(
                    KeyConditionExpression=Key('BusinessID').eq(business_id[0])
                )
            res1 = table.query(
                    KeyConditionExpression=Key('BusinessID').eq(business_id[1])
                )
            res2 = table.query(
                    KeyConditionExpression=Key('BusinessID').eq(business_id[2])
                )
            item0 = res0.get('Items', {})
            item1 = res1.get('Items', {})
            item2 = res2.get('Items', {})


            # Deleting the msg from queue right before sending the email
            delete_sqs_msg(sqs, queue_URL,msg)

            emailText = """
                Hello!\n
                Here are my %s restaurant suggestions for %s people, at %s: \n
                1. %s, located at %s, %s, %s \n
                2. %s, located at %s, %s, %s \n
                3. %s, located at %s, %s, %s.\n
                Enjoy your meal!""" % (
                        cuisine, 
                        party_size, 
                        time, 
                        item0[0]["Name"], 
                        item0[0]["Address"], item0[0]["City"], item0[0]["State"], 
                        item1[0]["Name"], 
                        item1[0]["Address"], item0[0]["City"], item0[0]["State"],
                        item2[0]["Name"], 
                        item2[0]["Address"], item0[0]["City"], item0[0]["State"]
                    )

            sesClient.send_email(
                    Destination={
                        'ToAddresses': [
                                email
                            ]
                    },
                    Message={
                        'Body': {'Text': {'Data': emailText}},
                        'Subject': {'Data': 'Restaurant recommendations'}
                    },
                    Source=os.getenv('source_email_id')
                )
            return "Suggestions would be sent to your Email in sometime!!!"
        except Exception as e:
            print(e)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Error"})
            }