# ingestion.py
import boto3
import json
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
from tqdm import tqdm
import numpy as np
from requests_aws4auth import AWS4Auth
from botocore.config import Config

# =================================================================================================
# === 1. CONFIGURE YOUR RESOURCES HERE ===
# =================================================================================================
# --- AWS S3 Configuration ---
S3_BUCKET_NAME = "your-s3-bucket-for-raw-data" # <-- IMPORTANT: REPLACE with your bucket name
CANONICAL_TEXT_KEY = "your-canonical-text-on-s3.json" # <-- IMPORTANT: REPLACE
TRANSLATION_KEY = "your-translation-text-on-s3.json" # <-- IMPORTANT: REPLACE

# --- AWS DynamoDB Configuration ---
DYNAMODB_TABLE_NAME = "your-dynamodb-table-name" # <-- IMPORTANT: REPLACE with your table name

# --- AWS OpenSearch Configuration ---
OPENSEARCH_HOST = "your-opensearch-domain-endpoint" # <-- IMPORTANT: REPLACE with your OpenSearch domain endpoint
OPENSEARCH_PORT = 443
INDEX_NAME = "verses" # Name of the index to store the data

# --- AWS SageMaker Configuration ---
# NOTE: This endpoint must be deployed and running for OpenSearch ingestion to work.
SAGEMAKER_ENDPOINT_NAME = "your-sagemaker-embedding-endpoint" # <-- IMPORTANT: REPLACE 

# =================================================================================================
# === 2. INITIALIZE AWS CLIENTS ===
# =================================================================================================
# Ensure your AWS CLI is configured (aws configure)
s3_client = boto3.client('s3')
dynamodb_resource = boto3.resource('dynamodb')

# Create a config with a longer timeout
sagemaker_config = Config(
    read_timeout=300,
    connect_timeout=300,
    retries={'max_attempts': 3}
)
sagemaker_runtime = boto3.client('sagemaker-runtime', config=sagemaker_config)
# sagemaker_runtime = boto3.client('sagemaker-runtime')

# Note: For production Lambdas, it's better to use IAM roles for auth.
# For this local script, explicit credentials can be passed if needed, but CLI config is best.
service = 'es'
credentials = boto3.Session().get_credentials()
aws_auth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    'us-east-2',
    service,
    session_token=credentials.token
)

search_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
    http_auth=aws_auth, # Pass the explicit auth object
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

# =================================================================================================
# === 3. HELPER AND INGESTION FUNCTIONS ===
# =================================================================================================
def get_json_from_s3(bucket, key):
    """Downloads and parses a JSON file from S3."""
    print(f"Downloading {key} from bucket {bucket}...")
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return json.loads(response['Body'].read().decode('utf-8'))

def load_data_to_dynamodb(canonical_data, translation_data):
    """
    Loads canonical and translation data into DynamoDB using the single-table design.
    Uses BatchWriter for efficient bulk uploads.
    """
    print("\n--- Starting DynamoDB Ingestion ---")
    table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)
    text_id = canonical_data.get("textId")
    lang = translation_data.get("language")
    translator = translation_data.get("translator")

    with table.batch_writer() as batch:
        # 1. Ingest Canonical Verses
        print(f"Processing {len(canonical_data['verses'])} canonical verses for DynamoDB...")
        for verse in tqdm(canonical_data["verses"], desc="Canonical Verses"):
            pk = f"{text_id}_{verse['chapter']}_{verse['verse']}"
            item = {
                'PK': pk,
                'SK': 'C', # 'C' for Canonical
                'textId': text_id,
                'chapter': verse['chapter'],
                'verse': verse['verse'],
                'sanskritDevanagari': verse.get('sanskritDevanagari', ''),
                'sanskritTransliteration': verse.get('sanskritTransliteration', '')
            }
            batch.put_item(Item=item)

        # 2. Ingest Translation Verses
        print(f"Processing {len(translation_data['verses'])} translation verses for DynamoDB...")
        for verse in tqdm(translation_data["verses"], desc="Translation Verses"):
            pk = f"{text_id}_{verse['chapter']}_{verse['verse']}"
            sk = f"T_{lang}_{translator}" # 'T' for Translation
            item = {
                'PK': pk,
                'SK': sk,
                'textId': text_id,
                'chapter': verse['chapter'],
                'verse': verse['verse'],
                'language': lang,
                'translator': translator,
                'translationText': verse.get('translationText', '')
            }
            batch.put_item(Item=item)
    print("--- DynamoDB Ingestion Complete ---")


def load_data_to_opensearch(canonical_data, translation_data):
    """
    Merges canonical and translation data, gets embeddings, and bulk-uploads to OpenSearch.
    """
    print("\n--- Starting OpenSearch Ingestion ---")
    
    # Create an efficient lookup map for translations
    translations_map = {
        f"{v['chapter']}_{v['verse']}": v.get("translationText", "")
        for v in translation_data.get("verses", [])
    }
    
    # Use the bulk helper for efficient indexing
    print("Generating embeddings and indexing documents for OpenSearch...")
    try:
        success, failed = bulk(
            search_client, 
            generate_opensearch_actions(canonical_data, translations_map),
            chunk_size=100,
            request_timeout=200
        )
        print(f"Successfully indexed {success} documents in OpenSearch.")
        if failed:
            print(f"Failed to index {len(failed)} documents in OpenSearch.")
    except Exception as e:
        print(f"An error occurred during OpenSearch bulk indexing: {e}")
    print("--- OpenSearch Ingestion Complete ---")

def get_embedding(text, endpoint_name):
    """
    Invokes the SageMaker endpoint, which returns token-level embeddings.
    This function then performs mean pooling to create a single sentence-level embedding.
    """
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=json.dumps({"inputs": [text]})
    )
    response_body = json.loads(response['Body'].read().decode('utf-8'))
    token_vectors = response_body[0][0]
    vector_array = np.array(token_vectors)
    sentence_vector = np.mean(vector_array, axis=0)
    return sentence_vector.tolist()

def generate_opensearch_actions(canonical_data, translations_map):
    """Generator function to yield documents for OpenSearch bulk indexing."""
    text_id = canonical_data.get("textId", "UNKNOWN")
    
    for verse_data in tqdm(canonical_data.get("verses", []), desc="OpenSearch Docs"):
        try: # <--- ADD THIS
            chapter = verse_data.get("chapter")
            verse = verse_data.get("verse")
            doc_id = f"{text_id}_{chapter}_{verse}"

            if not chapter or not verse:
                continue

            verse_key = f"{chapter}_{verse}"
            translation_text = translations_map.get(verse_key, "")
            
            text_to_embed = f"Verse: {verse_data.get('sanskritTransliteration', '')}. Translation: {translation_text}"
            
            # This is the most likely point of failure
            embedding = get_embedding(text_to_embed, SAGEMAKER_ENDPOINT_NAME)

            doc = {
                'textId': text_id,
                'chapter': chapter,
                'verse': verse,
                'sanskritTransliteration': verse_data.get('sanskritTransliteration', ''),
                'translation_en': translation_text,
                'verse_vector': embedding
            }
            
            yield {
                "_index": INDEX_NAME,
                "_id": doc_id,
                "_source": doc,
            }
        except Exception as e: # <--- ADD THIS
            print(f"\n!!!!!! FAILED TO PROCESS DOCUMENT ID: {doc_id} !!!!!!") # <--- ADD THIS
            print(f"ERROR: {e}\n") # <--- ADD THIS
            continue # <--- ADD THIS (tells the loop to skip to the next item)

# =================================================================================================
# === 4. MAIN EXECUTION LOGIC ===
# =================================================================================================
def main():
    """Main ingestion logic."""
    print("Starting data ingestion process...")
    
    # 1. Download data from S3
    canonical_data = get_json_from_s3(S3_BUCKET_NAME, CANONICAL_TEXT_KEY)
    translation_data = get_json_from_s3(S3_BUCKET_NAME, TRANSLATION_KEY)
    
    # 2. Load data into DynamoDB
    load_data_to_dynamodb(canonical_data, translation_data)

    # 3. Load data into OpenSearch
    # Make sure your SageMaker endpoint is running before uncommenting/running this!
    load_data_to_opensearch(canonical_data, translation_data)

    print("\nIngestion process finished.")

if __name__ == "__main__":
    main()