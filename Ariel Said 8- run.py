import os
import json
import re
from datetime import datetime

from langchain_openai import AzureOpenAIEmbeddings
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from azure.search.documents._generated.models import QueryCaptionResult

from openai import AzureOpenAI
import tiktoken

from dotenv import load_dotenv

load_dotenv()

def num_tokens_from_string(string: str, encoding_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

class AzureEmbeddings:

    def __init__(self):
        pass

    @staticmethod
    def get_embedding():
        return AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("OPENAI_AZURE_DEPLOYMENT"), 
            openai_api_version="2023-08-01-preview",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            azure_endpoint=os.getenv("OPEN_AI_AZURE_URL")
        )

    @staticmethod
    def generate_embeddings(content: str):
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("OPENAI_AZURE_DEPLOYMENT"), 
            openai_api_version="2023-08-01-preview",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            azure_endpoint=os.getenv("OPEN_AI_AZURE_URL")
        )

        doc_result = embeddings.embed_documents([content])

        return doc_result[0]

openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_CHAT_OPENAI_API_KEY"), 
    api_version=os.getenv("AZURE_CHAT_OPENAI_API_VERSION"), 
    azure_endpoint=os.getenv("AZURE_CHAT_OPENAI_ENDPOINT")
    )

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
        ct_price = 0.0000006
        pt_price = 0.00000015
    if model == "gpt4o":
        ct_price = 0.000015
        pt_price = 0.000005

    ct = new_completion.usage.completion_tokens
    pt = new_completion.usage.prompt_tokens
    tt = new_completion.usage.total_tokens
    usd_total_price = (ct * ct_price) + (pt * pt_price)
    cop_total_price = usd_total_price * USD_price_in_COP
    conversation_ct += ct
    conversation_pt += pt
    conversation_tt += tt
    conversation_usd_total_price = (conversation_ct * ct_price) + (
        conversation_pt * pt_price
    )
    conversation_cop_total_price = conversation_usd_total_price * USD_price_in_COP

    print(
        f"💰 Conversation price: ${conversation_cop_total_price} COP (In: {conversation_pt}, Out: {conversation_ct}, Total token: {conversation_tt})\n"
        f"   This message: ${cop_total_price} COP (In: {pt}, Out: {ct}, Total token: {tt}) "
        f""
    )
    log(
        f"💰 Conversation price: ${conversation_cop_total_price} COP (In: {conversation_pt}, Out: {conversation_ct}, Total token: {conversation_tt})\n "
        f"   This message: ${cop_total_price} COP (In: {pt}, Out: {ct}, Total token: {tt}) "
        f""
    )

    return

### 🔑 Definir system prompt y tools

messages = []
conversation = []
user_input = ""

codes_to_laws = "\n- Código Penal: Ley 599 de 2000\n- Código Civil: Ley 57 de 1887\n- Código de Comercio: Decreto 410 de 1971\n- Código de Procedimiento Civil: Decreto 1400 de 1970\n- Código de Procedimiento Penal: Ley 906 de 2004\n- Código General del Proceso: Ley 1564 de 2012\n- Código de la Infancia y la Adolescencia: Ley 1098 de 2006\n- Código Nacional de Policía: Decreto 1355 de 1970\n- Código de Recursos Naturales: Decreto 2811 de 1974\n- Código Electoral: Decreto 2241 de 1986\n- Código Disciplinario Único: Ley 734 de 2002\n- Código Contencioso Administrativo: Ley 1437 de 2011 (anteriormente Decreto 1 de 1984)\n- Código de Minas: Ley 685 de 2001\n- Código de Educación: Ley 115 de 1994\n- Código Nacional de Tránsito Terrestre: Ley 769 de 2002\n- Código del Menor: Decreto 2737 de 1989\n- Código de Construcción del Distrito Capital de Bogotá: Acuerdo 20 de 1995\n- Código de Construcción Sismo-Resistente: Acuerdo correspondiente (no especificado en los resultados)\n- Código de Régimen Departamental: Decreto 1222 de 1986\n- Código de Régimen Político y Municipal: Decreto-Ley 1333 de 1986\n- Código Penal Militar: Ley 522 de 1999\n- Código Penitenciario y Carcelario: Ley 65 de 1993\n- Código Procesal del Trabajo y del Seguro Social: Decreto-Ley 2158 de 1948\n- Código Sustantivo del Trabajo: Decreto 2663 de 1950\n- Código Sanitario Nacional: Ley 9 de 1979\n- Código General Disciplinario: Ley 1952 de 2019\n- Código Nacional de Seguridad y Convivencia Ciudadana: Ley 1801 de 2016\n- CODIGO DE POLICIA DE BOGOTA: ACUERDO 79 DE 2003\n- Código Penal Militar: Ley 522 de 1999\n- Código Penitenciario y Carcelario: Ley 65 de 1993\n- Código Procesal del Trabajo y del Seguro Social: Decreto-Ley 2158 de 1948\n- Código Sustantivo del Trabajo: Decreto 2663 de 1950\n- Código Sanitario Nacional: Ley 9 de 1979\n- Código General Disciplinario: Ley 1952 de 2019\n- Código Nacional de Seguridad y Convivencia Ciudadana: Ley 1801 de 2016"


get_next_chunk = {
    "type": "function",
    "function": {
        "name": "get_next_chunk",
        "description": "Use this tool to get when an important sources comes incomplete or the content is cut off. This tool will help you retrieve the following section of that given source.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "the unique identifier of the chunk that is incomplete. eg:'20240719192458csjscpboletinjurisprudencial20181219pdf_chunk30'",
                },
            },
            "required": ["source_id"],
        },
    },
}

response_system_template = f"""
Eres Ariel, un asistente para la investigación legal en jurisprudencia colombiana. Sigue estas instrucciones al responder:

1. Consulta de Fuentes:
- Tienes acceso a algunas fuentes que previasmente has encontrado y seleccionado para generar esta respuesta. - Dentro de esas fuentes se encuentra toda la información disponible para responder. 
- Expresa toda la información que encuentres en las fuentes proporcionadas y que sea relevante para responder.
- Si las fuentes no ayudan a responder la pregunta, responde: "No encuentro información con esos términos, ¿puedes reformular tu consulta?"

2. Redacción de Respuestas:
- Sé detallado y preciso, utilizando exclusivamente la información de las fuentes proporcionadas.
- No incluyas información que no haya sido extraída directamente de las fuentes.

3. Citación de Fuentes:
- Cita el mayor número de fuentes aplicables.
- Utiliza corchetes para referenciar la fuente con el ID del fragmento sin modificarlo, por ejemplo: [12345_id_de_ejemplo].
- No combines fuentes; lista cada fuente por separado.

3. Formato de Respuesta:
- Escribe tus respuestas en formato HTML, sin incluir los tags "```html" al principio o al final.
- Utiliza etiquetas HTML estándar como <p>, <strong>, <em>, etc.

5. Interpretación de Categorías:
- Prioriza las fuentes según su categoría:
    1. Constitucional: Es la norma máxima y más importante establecida por el gobierno del país. 
    2. Legal: Es la que le sigue en importancia y son los decretos, códigos y leyes oficiales del país establecida por los ministerios. 
    3. Infralegal: Le sigue en importancia a la categoría Legal. 
    4. Jurisprudencia: Son los documentos de juicios reales y de cómo se ha ejercido la ley en el pasado. 
    5. Doctrina: Son documentos o libros escritos por autores del derecho que no son parte de la ley pero ayudan a darle una interpetación a la ley.
- Da mayor importancia a las fuentes más actuales.

6. Precisión Legal:
- Siempre dale más importancia a la fuente primaria. Si debes citar una ley, artículo o norma, cita la fuente directa, es decir, esa ley, artículo o normal.
- Las fuentes secundarias te ayudarán a entender la interpretación sobre las fuentes primarias.
- No confundas leyes o artículos; si el usuario pregunta por una ley específica, ignora extractos de otras leyes.
- Utiliza las fuentes para dar una respuesta completa y darle al usuario información adicional que pueda serle de ayuda.
- Cita textualmente cuando necesites mencionar el contenido un artículo, ley u otro documento y si el tamaño de este lo permite.

7. Evita Imprecisiones:
- En caso de encontrar información contradictoria, señálala y sugiere una posible causa.
- No te salgas del tema de la pregunta del usuario.
- En caso que el usuario haya dado información incorrecto o imprecisa, señálala y da un argumento.
- Si la ley, la jurisprudencia y la doctrina tienen respuestas diferentes o interpretaciones diferentes para la misma pregunta, señala las distintas perspectivas.
"""

# Incluir que el usuario puede estar proporcionando alguna información que es falsa, en ese caso debe apuntarla y argumentar con la información de las fuentes el porqué es falsa.
# Incluir que señale información contradictoria si es relevante en las fuentes.
# Que siempre le dé más importancia a las fuentes primarias.
# Que las fuentes secundarias ayudan a dar interpretación y contexto.

query_system_template = f"""Eres un experto legal que necesita buscar en una base de conocimiento con cientos de miles de documentos, fuentes confiables y precisas para responder las consultas del usuario. La base de conocimientos está alojada en Azure AI Search y bebes generar un query por cada búsqueda que necesitas y que que conserve todo el significado semántico de la idea. 

Los documentos están guardados en fragmentos con los siguientes campos:
- id: Identificador único del fragmento
- title: Título del documento
- author: Autor del documento
- keywords: Tema legal, puede ser: General, Constitucional, Internacional_Publico, Internacional_Privado, Penal, Financiero, entre otros.
- category: Tipo de documento legal. Las opciones son: Jurisprudencia, Doctrina, Constitucional, Legal, Infralegal y Otros_temas_legales. 
- page: Página de la que fue extraído el fragmento.
- year: Año en el que se publicó el documento.
- content: 500 tokens de contenido, fragmento o extracto del documento. Son solo 500 tokens del documento completo.

Pasos para generar la búsqueda:
1. Identifica qué información necesitas investigar para responder de forma precisa y completa al usuario.
2. Solo puedes hacer 3 búsquedas, así que elabora un plan de investigación organizarás cómo puedes distribuir tus búsquedas en caso que necesites hacer más de 1.  
3. Genera un query por cada búsquedad que necesitas ejecutar. Puedes generar un máximo de 3 búsquedas. Puedes buscar cualquier cosa, desde teorías del derecho, hasta leyes o una búsqueda general.
4. Cada búsqueda solo puede contener 1 idea. Eso significa que si debes comparar conceptos, leyes o documentos, debes buscarlos por separado.
5. Por cada búsqueda, da una breve explicación donde agumentes porqué necesitas hacer esa búsqueda.

Cada query debe cumplir con las siguientes condiciones:
- Debe ser una idea semánticamente completa y contener los keywords relevantes.
- No debe ser demasiado largo. Sé conciso, pero nunca dejes por fuera conceptos claves como el lugar, momento u otros aspectos claves.
- Siempre incluye el qué, cuándo o cómo en tu término de búsqueda, ya esto hará que la búsqueda esté semánticamente completa y genere los resultados correctos. Es decir, si por ejemplo el usuario pregunta '¿Cuándo se ...' el query debe incluir la palabra 'cuándo', 'momento de' o algo que haga similar.
- Si el usuario pregunta por el momento, lugar o alguna condición, esto debe estar presente en tu query.
- Si identificas una fuente específica como el número de ley, artículo, decreto, el título del documento, el nombre del autor o el tipo de documento legal que necesitas buscar, debes incluirlo en el query.
- Si hay varias formas de referise a una fuente, incluye los diferentes nombres de esa fuente en el query.
- No es necesario que todas tus búsquedas sean específicas para un documento, recuerda que solo puedes hacer máximo 3 búsquedas, así que en ocasiones puedes obtener mejor información si buscas conceptos más generales en vez de un documento específico.

Esta es una lista de los códigos en colombia y sus respectiva ley. Si necesitas buscar alguna de estas fuentes, debes incluir ambas refencias en tu query: {codes_to_laws}
"""


query_schema = {
    "type": "json_schema",
    "json_schema": {
        "name": "search_query",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "searches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "search_query": {
                                "type": "string",
                                "description": "El query de búsqueda completo. Este debe cumplir con todos los requitiso.",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Argumento de porqué necesitas hacer esta búsqueda.",
                            },
                        },
                        "required": [
                            "search_query",
                            "reason",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["searches"],
            "additionalProperties": False,
        },
    },
}
selected_sources_schema = {
    "type": "json_schema",
    "json_schema": {
        "name": "selected_sources",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_id": {
                                "type": "string",
                                "description": "ID de la fuente que seleccionaste",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Argumento de porqué seleccionaste esta fuente.",
                            },
                        },
                        "required": [
                            "source_id",
                            "reason",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["sources"],
            "additionalProperties": False,
        },
    },
}
# Agregar un campo para identificar fuentes cortadas

def generate_completion(completion_messages):
    log(f"{json.dumps(completion_messages, indent=4)}\n")
    response = openai_client.chat.completions.create(
        model=os.getenv("AZURE_CHAT_OPENAI_DEPLOYMENT"),
        messages=completion_messages,
        tools=[get_next_chunk],
        temperature=0.2,
        n=1,
        tool_choice="auto",
    )
    log(response)
    get_conversation_price(response)
    return response


def generate_mini_completion(completion_messages):
    log(f"{json.dumps(completion_messages, indent=4)}\n")
    response = openai_client.chat.completions.create(
        model=os.getenv("AZURE_CHAT_MINI_OPENAI_DEPLOYMENT"),
        messages=completion_messages,
        temperature=0.2,
        n=1,
    )
    log(response)
    get_conversation_price(response, model="gpt4o-mini")
    return response


def choose_sources_completion(completion_messages):
    log(f"{json.dumps(completion_messages, indent=4)}\n")
    response = openai_client.chat.completions.create(
        model=os.getenv("AZURE_CHAT_MINI_OPENAI_DEPLOYMENT"),
        messages=completion_messages,
        response_format=selected_sources_schema,
        temperature=0.0,
        n=1,
    )
    log(response)
    get_conversation_price(response, model="gpt4o-mini")
    return response


def generate_query(query_messages):
    log(f"{json.dumps(query_messages, indent=4)}\n")
    response = openai_client.chat.completions.create(
        model=os.getenv("AZURE_CHAT_MINI_OPENAI_DEPLOYMENT"),
        messages=query_messages,
        response_format=query_schema,
        temperature=0.0,
    )
    log(response)
    get_conversation_price(response, model="gpt4o-mini")
    return response

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

def filter_docs(doc_list):
    print(f"🧹 Eliminando fuentes irrelevantes o duplicadas ...")
    filtered_docs = []
    seen_docs = set()
    
    for doc in doc_list:
        score = doc.get("score", 10) 
        rerank = doc.get("rerank", 10) 
        content = doc["content"] 
        if (
            content not in seen_docs
            and (rerank > 2
            or score > 0.17)
        ):
            filtered_docs.append(doc)
            seen_docs.add(content)
    print(f"🧹 Docs filtrados. De {len(doc_list)} pasaron {len(filtered_docs)} ...")
    log(f"🧹 Docs filtrados. De {len(doc_list)} pasaron {len(filtered_docs)} ...\n"
    f"{json.dumps(filtered_docs, indent=4)}")
    return filtered_docs

def add_doc_to_context(docs_list):
    print(f"📋 Agregando fuentes al contexto ...")
    sources = ""
    counter = 0
    
    for document in docs_list:
        counter += 1
        sources += (
            f"Fuente:\n"
            f"{document.get("reason", "")}"
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
                "exhaustive": True,
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

    return restults_filtered[:25]


def get_next_chunks(id):
    log(f"⏩️ Buscando los chunks siguientes de {id} ...")
    print(f"⏩️ Buscando los chunks siguientes de {id} ...")
    pattern = r"^(.*_chunk)(\d+)$"
    match = re.search(pattern, id)

    if match:
        prefix = match.group(1)
        chunk_number = int(match.group(2))
        next_chunks_result = search_client.search(
            filter=f"id eq '{prefix}{chunk_number + 1}' or id eq '{prefix}{chunk_number + 2}'",
            top=2,
        )
        return format_search_results(list(next_chunks_result))


def get_next_chunk_tool(source_id):
    next_chunks = get_next_chunks(source_id)
    log(f"Continuación de {source_id}:\n{add_doc_to_context(next_chunks)}")
    return f"Continuación de {source_id}:\n{add_doc_to_context(next_chunks)}"

def append_message(new_message):
    global messages, conversation

    if isinstance(new_message, dict):
        role = new_message.get("role")
        content = new_message.get("content")
    else:
        role = new_message.role
        content = new_message.content

    if role == "assistant":
        if new_message.tool_calls:
            tool_calls = new_message.tool_calls
            tool_calls_formatted = []
            for tool_call in tool_calls:
                tool_calls_formatted.append(
                    {
                        "id": tool_call.id,
                        "function": {
                            "arguments": str(json.loads(tool_call.function.arguments)),
                            "name": tool_call.function.name,
                        },
                        "type": "function",
                    }
                )
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": tool_calls_formatted,
                },
            )
            return messages  ## Assistant call tools
        elif content:
            messages.append({"role": "assistant", "content": content})
            return messages  ## Assistant talk
    elif role == "tool":
        messages.append(new_message)
        return messages  ## Tool reponse
    else:
        return messages
    
    
def call_tools(tool_calls):
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        if tool_name == "get_next_chunk":
            content = get_next_chunk_tool(tool_args.get("source_id"))

        new_tool_message = {
            "tool_call_id": tool_call.id,
            "role": "tool",
            "name": tool_name,
            "content": content,
        }

        append_message(new_message=new_tool_message)

    print(">> 🤖 Generando respuesta ...")
    new_assistant_completion = generate_completion()
    new_assistant_message = new_assistant_completion.choices[0].message
    append_message(new_message=new_assistant_message)

    if new_assistant_message.content:
        return print("💬 Assistant:" + new_assistant_message.content)
    else:
        return call_tools(
            tool_calls=new_assistant_message.tool_calls,
        )
        
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


def get_answer(user_prompt):
    global messages, log_file_name, user_input

    user_input = user_prompt

    current_time = datetime.now().strftime("%m-%d %H:%M")
    log_file_name = f"logs/{current_time} - {user_input[:50]}.log"

    print("🙎‍♂️ User: " + user_input)
    log(f"User input: {user_input}")

    query_prompt_message = {"role": "system", "content": query_system_template}
    query_user_prompt_message = {
        "role": "user",
        "content": f"Genera uno o varias búsquedas para responder esta pregunta: {user_input}",
    }

    query_messages = [
        query_prompt_message,
        *messages,
        query_user_prompt_message,
    ]

    print("🤖 Generando queries con la pregunta del usuario ...")
    first_query_completion = generate_query(query_messages)
    first_search_terms = json.loads(
        first_query_completion.choices[0].message.content
    ).get("searches")
    print(f"🤖 {len(first_search_terms)} búsquedas generadas ...")

    # TODO: Puedo explorar en meterle una validación de si necesita hacer otra pasa de búsqueda o en los documentos ya está la respuesta completa y exacta.

    sources_found = []
    search_result_prompt = ""
    for search in first_search_terms:
        search_query = search.get("search_query")
        query_reason = search.get("reason")
        # print(f"Buscando '{search_query}': {query_reason}")
        print(query_reason)
        query_results = search_for_chunks(search_query)
        sources_found += query_results
        sources_to_add = add_doc_to_context(query_results)
        search_result_prompt += f"{query_reason}.\nResultados de la búsqueda '{search_query}':\n{sources_to_add}\n\n"

    sources_prompt_message = {
        "role": "assistant",
        "content": search_result_prompt,
    }
    sources_instructions_prompt_message = {
        "role": "system",
        "content": f"Ejectuaste una búsqueda inicial y encontraste algunos extractos con esa búsqueda. Ahora, sigue las siguientes instrucciones:\n1. Revisa todos los extractos obtenidos con tus primeras búsquedas e identifica fuentes relevantes que te ayuden a responder al usuario.\n2. Identifica leyes, artículos, o nombres de sentencias o documentos exactos e inclúyelos en el query si son importantes para responder la pregunta del usuario.\n3. Revisa tu estrategia de búsqueda inicial y mejórala. Ten en cuenta que debes separar conceptos, uno por cada búsqueda en la medida de los posible.\n4. Arma tu query teniendo en cuenta las fuentes, incluyendo el contexto semántico completo, pero sé conciso y no busques varias cosas en un solo query.\n5. Si necesitas buscar más de una fuente o término, crea otra búsqueda.7. Si la ley, artículo o sentencia tiene un número ej: 'Ley 203 de 1999', inclúyela en el query junto a su nombre de referencia 'Código de ...'. 8. Ahora que tienes información a tu disposición, puedes revisar si la pregunta hecha por el usuario está bien formulada o no y corregir las búsquedas en base a estos hallazgos. 9. Sigue las condiciones iniciales que debe cumplir cada query.\n10. Identifica si hay menciones a otras fuentes relevantes, teorías o definiciones que necesitas investigar más.\n\n",
    }

    query_messages += [
        sources_prompt_message,
        sources_instructions_prompt_message,
    ]

    print("🤖 Generando nuevas búsquedas con la nueva información ...")
    second_query_completion = generate_query(query_messages)
    second_search_terms = json.loads(
        second_query_completion.choices[0].message.content
    ).get("searches")
    print(f"🤖 {len(second_search_terms)} búsquedas generadas ...")

    query_reasons = ""
    for search in second_search_terms:
        search_query = search.get("search_query")
        query_reason = search.get("reason")
        # print(f"Buscando '{search_query}': {query_reason}")
        print(query_reason)
        query_results = search_for_chunks(search_query)
        sources_found += query_results
        query_reasons += f"{query_reason} Por eso busqué '{search_query}'. "

    sources_found_filtered = filter_docs(sources_found)
    sources_to_add = add_doc_to_context(sources_found_filtered)

    response_prompt_message = {"role": "system", "content": response_system_template}
    select_user_prompt_message = {
        "role": "user",
        "content": f"Busca información relevante y selecciona las mejores fuentes para responder a: {user_input}",
    }
    select_prompt_message = {
        "role": "assistant",
        "content": f"{query_reasons}.\n\nResultados de mis búsquedas:\n{sources_to_add}\n\nEjectuaste una búsqueda con lo que el usuario te preguntó y encontraste fuentes que pueden servirte, ahora debes escoger las mejores. Sigue las siguientes instrucciones:\n1. Revisa todos los extractos obtenidos con tu búsqueda y escoge un máximo de 10 fuentes que te sirvan para responder al usuario.\n2. Enlista las fuentes que escogiste e identifícalas por su ID y por ningún motivo en absoluto cambies el valor del ID o número de chunk de una fuente. Ordénalas por importancia, posicionando de primero la que consideres más relevante o más cercanas a lo que el usuario pidió.\n3.(Opcional) Intenta seleccionar un grupo de fuentes donde puedas dar una respuesta completa a la pregunta, señalar contradicciones en las fuentes, dar información complementaria relevante y señalar diversos puntos de vista al respecto lo que el usuario pregunta.\n4. Al lado de cada fuente que seleccionaste escribe una muy breve explicación argumentando porqué la escogiste y porqué ayuda a responder mejor la solicitud del usuario.\n5. Toda la información debe provenir de lo que dicen las fuentes, no inventes ni des información adicional que no estén presentes en las fuentes.\nRecomendaciones adicionales\n- Dale más importancia a las fuentes que son extractos del documento que el usuario pidio.\n- Conforma tu selección tanto de fuentes primarias como secundarias si esto ayuda a reponder mejor la pregunta.\n- Ten en cuenta que los nombres de algunos codigos hacen referencia a una ley, decreto o articulo. Aqui tienes un listado para que te guies:\n{codes_to_laws}",
    }
    # select_instructions_prompt_message = {
    #     "role": "system",
    #     "content": f"Ejectuaste una búsqueda con lo que el usuario te preguntó y encontraste fuentes que pueden servirte, ahora debes escoger las mejores. Sigue las siguientes instrucciones:\n1. Revisa todos los extractos obtenidos con tu búsqueda y escoge un máximo de 10 fuentes que te sirvan para responder al usuario.\n2. Enlista las fuentes que escogiste e identifícalas por su ID y por ningún motivo en absoluto cambies el valor del ID o número de chunk de una fuente. Ordénalas por importancia, posicionando de primero la que consideres más relevante o más cercanas a lo que el usuario pidió.\n3.(Opcional) Intenta seleccionar un grupo de fuentes donde puedas dar una respuesta completa a la pregunta, señalar contradicciones en las fuentes, dar información complementaria relevante y señalar diversos puntos de vista al respecto lo que el usuario pregunta.\n4. Al lado de cada fuente que seleccionaste escribe una muy breve explicación argumentando porqué la escogiste y porqué ayuda a responder mejor la solicitud del usuario.\n5. Toda la información debe provenir de lo que dicen las fuentes, no inventes ni des información adicional que no estén presentes en las fuentes.\nRecomendaciones adicionales\n- Dale más importancia a las fuentes que son extractos del documento que el usuario pidio.\n- Conforma tu selección tanto de fuentes primarias como secundarias si esto ayuda a reponder mejor la pregunta.\n- Ten en cuenta que los nombres de algunos codigos hacen referencia a una ley, decreto o articulo. Aqui tienes un listado para que te guies:\n{codes_to_laws}",
    # }

    selection_messages = [
        response_prompt_message,
        *messages,
        select_user_prompt_message,
        select_prompt_message,
        # select_instructions_prompt_message,
    ]

    print("🤖 Escogiendo las mejores fuentes para responder al usuario ...")
    selected_sources_to_add = []
    selected_sources_completion = choose_sources_completion(selection_messages)
    selected_sources = json.loads(
        selected_sources_completion.choices[0].message.content
    ).get("sources")
    for index, source in enumerate(selected_sources, start=1):
        source_id = source.get("source_id")
        source_reason = source.get("reason")
        for source in sources_found_filtered:
            if source["id"] == source_id:
                source["reason"] = source_reason
                selected_sources_to_add.append(source)
        print(f"{index}. [{source_id}] : {source_reason}")

    # return
    sources_to_add = add_doc_to_context(selected_sources_to_add)

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

    response_completion = generate_completion(response_messages)
    print(response_completion.choices[0].message.content)

    # print(">> 🤖 Generando respuesta ...")
    # new_user_message = {"role": "user", "content": user_input}
    # messages = [new_user_message]
    # response = generate_completion()
    # response_message = response.choices[0].message

    # messages = append_message(new_message=response_message)

    # tool_calls = response_message.tool_calls
    # if tool_calls:
    #     call_tools(tool_calls=tool_calls)
    # elif response_message.content:
    #     print("💬 Assistant:", response_message.content)
    # else:
    #     print("An error ocurred during completion generation - response: ", response)
    
run_conversation("¿Qué dice el artículo 103 del código penal?")