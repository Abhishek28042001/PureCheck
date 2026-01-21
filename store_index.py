from langchain_openai import AzureOpenAIEmbeddings
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from pinecone import ServerlessSpec
import src.helper as helper
import os
import dotenv
dotenv.load_dotenv()

NETAICONNECT_API_KEY = os.getenv("NETAICONNECT_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["NETAICONNECT_API_KEY"] = NETAICONNECT_API_KEY


extracted_data=helper.upload_pdf('data/')
filter_data = helper.filter_to_minimal_docs(extracted_data)
text_chunks=helper.text_split(filter_data)

# Initialize Azure OpenAI Embeddings
embeddings = AzureOpenAIEmbeddings(
    model="text-embedding-ada-002",
    azure_endpoint="https://netaiconnect.netapp.com/",
    api_key=NETAICONNECT_API_KEY, # Add your NetAIConnect API key here
    openai_api_version="2023-05-15",
) 

# Initialize Pinecone client
pc = Pinecone(api_key=PINECONE_API_KEY)

index_name = "purecheck-index"
# Create Pinecone index if it doesn't exist
if not pc.has_index(index_name):
    pc.create_index(
        name = index_name,
        dimension=1536,  # Dimension of the embeddings
        metric= "cosine",  # Cosine similarity
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
# Connect to Pinecone index
index = pc.Index(index_name)

# Upload in very small batches to avoid exceeding Pinecone's 4MB limit
# Using batch_size=5 for safety with large documents
docsearch = PineconeVectorStore.from_documents(
    documents=text_chunks,
    embedding=embeddings,
    index_name=index_name,
    batch_size=5,  # Very small batch size to stay well under 4MB limit
    embeddings_chunk_size=5  # Also limit embedding batch size
)

print("Documents uploaded to Pinecone index successfully.")