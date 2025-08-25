# AI-Powered Serverless Search Engine on AWS

*Note: For cost optimization, a core architectural principle, the backend OpenSearch cluster is not provisioned 24/7. The live demo can be activated upon request. Please contact me, and I can have the full stack running within 15 minutes)*

---

## Project Overview

This project is a fully serverless, AI-driven semantic search application built on AWS. It allows users to perform natural language queries on the Bhagavad Gita, returning results based on contextual meaning, not just keywords. The architecture is designed for scalability, fault tolerance, and cost-efficiency by leveraging a decoupled, microservices-based design.

## Architecture Diagram

## Key Features

-   **Semantic Search:** Utilizes a Hugging Face sentence-transformer model on Amazon SageMaker to convert text into 384-dimension vector embeddings, enabling context-aware search.
-   **Verse Browser:** A dedicated, low-latency API endpoint leverages Amazon DynamoDB for direct key-value lookup of specific verses by chapter and number.
-   **Fully Serverless API:** The user-facing application is powered by AWS Lambda and Amazon API Gateway, ensuring it scales automatically and incurs costs only upon request.
-   **Cost-Optimized Design:** Implements a multi-datastore strategy (S3, DynamoDB, OpenSearch) to use the right tool for each job. Crucially, the expensive SageMaker ML inference endpoint is decoupled and used only for the one-time data ingestion process, not for live queries.

## Technology Stack

-   **Compute:** AWS Lambda
-   **API & Networking:** Amazon API Gateway
-   **Database & Storage:** Amazon OpenSearch (for k-NN vector search), Amazon DynamoDB (for key-value metadata), Amazon S3 (for raw data and static website hosting)
-   **AI / Machine Learning:** Amazon SageMaker (for hosting the embedding model)
-   **Security & Identity:** AWS IAM
-   **Monitoring & Observability:** Amazon CloudWatch
-   **Development:** Python (Boto3, Opensearch-py), JavaScript, HTML/CSS, REST APIs

## Setup & Deployment

This project consists of a backend data pipeline and a serverless API.

### 1. Backend Data Ingestion
The data pipeline is orchestrated by the `ingestion/ingestion.py` script. It performs the following steps:
1.  Downloads raw text files from an S3 bucket.
2.  Calls a provisioned SageMaker endpoint to generate vector embeddings for each verse.
3.  Loads structured metadata into DynamoDB for fast lookups.
4.  Indexes the verses and their corresponding vectors into an Amazon OpenSearch cluster configured for k-NN search.

### 2. Serverless API & Frontend
1.  **Backend:** Two Lambda functions (`search-function` and `get-verse-function`) are deployed and fronted by a single Amazon API Gateway.
2.  **Frontend:** A static HTML/JS/CSS single-page application (`frontend/index.html`) is hosted on Amazon S3 with Static Website Hosting enabled. The JavaScript in this file makes direct calls to the deployed API Gateway endpoints.
