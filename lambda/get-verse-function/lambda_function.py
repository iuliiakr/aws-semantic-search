import json
import boto3
import os

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'your-dynamodb-table-name') # Set your table name here
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    Fetches a specific verse (canonical and translation) from DynamoDB.
    """
    try:
        # Get the verse ID from the path parameter (e.g., "BG_1_5")
        verse_id = event['pathParameters']['id']
        
        # Query DynamoDB for all items with that Primary Key (PK)
        # This will get the canonical verse (SK='C') and all translations
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq(verse_id)
        )
        
        items = response.get('Items', [])
        
        if not items:
            return {
                'statusCode': 404,
                'headers': {
                    'Access-Control-Allow-Origin': '*', # Enable CORS
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'OPTIONS,GET'
                },
                'body': json.dumps({'error': 'Verse not found'})
            }
        
        # Process the results into a more friendly format
        result = {
            'id': verse_id,
            'canonical': None,
            'translations': []
        }
        for item in items:
            if item.get('SK') == 'C':
                result['canonical'] = {
                    'sanskritDevanagari': item.get('sanskritDevanagari'),
                    'sanskritTransliteration': item.get('sanskritTransliteration')
                }
            elif item.get('SK', '').startswith('T_'):
                result['translations'].append({
                    'language': item.get('language'),
                    'translator': item.get('translator'),
                    'text': item.get('translationText')
                })
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*', # Enable CORS
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,GET'
            },
            'body': json.dumps(result)
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*', # Enable CORS
            },
            'body': json.dumps({'error': 'An internal server error occurred.'})
        }