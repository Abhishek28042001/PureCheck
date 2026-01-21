from flask import Flask, render_template, jsonify, request, session
from langchain_pinecone import PineconeVectorStore
from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from src.prompt import *
from src.helper import (
    allowed_file,
    create_nutrition_analysis_chain
)
from openai import AzureOpenAI
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

load_dotenv()

NETAICONNECT_API_KEY = os.getenv("NETAICONNECT_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["NETAICONNECT_API_KEY"] = NETAICONNECT_API_KEY

# FSSAI INR Baseline Values
FSSAI_INR_BASELINE = {
    "energy_kcal": 2000,
    "total_fat_g": 65,
    "saturated_fat_g": 20,
    "carbohydrates_g": 300,
    "sugars_g": 50,
    "added_sugars_g": 30,
    "protein_g": 50,
    "sodium_mg": 2000,
    "fiber_g": 25,
}

POSITIVE_FACTOR_THRESHOLD = {
    "protein": {"high_threshold_percent": 20, "source_threshold_percent": 10},
    "fiber": {"high_threshold_percent": 20, "source_threshold_percent": 10}
}

embeddings = AzureOpenAIEmbeddings(
    model="text-embedding-ada-002",
    azure_endpoint="https://netaiconnect.netapp.com/",
    api_key=NETAICONNECT_API_KEY,
    openai_api_version="2023-05-15",
)

index_name = "purecheck-index"

docsearch = PineconeVectorStore.from_existing_index(
                index_name=index_name,
                embedding=embeddings,
)

retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k":3})

# Chat model configuration
chatModel = AzureChatOpenAI(
    model="gpt-4o",
    deployment_name='gpt-4o',
    api_key=NETAICONNECT_API_KEY,
    azure_endpoint='https://netaiconnect.netapp.com/',
    api_version='2023-05-15',
    temperature=0.0
)

# Create RAG chain for FSSAI questions
system_prompt = """You are a helpful assistant that answers questions about FSSAI food safety regulations and nutrition guidelines.
Use the following context to answer the user's question. If you don't know the answer, say so.

Context: {context}"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}")
])

question_answer_chain = create_stuff_documents_chain(chatModel, prompt)
rag_chain = create_retrieval_chain(retriever, question_answer_chain)

# Initialize o3-mini client for reasoning
o3_client = AzureOpenAI(
    api_key=NETAICONNECT_API_KEY,
    api_version="2024-12-01-preview",
    azure_endpoint="https://netaiconnect.netapp.com/"
)

# Create nutrition analysis chain
nutrition_analysis_chain = create_nutrition_analysis_chain(
    api_key=NETAICONNECT_API_KEY,
    fssai_inr_baseline=FSSAI_INR_BASELINE,
    o3_client=o3_client
)

# Routes
@app.route('/')
def index():
    """Main page with image upload and chat interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    """Handle image upload and analyze nutrition"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename, app.config['ALLOWED_EXTENSIONS']):
        return jsonify({'error': 'Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF, WEBP)'}), 400
    
    try:
        # Save the uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Execute the nutrition analysis chain (LangChain SequentialChain)
        # This chain handles: extraction -> analysis -> INR score calculation
        chain_result = nutrition_analysis_chain.invoke(filepath)
        
        if not chain_result['success']:
            return jsonify({
                'error': chain_result.get('error', 'Analysis failed'),
                'details': chain_result.get('details')
            }), 500
        
        # Extract results from chain
        product_data = chain_result['product_data']
        analysis = chain_result['analysis']
        inr_result = chain_result['inr_result']
        
        # Store in session for chat context
        session['current_product'] = {
            'product_data': product_data,
            'analysis': analysis,
            'inr_result': inr_result,
            'image_path': filepath
        }
        
        return jsonify({
            'success': True,
            'product_data': product_data,
            'analysis': analysis,
            'inr_result': inr_result,
            'image_path': filename
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages about the analyzed product or FSSAI questions"""
    # Get message from JSON data
    data = request.get_json()
    msg = data.get('message', '')
    
    if not msg:
        return jsonify({'success': False, 'error': 'No message provided'}), 400
    
    print(f"User input: {msg}")
    
    try:
        # Get current product context from session
        current_product = session.get('current_product')
        
        if current_product:
            # Product-specific chat with context
            product_context = f"""

Current Product Analysis:
- Product: {current_product['product_data'].get('product_name', 'Unknown')}
- Brand: {current_product['product_data'].get('brand', 'Unknown')}
- Type: {current_product['product_data'].get('product_type', 'Solid')}
- INR Score: {current_product['inr_result']['inr_score']:.1f}/100
- Grade: {current_product['inr_result']['grade']}
- Energy: {current_product['product_data']['nutritional_info_per_100g']['energy_kcal']} kcal/100g
- Sugars: {current_product['product_data']['nutritional_info_per_100g']['sugars_g']} g/100g
- Saturated Fat: {current_product['product_data']['nutritional_info_per_100g']['saturated_fat_g']} g/100g
- Sodium: {current_product['product_data']['nutritional_info_per_100g']['sodium_mg']} mg/100g
- Protein: {current_product['product_data']['nutritional_info_per_100g']['protein_g']} g/100g

Health Warnings: {', '.join(current_product['inr_result'].get('health_warnings', [])) or 'None'}
Positive Claims: {', '.join(current_product['inr_result'].get('positive_claims', [])) or 'None'}

You are the CPG (Compliance and Product Guidance) assistant for FSSAI regulations and nutrition guidelines.
Pin-point your answers based on the product data provided above.
Tell where the guidlines fails. Which clause is violated.


User Question: {msg}

Format your response with:
- Use **bold** for important terms (wrap text in **)
- Use bullet points with "- " for lists
- Be concise and friendly
- Include relevant emojis where appropriate
"""
            # Use chatModel directly for product-specific questions
            response_obj = chatModel.invoke(product_context)
            response_text = response_obj.content
            
        else:
            # General FSSAI chat using RAG chain
            response = rag_chain.invoke({"input": msg})
            response_text = response["answer"]
        
        print(f"Response: {response_text}")
        return jsonify({'success': True, 'response': response_text})
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/clear-session', methods=['POST'])
def clear_session():
    """Clear current product session"""
    session.pop('current_product', None)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)