# lambda_function.py
import json
import boto3
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# --- Environment Variables ---

OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']
SAGEMAKER_ENDPOINT = os.environ['SAGEMAKER_ENDPOINT']
AWS_REGION = os.environ['AWS_REGION']
INDEX_NAME = "verses"

# --- AWS Clients (initialized outside the handler for reuse) ---
sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=AWS_REGION)

# Set up the explicit IAM authentication for OpenSearch
service = 'es'
credentials = boto3.Session().get_credentials()
aws_auth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    AWS_REGION,
    service,
    session_token=credentials.token
)
search_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
    http_auth=aws_auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def get_embedding(text, endpoint_name):
    """Gets a vector embedding for a given text from SageMaker."""
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=json.dumps({"inputs": [text]})
    )
    response_body = json.loads(response['Body'].read().decode('utf-8'))
    token_vectors = response_body[0][0]
    # Mean pooling
    sentence_vector = [float(sum(col)) / len(col) for col in zip(*token_vectors)]
    return sentence_vector

def lambda_handler(event, context):
    """Main Lambda handler function."""
    print(f"Received event: {event}")
    
    # 1. Get the search query from the request
    try:
        query_text = event['queryStringParameters']['q']
        if not query_text:
            raise KeyError
    except (TypeError, KeyError):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Query parameter "q" is missing or empty.'})
        }
        
    try:
        # 2. Get the vector embedding for the search query
        query_vector = get_embedding(query_text, SAGEMAKER_ENDPOINT)
        
        # 3. Build and execute the k-NN search query on OpenSearch
        knn_query = {
            "size": 5,
            "_source": ["textId", "chapter", "verse", "sanskritTransliteration", "translation_en"],
            "query": {
                "knn": {
                    "verse_vector": {
                        "vector": query_vector,
                        "k": 5
                    }
                }
            }
        }
        
        response = search_client.search(
            index=INDEX_NAME,
            body=knn_query
        )
        
        # 4. Format the results
        results = [hit['_source'] for hit in response['hits']['hits']]
        
        # 5. Return the results in the correct API Gateway format
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # Allow cross-origin requests
            },
            'body': json.dumps(results)
        }
        
    except Exception as e:
        print(f"ERROR: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'An internal server error occurred.'})
        }