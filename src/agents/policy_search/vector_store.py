from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from agents.policy_search.data.data import load_documents


def create_db():

    documents=load_documents()


    embeddings=HuggingFaceEmbeddings(
        model_name=
        "sentence-transformers/all-MiniLM-L6-v2"
    )


    db=Chroma.from_documents(
        documents,
        embeddings,
        persist_directory="db"
    )


    return db