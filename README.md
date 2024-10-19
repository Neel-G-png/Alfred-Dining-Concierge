# Dining Concierge Chatbot Project with OpenSearch

## Overview
This project implements a **Dining Concierge Chatbot** using AWS services such as Lex, Lambda, SQS, DynamoDB, **Amazon OpenSearch**, and **SES**. The chatbot collects user dining preferences and provides restaurant recommendations based on the inputs. The project features an API-driven architecture, asynchronous processing of dining requests, and email notifications for recommendations.

## Features
- **AWS Lex Chatbot**: Collects user preferences (location, cuisine, dining time, etc.) via conversation.
- **API Gateway and Lambda**: Manages API-driven communication between the chatbot and backend services.
- **DynamoDB**: Stores restaurant data and user interaction history.
- **SQS**: Queues dining requests for asynchronous processing.
- **Amazon OpenSearch**: Stores restaurant IDs and cuisines for quick filtering and recommendations.
- **SES (Simple Email Service)**: Sends restaurant recommendations via email.
- **EventBridge Scheduler**: Triggers Lambda to process queued requests regularly.

---

## Project Structure

1. **Frontend**:
   - Hosted on AWS S3 as a static website.
   - Interacts with the chatbot API.

2. **API and Backend**:
   - **API Gateway**: Handles API requests to the chatbot.
   - **Lambda Functions**:
     - `LF0`: Receives API requests and forwards the user input to Lex.
     - `LF1`: Handles Lex intent processing, collects dining preferences, and queues requests to SQS.
     - `LF2`: Processes messages from SQS, fetches restaurant recommendations, and sends emails via SES. Triggered by **EventBridge Scheduler**.

3. **Chatbot (Amazon Lex)**:
   - **Intents**:
     - `GreetingIntent`: Greets the user.
     - `ThankYouIntent`: Responds to thank-you messages.
     - `DiningSuggestionsIntent`: Collects user preferences (location, cuisine, dining time, etc.).

4. **Database (DynamoDB)**:
   - Stores restaurant data and user interaction history for future reference.

5. **Queueing System (SQS)**:
   - Asynchronously queues user dining requests for processing by Lambda.

6. **Amazon OpenSearch**:
   - Stores restaurant IDs and cuisines for quick lookup by the Lambda function.

7. **Email Notifications (SES)**:
   - Sends restaurant recommendations to users via email based on their preferences.

8. **EventBridge Scheduler**:
   - Triggers **LF2** Lambda function periodically to process SQS messages and send recommendations via email.

---

## Lambda Functions

### `LF0`: API Request Handler
- Receives API requests and forwards user input to Lex.
- Forwards responses from Lex back to the client.

### `LF1`: Lex Intent Handler
- Handles the intents from Lex, such as `DiningSuggestionsIntent`.
- Collects user inputs (location, cuisine, dining time, email, etc.).
- Pushes the data to SQS for further processing by another Lambda.

### `LF2`: SQS Queue Processor
- Polls SQS for user requests.
- Fetches restaurant recommendations from OpenSearch and DynamoDB.
- Sends restaurant recommendations via SES to the user's email.
- Triggered by **EventBridge Scheduler** every minute to process new requests in SQS.

---

## Useful Links

- [Amazon Lex Documentation](https://docs.aws.amazon.com/lex/latest/dg/getting-started.html)
- [Amazon S3 Static Website Hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html)
- [Amazon DynamoDB Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html)
- [Amazon OpenSearch Documentation](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html)
- [Amazon SES Documentation](https://docs.aws.amazon.com/ses/latest/DeveloperGuide/Welcome.html)
- [Amazon EventBridge Scheduler Documentation](https://docs.aws.amazon.com/eventbridge/latest/userguide/scheduler.html)

---