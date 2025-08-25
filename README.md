# AI-Powered Serverless Search Engine on AWS

*Note: For cost optimization, a core architectural principle, the backend OpenSearch cluster is not provisioned 24/7. The live demo can be activated upon request. Please contact me, and I can have the full stack running within 15 minutes)*

---

## Project Overview

This project is a fully serverless, AI-driven semantic search application built on AWS. It allows users to perform natural language queries on the Bhagavad Gita, returning results based on contextual meaning, not just keywords. The architecture is designed for scalability, fault tolerance, and cost-efficiency by leveraging a decoupled, microservices-based design.

## Architecture Diagram

```mermaid
graph TD
    subgraph "Live Query Flow (Serverless API)"
        direction LR
        User([<img src='https://i.imgur.com/s40QJj5.png' width='50' /><br/>User Browser]) --> S3_Frontend
        
        subgraph "Frontend"
            S3_Frontend["<img src='https://i.imgur.com/LdF5y3z.png' width='50' /><br/>Static Website<br/>(on Amazon S3)"]
        end

        subgraph "API Layer"
             APIGW["<img src='https://i.imgur.com/A65w6J8.png' width='50' /><br/>Amazon API Gateway"]
        end
        
        subgraph "Compute & Logic"
            Lambda_Search["<img src='https://i.imgur.com/uT3OiOF.png' width='50' /><br/>Search Lambda"]
            Lambda_Verse["<img src='https://i.imgur.com/uT3OiOF.png' width='50' /><br/>GetVerse Lambda"]
        end
        
        subgraph "Data Layer"
            OpenSearch["<img src='https://i.imgur.com/8Qpgy6a.png' width='50' /><br/>Amazon OpenSearch<br/>(k-NN Index)"]
            DDB["<img src='https://i.imgur.com/w108cWD.png' width='50' /><br/>Amazon DynamoDB<br/>(Verse Metadata)"]
        end
        
        S3_Frontend --> APIGW
        APIGW -- "GET /search?q=..." --> Lambda_Search
        APIGW -- "GET /verse/{id}" --> Lambda_Verse
        Lambda_Search --> OpenSearch
        Lambda_Verse --> DDB
    end

    subgraph "Data Ingestion Flow (One-Time Process)"
        direction TD
        Developer([<img src='https://i.imgur.com/6U4t9H5.png' width='50' /><br/>Developer/CI-CD]) --> IngestionScript
        
        subgraph "Compute & Orchestration"
            IngestionScript["<img src='https://i.imgur.com/z4AnSwh.png' width='50' /><br/>ingestion.py"]
        end
        
        subgraph "AI / ML"
            SageMaker["<img src='https://i.imgur.com/C3eG4ms.png' width='50' /><br/>Amazon SageMaker<br/>(Embedding Model)"]
        end
        
        S3_Raw["<img src='https://i.imgur.com/LdF5y3z.png' width='50' /><br/>S3 Bucket<br/>(Raw JSON Data)"] --> IngestionScript
        IngestionScript -- "1. Get Text"
        IngestionScript -- "2. Generate Vector" --> SageMaker
        SageMaker -- "3. Return Vector" --> IngestionScript
        IngestionScript -- "4a. Write Index + Vector" --> OpenSearch
        IngestionScript -- "4b. Write Metadata" --> DDB
    end

    classDef default fill:#fff,stroke:#333,stroke-width:2px;
```

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
