import os
import json

from langchain_openai import AzureOpenAIEmbeddings
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from pinecone import Pinecone
import cohere

from dotenv import load_dotenv


from openai import AzureOpenAI


from ariel_prompting import (
    query_few_shots,
    query_system_template,
    response_few_shots,
    response_system_template,
)

load_dotenv()


class AzureEmbeddings:

    def __init__(self):
        pass

    @staticmethod
    def get_embedding():
        return AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("OPENAI_AZURE_DEPLOYMENT"),
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            azure_endpoint=os.getenv("OPEN_AI_AZURE_URL"),
        )

    @staticmethod
    def generate_embeddings(content: str):
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("OPENAI_AZURE_DEPLOYMENT"),
            openai_api_version="2023-08-01-preview",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            azure_endpoint=os.getenv("OPEN_AI_AZURE_URL"),
        )

        doc_result = embeddings.embed_documents([content])

        return doc_result[0]


openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

print("Azure SSN ", os.getenv("AZURE_COGNITIVE_SEARCH_SERVICE_NAME"))

embeddings_client = AzureEmbeddings()
store_search_url: str = (
    f"https://{os.getenv('AZURE_COGNITIVE_SEARCH_SERVICE_NAME')}.search.windows.net"
)
search_client = SearchClient(
    store_search_url,
    os.getenv("AZURE_COGNITIVE_SEARCH_INDEX_NAME"),
    AzureKeyCredential(os.getenv("AZURE_COGNITIVE_SEARCH_API_KEY")),
)

pinecone_client = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pinecone_client.Index(os.getenv("PINECONE_API_INDEX"))
co = cohere.Client(os.getenv("COHERE_API_KEY"))


def get_query(user_input):
    query_user_content_template = f"Generate search query for: {user_input}"
    query_messages = [
        {"role": "system", "content": query_system_template},
        *query_few_shots,
        {"role": "user", "content": query_user_content_template},
    ]

    query = (
        openai_client.chat.completions.create(
            messages=query_messages,
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            temperature=0.0,
            n=1,
        )
        .choices[0]
        .message.content
    )
    query_vectors = embeddings_client.generate_embeddings(content=query)

    return {"query_vectors": query_vectors, "query_text": query}


def get_answer_azure(user_input):
    print("")
    print("Azure ask - User Input:", user_input)
    
    query = get_query(user_input)
    query_vectors = query["query_vectors"]
    query_text = query["query_text"]
    print("Query for: ", query_text)
    results = search_client.search(
        search_text=query_text,
        top=5,
        query_type=QueryType.SEMANTIC,
        vector_queries=[
            {
                "vector": query_vectors,
                "k": 5,
                "fields": "content_vector",
                "kind": "vector",
                "exhaustive": True,
            }
        ],
        semantic_configuration_name="default",
        query_caption="extractive|highlight-false",
        scoring_profile="none",
        # scoring_profile="legal",
        # scoring_parameters=[
        #     "tagx6-Constitucional",
        #     "tagx5-Legal",
        #     "tagx4-Infralegal",
        #     "tagx3-Jurisprudencia",
        #     "tagx2-Doctrina",
        # ],
    )

    documents = []
    for page in results.by_page():
        for document in page:
            doc = {
                "id": document["id"],
                "content": document["content"],
                "title": document["title"],
                "author": document["author"],
                "category": document["category"],
                "year": document["year"],
            }
            documents.append(doc)

    response_user_content_template = f"{user_input} Sources: {documents}"

    response_messages = [
        {"role": "system", "content": response_system_template},
        *response_few_shots,
        {"role": "user", "content": response_user_content_template},
    ]

    response = {
        "content": (
            openai_client.chat.completions.create(
                messages=response_messages,
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                temperature=0.2,
                n=1,
            )
            .choices[0]
            .message.content
        ),
        "sources": documents,
    }

    return response


def get_answer_pinecone(user_input):
    print("")
    print("Pinecone ask - User Input:", user_input)

    query = get_query(user_input)
    query_vectors = query["query_vectors"]
    print("Query for: ", query["query_text"])
    query_response = pinecone_index.query(
        namespace=os.getenv("PINECONE_NAMESPACE"),
        vector=query_vectors,
        top_k=100,
        include_values=True,
        include_metadata=True,
    )

    documents = []
    for result in query_response.matches:
        print(result.id, " - ", result.score)
        documents.append(
            str(
                {
                    "id": result.get("id"),
                    "title": result.metadata.get("title"),
                    "category": result.metadata.get("category"),
                    "year": result.metadata.get("year"),
                    "author": result.metadata.get("author"),
                    "content": result.metadata.get("content"),
                }
            )
        )

    reranked_docs = co.rerank(
        model="rerank-multilingual-v3.0",
        query=user_input,
        documents=documents,
        top_n=5,
        return_documents=True,
    )

    query_formatted = []
    for result in reranked_docs.results:
        query_formatted.append(result.document.text)

    response_user_content_template = f"{user_input} Sources: {query_formatted}"

    response_messages = [
        {"role": "system", "content": response_system_template},
        *response_few_shots,
        {"role": "user", "content": response_user_content_template},
    ]

    response = {
        "content": (
            openai_client.chat.completions.create(
                messages=response_messages,
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                temperature=0.2,
                n=1,
            )
            .choices[0]
            .message.content
        ),
        "sources": query_formatted,
    }

    return response
