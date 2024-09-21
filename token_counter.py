import os
import gc
import re
import time

from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)


import tiktoken
from langchain_community.document_loaders import PDFPlumberLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter


from langchain.docstore.document import Document


INPUT_DIR = "input_files"
ERROR_OCR_MISSING_MESSAGE = "Sin OCR"
PRICE_PER_ADA_TOKEN = 0.0000001
PRICE_PER_CHUNK_STORAGE = 0.000055


def ensure_file_exists(file_path):
    """Ensure the log file exists or create a new one if it does not."""
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            file.write("")  # Create an empty file if it doesn't exist
    print(f"Checked/created file: {file_path}")


def ensure_directory_exists(directory_path):
    """Ensure the directory exists or create a new one if it does not."""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
    print(f"Checked/created directory: {directory_path}")


def setup_environment():
    """Setup the required directories, log files and directories."""
    ensure_directory_exists(INPUT_DIR)


def count_valid_pdfs(input_dir):
    count = 0
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                count += 1
    return count


def num_tokens_from_string(string: str, encoding_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


def new_split_local_pdf(pdf_path: str):
    loader = PDFPlumberLoader(pdf_path)
    pages = loader.load()
    if not any(page.page_content for page in pages):
        raise ValueError(ERROR_OCR_MISSING_MESSAGE)

    combined_text = ""
    page_offsets = []
    if not pages:
        raise ValueError(ERROR_OCR_MISSING_MESSAGE)

    for page in pages:
        if page.page_content:
            page_offsets.append(len(combined_text))
            combined_text += page.page_content
        else:
            print("No content in page")

    if not combined_text:
        raise ValueError(ERROR_OCR_MISSING_MESSAGE)
    sentence_endings = [
        "\n\n",
        "\n",
        ". ",
        "!",
        "?",
        "。",
        "！",
        "？",
        "‼",
        "⁇",
        "⁈",
        "⁉",
    ]
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=num_tokens_from_string,
        separators=sentence_endings,
    )

    chunks = text_splitter.split_text(combined_text)
    chunked_documents = []
    total_tokens = 0
    for chunk in chunks:
        start_offset = combined_text.find(chunk)
        total_tokens += num_tokens_from_string(chunk)
        try:
            page_num = (
                next(
                    i for i, offset in enumerate(page_offsets) if offset > start_offset
                )
                - 1
            )
        except StopIteration:
            page_num = len(page_offsets) - 1

        chunked_documents.append(
            Document(page_content=chunk, metadata={"page": page_num + 1})
        )
        print(chunked_documents)
    return {
        "total_tokens": total_tokens, 
        "total_pages": pages[0].metadata["total_pages"], 
        "total_chunks": len(chunked_documents),
        "chunks": chunked_documents
    }


def init_load_documents_azure():
    try:
        for root, dirs, files in os.walk(INPUT_DIR):
            for file in files:
                if file.lower().endswith(".pdf"):
                    print("")
                    file_in_progress = ""
                    filepath = os.path.join(root, file)
                    try:
                        file_in_progress = filepath
                        _, extension = os.path.splitext(filepath)
                        file_name = os.path.basename(filepath)
                        start_time = time.time() 
                        print(
                            "============================================================================="
                        )
                        print(f"{file_name}")
                        print(
                            "============================================================================="
                        )
                        print(
                            f">>>>>>>>>>>>>>>>>>>> 🔪 ... Separando el documento en chunks ..."
                        )

                        documents = new_split_local_pdf(filepath)
                        token_count = documents["total_tokens"]
                        chunks_count = documents["total_chunks"]
                        pages_count = documents["total_pages"]
                        
                        vectorizacion_price = token_count * PRICE_PER_ADA_TOKEN
                        storage_price = chunks_count * PRICE_PER_CHUNK_STORAGE
                        total_price = vectorizacion_price + storage_price
                        per_page_price = storage_price / pages_count
                        
                        
                        print(f"Total de tokens: ", token_count)
                        print(f"Total de chunks: ", chunks_count)
                        print(f"Total de páginas: ", pages_count)
                        print(f"")
                        print(f"Precio de vectorización {vectorizacion_price} USD")
                        print(f"Precio de alojamiento {storage_price} USD")
                        print(f"Total {chunks_count * PRICE_PER_CHUNK_STORAGE} USD --- {per_page_price} USD por página")

                        end_time = time.time()
                        elapsed_time = end_time - start_time
                        display_message = "Documento calculado"
                        if elapsed_time < 60:
                            print(
                                f">>>>>>>>>>>>>>>>>>>> {display_message} en: {elapsed_time:.6f} segundos"
                            )
                        else:
                            minutes, seconds = divmod(elapsed_time, 60)
                            print(
                                f">>>>>>>>>>>>>>>>>>>> {display_message} en: {int(minutes)} minutos y {seconds:.6f} segundos"
                            )
                    except Exception as e:
                        print(
                            f">>>>>>>>>>>>>>>>>>>> ❌ Error de carga del archivo\n📄 {file_in_progress} \nℹ️  {e}"
                        )

                    gc.collect()

            if not os.listdir(root):
                if root != INPUT_DIR:
                    os.rmdir(root)

        print("")
        print(
            "*********************************************************************************"
        )
        print(
            "*********************************************************************************"
        )
        print(f"Todos los documentos procesados")
        print(
            "*********************************************************************************"
        )
        print(
            "*********************************************************************************"
        )
    except Exception as e:
        print(f">>>>>>>>>>>>>>>>>>>> ❌ Error de general", e)


if __name__ == "__main__":
    setup_environment()
    print("")
    print(
        f">>> MIDIENDO DOCUMENTOS: \n\n"
        f"\n\n"
        f">>> {count_valid_pdfs(INPUT_DIR)} Documentos a calcular"
    )
    print("")
    user_input = input(
        """ 
        Presiona 1️⃣  para confirmar ✅
        Presiona 2️⃣  para cancelar ❌
        :"""
    )
    if user_input == "1":
        init_load_documents_azure()
        print("")
        print("")
    elif user_input == "2":
        print("Terminando el programa.")
    else:
        print("❌ Entrada no válida. Intente de nuevo.")
    os._exit(0)
