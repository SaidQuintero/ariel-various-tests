import os
import json
import re
from datetime import datetime
import hashlib

from langchain_openai import AzureOpenAIEmbeddings
from openai import OpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from azure.search.documents._generated.models import QueryCaptionResult

from openai import AzureOpenAI
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from dotenv import load_dotenv
from ariel_prompting import (
    query_schema,
    query_system_template,
    selected_sources_schema,
    selection_system_prompt,
    response_system_template
    )

load_dotenv()

messages = []
conversation = []
user_input = ""

class AzureEmbeddings:

    def __init__(self):
        pass
    @staticmethod
    def get_embedding():
        return AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"), 
            openai_api_version="2023-08-01-preview",
            openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_URL")
        )

    @staticmethod
    def generate_embeddings(content: str):
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"), 
            openai_api_version="2023-08-01-preview",
            openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_URL")
        )

        doc_result = embeddings.embed_documents([content])

        return doc_result[0]

    
openai_client = wrap_openai(OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
    ))

embeddings_client = AzureEmbeddings()
store_search_url: str = f'https://{os.getenv('AZURE_COGNITIVE_SEARCH_SERVICE_NAME')}.search.windows.net'
search_client = SearchClient(
            store_search_url, os.getenv("AZURE_COGNITIVE_SEARCH_INDEX_NAME"),
            AzureKeyCredential(os.getenv("AZURE_COGNITIVE_SEARCH_API_KEY"))
        )

log_file_name = ""

def ensure_directory(directory_name):
    if not os.path.exists(directory_name):
        os.makedirs(directory_name)


def log(message):
    global log_file_name
    ensure_directory("logs")
    with open(log_file_name, "a") as file:
        file.write(f"{datetime.now()}\n{message}\n")
        
conversation_price = 0
conversation_ct = 0
conversation_pt = 0
conversation_tt = 0


def get_conversation_price(new_completion, model="gpt4o"):
    global conversation_price, conversation_ct, conversation_pt, conversation_tt
    USD_price_in_COP = 4100

    if model == "gpt4o-mini":
        in_price = 0.00000015
        out_price = 0.0000006
    if model == "gpt-4o-2024-08-06":
        in_price = 0.0000025
        out_price = 0.000010
    if model == "gpt4o":
        in_price = 0.000005
        out_price = 0.000015
    if model == "llama-3-8b":
        in_price = 0.00000005
        out_price = 0.00000008
    if model == "llama-3-70b":
        in_price = 0.00000059
        out_price = 0.0000007
    if model == "haiku":
        in_price = 0.00000025
        out_price = 0.00000125

    ct = new_completion.usage.completion_tokens
    pt = new_completion.usage.prompt_tokens
    usd_total_price = (ct * out_price) + (pt * in_price)
    cop_total_price = usd_total_price * USD_price_in_COP
    conversation_price += cop_total_price
    print(
        f"💰 Conversation price: ${conversation_price} COP\n"
        f"   This message: ${cop_total_price} COP "
        f""
    )
    log(
        f"💰 Conversation price: ${conversation_price} COP\n"
        f"   This message: ${cop_total_price} COP "
        f""
    )

    return

def format_search_results(docs_list):
    print(f"📋 Agarrando todos los resultados ...")
    documents = []
    try:
        docs_list = list(docs_list)
        print(f"📋 Formateando resultados ...")
        for index, document in enumerate(docs_list, start=1):
            captions: QueryCaptionResult = document.get("@search.captions", "")
            captions_text = " // ".join([caption.text for caption in captions]) if captions is not None else ""
            doc_formatted = {
                "position" : index,
                "score": document.get("@search.score", 10),
                "rerank": document.get("@search.reranker_score", 10),
                "captions": captions_text,
                "id": document["id"],
                "title": document["title"],
                "author": document["author"],
                "keywords": document["keywords"],
                "category": document["category"],
                "page": document["page"],
                "year": document["year"],
                "has_copyright": document["has_copyright"],
                "file_path": document["file_path"],
                "external_id": document["external_id"],
                "content": document["content"],
            }
            documents.append(doc_formatted)
    except Exception as e:
        print(e)
    log(
        f">>>>>>format_search_results:\n"
        f"{json.dumps(documents, indent=4)}"
        )
    return documents

def normalize_content(text):
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.lower()
    return text

def compute_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def filter_docs(doc_list):
    print(f"🧹 Eliminando fuentes irrelevantes o duplicadas ...")
    filtered_docs = []
    seen_hashes = set()
    seen_ids = set()
    
    for doc in doc_list:
        score = doc.get("score", 10) 
        rerank = doc.get("rerank", 10) 
        content = doc["content"] 
        id = doc["id"] 
        normalized_content = normalize_content(content)
        content_hash = compute_hash(normalized_content)
        if (
            content_hash not in seen_hashes
            and id not in seen_ids
            and (rerank > 2
            or score > 0.17)
        ):
            filtered_docs.append(doc)
            seen_hashes.add(content_hash)
            seen_ids.add(id)
    print(f"🧹 Docs filtrados. De {len(doc_list)} pasaron {len(filtered_docs)} ...")
    log(f"🧹 Docs filtrados. De {len(doc_list)} pasaron {len(filtered_docs)} ...\n"
    f"{json.dumps(filtered_docs, indent=4)}")
    return filtered_docs

def get_best_results(doc_list):
    best_results = []
    for doc in doc_list:
        rerank = doc.get("rerank", 0) 
        if (
            rerank > 2.9
        ):
            best_results.append(doc)
            
    print(f"⭐️ Guardando los mejores. De {len(doc_list)} pasaron {len(best_results)} ...")
    log(f"⭐️ Guardando los mejores. De {len(doc_list)} pasaron {len(best_results)} ...\n")
    return best_results[:2]
    

def add_doc_to_context(docs_list, title="Fuente"):
    print(f"📋 Agregando fuentes al contexto ...")
    sources = ""
    counter = 0
    docs_list
    filtered_docs = filter_docs(docs_list)
    
    for document in filtered_docs:
        counter += 1
        sources += (
            f"{title}:\n"
            # f"{document.get("reason", "")}"
            f"id: {document["id"]}\n"
            f"title: {document["title"]}\n"
            f"author: {document["author"]}\n"
            f"year: {document["year"]}\n"
            f"keywords: {document["keywords"]}\n"
            f"category: {document["category"]}\n"
            f"page: {document["page"]}\n"
            f"content: {document["content"]}\n"
            f"\n\n"
        )      
    log(
        f"To add in Context: \n"
        f"{json.dumps({"sources":sources}, indent=4)}"
        )
    print(f"📋 {counter} fuentes agregadas ...")
    return sources

def search_for_chunks(text_query):
    log(f"🔎 Buscando documentos: {text_query} ...")
    print(f"🔎 Buscando documentos: {text_query} ...")
    results_num = 50
    vector_query = embeddings_client.generate_embeddings(content=text_query)

    results = search_client.search(
        search_text=text_query,
        vector_queries=[
            {
                "vector": vector_query,
                "k": results_num,
                "fields": "content_vector",
                "kind": "vector",
            }
        ],
        top=results_num,
        query_type=QueryType.SEMANTIC,
        semantic_configuration_name="default",
        query_caption="extractive|highlight-false",
        scoring_profile="legal",
        scoring_parameters=[
            "tagx6-Constitucional",
            "tagx5-Legal",
            "tagx4-Infralegal",
            "tagx3-Jurisprudencia",
            "tagx2-Doctrina",
        ],
    )
    results_formatted = format_search_results(results)
    restults_filtered = filter_docs(results_formatted)

    return restults_filtered[:15]       
        
@traceable(tags=[os.getenv('ENV')])
def run_conversation(user_prompt=None):
    if user_prompt:
        get_answer(user_prompt)
    else:
        while True:
            user_input = input("You: ")
            if user_input.lower() == "exit":
                print("Exiting chat...")
                break
            get_answer(user_input)

@traceable(tags=[os.getenv('ENV')])
def get_answer(user_prompt):
    global messages, log_file_name, user_input

    user_input = user_prompt

    current_time = datetime.now().strftime("%m-%d %H:%M")
    log_file_name = f"logs/{current_time} - {user_input[:50]}.log"

    print("🙎‍♂️ User: " + user_input)
    log(f"User input: {user_input}")

    query_prompt_message = {"role": "system", "content": query_system_template}
    response_prompt_message = {"role": "system", "content": response_system_template}
    query_user_prompt_message = {
        "role": "user",
        "content": f"Genera solo 1 búsqueda para: {user_input}",
    }

    query_messages = [
        query_prompt_message,
        *messages,
        query_user_prompt_message,
    ]

    print("🤖 Generando queries con la pregunta del usuario ...")
    log(f"{json.dumps(query_messages, indent=4)}\n")
    first_query_completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=query_messages,
        response_format=query_schema,
        temperature=0.0,
    )
    log(first_query_completion)
    get_conversation_price(first_query_completion, model="gpt4o-mini")
    first_search_terms = json.loads(
        first_query_completion.choices[0].message.content
    ).get("searches")
    print(f"🤖 {len(first_search_terms)} búsquedas generadas ...")

    sources_found = []
    best_results = []
    search_result_prompt = ""
    search_reasons = ""

    for search in first_search_terms:
        search_query = search.get("search_query")
        query_reason = search.get("reason")
        # print(f"Buscando '{search_query}': {query_reason}")
        print(query_reason)
        query_results = search_for_chunks(search_query)
        sources_found += query_results
        search_reasons += f"{query_reason} Por eso buscaré '{search_query}'.\n"
        # search_queries += f"'{search_query}',"
        sources_to_add = add_doc_to_context(query_results)
        best_results += get_best_results(query_results)
        search_result_prompt += f"{query_reason}.\nPor eso búsqué '{search_query}' y encontré estas fuentes:\n{sources_to_add}\n\n"

    # Meter aquí razonamiento de qué información ha encontrado en esta búsqueda.

    reasoning_results_prompt_message = {
        "role": "assistant",
        "content": search_result_prompt,
    }
    reasoning_prompt_message = {
        "role": "system",
        "content": f"Necesito que plantees una nueva y mejorada estrategia de búsqueda para responder al usuario de forma completa:\n1. Resume La Información: Lee y absorbe toda la información de las fuentes y utiliza los hallazgos más relevantes para mi investigación. \n2. Genera Una Nueva Búsqueda: Con estos nuevos hallazgos sugiere un máximo de 3 búsquedas que ayuden a conseguir información precisa y relevante para responder a la pregunta del usuario. \n\n3. Dime por qué estas 3 nuevas búsquedas me ayudarían en mi investigación. \nRecuerda que cada query debe cumplir con el checklist y que estamos buscando documentos para responder a: : {user_input}",
    }

    query_messages += [
        reasoning_results_prompt_message,
        reasoning_prompt_message,
    ]

    print("🤖 Generando nuevas búsquedas con la nueva información ...")
    log(f"{json.dumps(query_messages, indent=4)}\n")
    second_query_completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=query_messages,
        response_format=query_schema,
        temperature=0.0,
    )
    log(second_query_completion)
    get_conversation_price(second_query_completion, model="gpt4o-mini")
    second_search_terms = json.loads(
        second_query_completion.choices[0].message.content
    ).get("searches")
    print(f"🤖 {len(second_search_terms)} búsquedas generadas ...")

    query_reasons = ""
    # search_strategy = first_search_terms.get("strategy")
    # print(f"{search_strategy}")
    for search in second_search_terms:
        search_query = search.get("search_query")
        query_reason = search.get("reason")
        print(f"Buscando '{search_query}': {query_reason}")
        # print(query_reason)
        query_results = search_for_chunks(search_query)
        sources_found += query_results
        best_results += get_best_results(query_results)
        query_reasons += f"Buscaré fragmentos de documentos legales con el query '{search_query}': {query_reason}\n"
        # query_reasons += f"{query_reason} Por eso busqué '{search_query}'. "

    # return
    sources_to_add = add_doc_to_context(sources_found, "Fragmento")

    select_system_prompt_message = {"role": "system", "content": selection_system_prompt}
    select_user_prompt_message = {
        "role": "user",
        "content": f"Busca información relevante y selecciona entre 3 y 7 de los mejores fragmentos para responder: {user_input}",
    }
    select_reasons_prompt_message = {
        "role": "assistant",
        "content": f"{query_reasons}",
    }
    select_prompt_message = {
        "role": "assistant",
        "content": f"Resultados de mis búsquedas:\n{sources_to_add} \n\nAhora debo seleccionar entre 3 y 7 fragmentos siguiendo las instrucciones y garantizando que cumpla con el checklist.",
    }

    selection_messages = [
        select_system_prompt_message,
        *messages,
        select_user_prompt_message,
        select_reasons_prompt_message,
        select_prompt_message,
    ]
    
    # TODO: Limpiar código

    print("🤖 Escogiendo las mejores fuentes para responder al usuario ...")
    log(f"{json.dumps(selection_messages, indent=4)}\n")
    selected_sources_to_add = best_results[:6]
    selected_sources_completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=selection_messages,
        response_format=selected_sources_schema,
        temperature=0.0,
        n=1,
    )
    log(selected_sources_completion)
    get_conversation_price(selected_sources_completion, model="gpt4o-mini")
    selected_sources = json.loads(
        selected_sources_completion.choices[0].message.content
    ).get("sources")
    for index, source in enumerate(selected_sources, start=1):
        source_id = source.get("source_id")
        source_reason = source.get("reason")
        for source in sources_found:
            if source["id"] == source_id:
                source["reason"] = source_reason
                selected_sources_to_add.append(source)
        print(f"{index}.[{source_id}]: {source_reason}")
        
    filter_selected_sources_to_add = filter_docs(selected_sources_to_add)

    sources_at_end = ""
    for index, source in enumerate(filter_selected_sources_to_add, start=1):
        sources_at_end += f"{index}. {source["title"]} - Página {source["page"]}<br>\n"
        
                
    sources_to_add = add_doc_to_context(filter_selected_sources_to_add)
    # TODO: Agregar hasta 3 por cada query que excedan 2.8/3 como score semántico.
    # Quizás ponerle cap de 6 fuentes máximo en total ordenadas por score semántico, porque pueden ser 18 si ambas búsqueda es de 3 queries y tiene matchs fuertes
    # TODO: Esto podría ser que los reorganice convirtiendo en vectores en la pregunta y comparándolos con los vectores de cada chunk, ChatGPT me dió esa idea... o cohere.

    user_message = {
        "role": "user",
        "content": user_input,
    }
    sources_prompt_message = {
        "role": "assistant",
        "content": f"Fuentes econtradas:\n{sources_to_add}",
    }

    response_messages = [
        response_prompt_message,
        *messages,
        user_message,
        sources_prompt_message,
    ]
    
    log(f"{json.dumps(response_messages, indent=4)}\n")
    response_completion = openai_client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=response_messages,
        temperature=0.2,
        n=1,
    )
    log(response_completion)
    get_conversation_price(response_completion)
    print(response_completion.choices[0].message.content)
    
    print(f"\n\n<p>{sources_at_end}</p>")
    return

run_conversation("¿Cuándo se consuma el hurto?")