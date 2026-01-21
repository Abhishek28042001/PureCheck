"""
Helper functions for PureCheck - Food Product Analysis
"""

import base64
import os
import json
from openai import AzureOpenAI
from langchain_community.document_loaders import PDFPlumberLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.prompt import NUTRITION_EXTRACTION_PROMPT
from typing import List
from langchain.schema import Document
from langchain_community.document_loaders import DirectoryLoader


def upload_pdf(file_path):
    print(f"Loading PDF document from: {file_path}")
    loader = DirectoryLoader(
                    file_path, 
                    glob="**/*.pdf", 
                    loader_cls=PDFPlumberLoader
                )
    documents = loader.load()
    return documents

# filtering the documents structure
def filter_to_minimal_docs(docs: List[Document]) -> List[Document]:
    minimal_docs = []
    for doc in docs:
        src = doc.metadata.get("source")
        minimal_doc = Document(metadata={"source": src}, page_content=doc.page_content)
        minimal_docs.append(minimal_doc)
    return minimal_docs

# Split the document in smaller chunks
def text_split(minimal_docs):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=20,
        separators=["\n\n", "\n", " ", ""]
    )
    text_chunks = text_splitter.split_documents(minimal_docs)
    return text_chunks

def encode_image_to_base64(image_path):
    """
    Encode an image file to base64 string.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Base64 encoded image string
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def extract_nutrition_info_gpt4o(image_path, api_key=None, azure_endpoint=None):
    """
    Extract nutritional information from a food product image using GPT-4o Vision.
    
    Args:
        image_path (str): Path to the food product image
        api_key (str, optional): NetAIConnect API key. If None, will use NETAICONNECT_API_KEY env variable
        azure_endpoint (str, optional): Azure endpoint URL. Defaults to NetAIConnect endpoint
        
    Returns:
        dict: Extracted nutritional information in structured format
    """
    # Get API key from environment if not provided
    if api_key is None:
        api_key = os.getenv("NETAICONNECT_API_KEY")
        if not api_key:
            raise ValueError("API key not provided and NETAICONNECT_API_KEY environment variable not set")
    
    # Set default Azure endpoint
    if azure_endpoint is None:
        azure_endpoint = "https://netaiconnect.netapp.com/"
    
    # Initialize Azure OpenAI client
    client = AzureOpenAI(
        api_key=api_key,
        api_version="2024-02-15-preview",
        azure_endpoint=azure_endpoint
    )
    
    # Encode image to base64
    base64_image = encode_image_to_base64(image_path)
    
    # Prepare the message with image
    messages = [
        {
            "role": "system",
            "content": "You are an expert food product label analyzer with OCR capabilities."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": NUTRITION_EXTRACTION_PROMPT
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ]
    
    # Call GPT-4o Vision
    response = client.chat.completions.create(
        model="gpt-4o",  # GPT-4o model with vision capabilities
        messages=messages,
        max_tokens=2000,
        temperature=0.1  # Low temperature for more consistent outputs
    )
    
    # Extract the response content
    result_text = response.choices[0].message.content
    
    # Try to parse JSON from the response
    try:
        # Find JSON in the response (might be wrapped in markdown code blocks)
        if "```json" in result_text:
            json_start = result_text.find("```json") + 7
            json_end = result_text.find("```", json_start)
            json_str = result_text[json_start:json_end].strip()
        elif "```" in result_text:
            json_start = result_text.find("```") + 3
            json_end = result_text.find("```", json_start)
            json_str = result_text[json_start:json_end].strip()
        else:
            json_str = result_text
            
        nutrition_data = json.loads(json_str)
        return {
            "success": True,
            "data": nutrition_data,
            "raw_response": result_text
        }
    except json.JSONDecodeError as e:
        # If JSON parsing fails, return raw text
        return {
            "success": False,
            "error": f"Failed to parse JSON: {str(e)}",
            "raw_response": result_text
        }


def analyze_food_product(image_path, api_key=None):
    """
    High-level function to analyze a food product image.
    
    Args:
        image_path (str): Path to the food product image
        api_key (str, optional): NetAIConnect API key
        
    Returns:
        dict: Analysis results
    """
    print(f"Analyzing food product image: {image_path}")
    
    try:
        result = extract_nutrition_info_gpt4o(image_path, api_key)
        
        if result["success"]:
            print("\n✓ Successfully extracted nutritional information!")
            return result["data"]
        else:
            print(f"\n✗ Error: {result['error']}")
            print("Raw response:")
            print(result["raw_response"])
            return None
            
    except Exception as e:
        print(f"\n✗ Error analyzing image: {str(e)}")
        return None


def display_nutrition_summary(nutrition_data):
    """
    Display a formatted summary of nutritional information.
    
    Args:
        nutrition_data (dict): Nutritional information dictionary
    """
    if not nutrition_data:
        print("No data to display")
        return
        
    print("\n" + "="*60)
    print("FOOD PRODUCT NUTRITIONAL INFORMATION")
    print("="*60)
    
    # Product Information
    print(f"\nProduct: {nutrition_data.get('product_name', 'N/A')}")
    print(f"Brand: {nutrition_data.get('brand', 'N/A')}")
    print(f"Type: {nutrition_data.get('product_type', 'N/A')}")
    print(f"Package Size: {nutrition_data.get('package_size', 'N/A')}")
    print(f"Serving Size: {nutrition_data.get('serving_size', 'N/A')}")
    
    # Nutritional Information
    nutrition = nutrition_data.get('nutritional_info_per_100g', {})
    if nutrition:
        print("\n" + "-"*60)
        print("NUTRITIONAL VALUES (per 100g/100ml)")
        print("-"*60)
        
        print(f"\nEnergy:")
        print(f"  - {nutrition.get('energy_kcal', 'N/A')} kcal")
        print(f"  - {nutrition.get('energy_kj', 'N/A')} kJ")
        
        print(f"\nCarbohydrates: {nutrition.get('carbohydrates_g', 'N/A')} g")
        print(f"  - Sugars: {nutrition.get('sugars_g', 'N/A')} g")
        if 'added_sugars_g' in nutrition and nutrition['added_sugars_g'] != 'N/A':
            print(f"  - Added Sugars: {nutrition.get('added_sugars_g')} g")
        
        print(f"\nFat: {nutrition.get('total_fat_g', 'N/A')} g")
        print(f"  - Saturated Fat: {nutrition.get('saturated_fat_g', 'N/A')} g")
        if 'trans_fat_g' in nutrition and nutrition['trans_fat_g'] != 'N/A':
            print(f"  - Trans Fat: {nutrition.get('trans_fat_g')} g")
        
        print(f"\nProtein: {nutrition.get('protein_g', 'N/A')} g")
        print(f"Fiber: {nutrition.get('fiber_g', 'N/A')} g")
        print(f"Sodium: {nutrition.get('sodium_mg', 'N/A')} mg")
        
        # Other nutrients
        other = nutrition.get('other_nutrients', {})
        if other:
            print(f"\nOther Nutrients:")
            for nutrient, value in other.items():
                print(f"  - {nutrient}: {value}")
    
    print("\n" + "="*60)


def allowed_file(filename, allowed_extensions):
    """
    Check if file extension is allowed.
    
    Args:
        filename (str): Name of the file
        allowed_extensions (set): Set of allowed file extensions
        
    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def calculate_inr_score(product_data, analysis, fssai_inr_baseline, o3_client):
    """
    Calculate INR score using o3-mini reasoning model.
    
    Args:
        product_data (dict): Product nutritional data
        analysis (dict): Nutrient analysis with % of INR
        fssai_inr_baseline (dict): FSSAI baseline values
        o3_client: Azure OpenAI client for o3-mini
        
    Returns:
        dict: INR score result with negative points, positive points, score, grade, etc.
    """
    import re
    import json
    
    reasoning_prompt = f"""You are an expert food nutrition analyst tasked with calculating the Indian Nutrition Rating (INR) score for a food product based on FSSAI guidelines.

**Product Information:**
- Product Type: {product_data.get('product_type', 'Solid')}
- Nutritional Information (per 100g):
  - Energy: {product_data['nutritional_info_per_100g']['energy_kcal']} kcal
  - Sugars: {product_data['nutritional_info_per_100g']['sugars_g']} g
  - Saturated Fat: {product_data['nutritional_info_per_100g']['saturated_fat_g']} g
  - Sodium: {product_data['nutritional_info_per_100g']['sodium_mg']} mg
  - Protein: {product_data['nutritional_info_per_100g']['protein_g']} g
  - Fiber: {product_data['nutritional_info_per_100g'].get('fiber_g', 'Not Available')}

**FSSAI INR Baseline Values (2000 kcal diet):**
- Energy: {fssai_inr_baseline['energy_kcal']} kcal
- Sugars: {fssai_inr_baseline['sugars_g']} g
- Saturated Fat: {fssai_inr_baseline['saturated_fat_g']} g
- Sodium: {fssai_inr_baseline['sodium_mg']} mg
- Protein: {fssai_inr_baseline['protein_g']} g
- Fiber: {fssai_inr_baseline['fiber_g']} g

**Nutrient Analysis (% of INR per 100g):**
- Energy: {analysis['energy_kcal']['percent_of_inr']:.1f}%
- Sugars: {analysis['sugars_g']['percent_of_inr']:.1f}%
- Saturated Fat: {analysis['saturated_fat_g']['percent_of_inr']:.1f}%
- Sodium: {analysis['sodium_mg']['percent_of_inr']:.1f}%
- Protein: {analysis['protein_g']['percent_of_inr']:.1f}%

**Task:**
Calculate the Indian Nutrition Rating (INR) score (0-100) using this methodology:

1. **Negative Points** (0-10 each, max 40 total):
   - Energy, Sugars, Saturated Fat, Sodium (capped at 10 points each)
   
2. **Positive Points** (0-5 each, max 10 total):
   - Protein, Fiber

3. **Final Score:**
   - Raw Score = (Total Positive - Total Negative) + 40
   - Scale to 0-100: Raw Score × 2
   - Grade: A (80-100), B (60-79), C (40-59), D (20-39), E (0-19)

**Output Format (JSON only):**
{{
    "negative_points": {{"energy": <val>, "sugars": <val>, "saturated_fat": <val>, "sodium": <val>, "total": <val>}},
    "positive_points": {{"protein": <val>, "fiber": <val>, "total": <val>}},
    "inr_score": <0-100>,
    "grade": "<A/B/C/D/E>",
    "interpretation": "<brief text>",
    "health_warnings": [<list>],
    "positive_claims": [<list>]
}}
"""
    
    response = o3_client.chat.completions.create(
        model="o3-mini",
        messages=[{"role": "user", "content": reasoning_prompt}],
        temperature=1,
        max_completion_tokens=5000
    )
    
    # Parse JSON from response
    response_text = response.choices[0].message.content
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    
    if json_match:
        return json.loads(json_match.group())
    return None


def calculate_nutrient_analysis(product_nutrition, fssai_inr_baseline):
    """
    Calculate percentage of INR for each nutrient.
    
    Args:
        product_nutrition (dict): Product nutritional information per 100g
        fssai_inr_baseline (dict): FSSAI baseline values
        
    Returns:
        dict: Analysis with per_100g, inr_baseline, and percent_of_inr for each nutrient
    """
    analysis = {}
    nutrients = ['energy_kcal', 'sugars_g', 'saturated_fat_g', 'sodium_mg', 'protein_g']
    
    for nutrient in nutrients:
        value = product_nutrition.get(nutrient, 0)
        if value == "Not Available" or value is None or value == "N/A":
            value = 0
        else:
            # Convert to float to handle string values
            try:
                value = float(value)
            except (ValueError, TypeError):
                value = 0
        
        baseline_key = nutrient
        if baseline_key not in fssai_inr_baseline:
            # Map to correct baseline key
            baseline_key = nutrient
            
        baseline = fssai_inr_baseline.get(baseline_key, 1)
        
        analysis[nutrient] = {
            "per_100g": value,
            "inr_baseline": baseline,
            "percent_of_inr": (value / baseline * 100) if value and baseline else 0
        }
    
    # Add fiber if available
    fiber = product_nutrition.get('fiber_g')
    if fiber != "Not Available" and fiber is not None and fiber != "N/A":
        try:
            fiber = float(fiber)
            analysis['fiber_g'] = {
                "per_100g": fiber,
                "inr_baseline": fssai_inr_baseline['fiber_g'],
                "percent_of_inr": (fiber / fssai_inr_baseline['fiber_g'] * 100)
            }
        except (ValueError, TypeError):
            pass
    
    return analysis


def create_nutrition_analysis_chain(api_key, fssai_inr_baseline, o3_client):
    """
    Create a LangChain SequentialChain for complete nutrition analysis pipeline.
    
    This chain orchestrates the entire process using LCEL (LangChain Expression Language):
    1. Extract nutrition from image (GPT-4o Vision)
    2. Calculate nutrient analysis (% of INR)
    3. Calculate INR score (o3-mini reasoning)
    
    Args:
        api_key (str): NetAIConnect API key
        fssai_inr_baseline (dict): FSSAI baseline values
        o3_client: Azure OpenAI client for o3-mini
        
    Returns:
        RunnableSequence: LangChain sequential chain
    """
    from langchain_core.runnables import RunnableLambda, RunnablePassthrough
    
    # Step 1: Extract nutrition information using GPT-4o Vision
    def extract_nutrition_step(inputs):
        """Extract nutrition from image"""
        image_path = inputs if isinstance(inputs, str) else inputs.get('image_path')
        
        extraction_result = extract_nutrition_info_gpt4o(image_path, api_key=api_key)
        
        if not extraction_result['success']:
            return {
                'success': False,
                'error': 'Nutrition extraction failed',
                'details': extraction_result.get('error'),
                'image_path': image_path
            }
        
        return {
            'success': True,
            'image_path': image_path,
            'product_data': extraction_result['data']
        }
    
    # Step 2: Calculate nutrient analysis (% of INR)
    def calculate_analysis_step(inputs):
        """Calculate nutrient analysis"""
        if not inputs.get('success'):
            return inputs  # Pass through errors
        
        product_data = inputs['product_data']
        
        analysis = calculate_nutrient_analysis(
            product_data['nutritional_info_per_100g'], 
            fssai_inr_baseline
        )
        
        return {
            'success': True,
            'image_path': inputs['image_path'],
            'product_data': product_data,
            'analysis': analysis
        }
    
    # Step 3: Calculate INR score using o3-mini reasoning
    def calculate_inr_step(inputs):
        """Calculate INR score"""
        if not inputs.get('success'):
            return inputs  # Pass through errors
        
        product_data = inputs['product_data']
        analysis = inputs['analysis']
        
        inr_result = calculate_inr_score(
            product_data, 
            analysis, 
            fssai_inr_baseline, 
            o3_client
        )
        
        if inr_result is None:
            return {
                'success': False,
                'error': 'INR score calculation failed',
                'image_path': inputs['image_path']
            }
        
        return {
            'success': True,
            'image_path': inputs['image_path'],
            'product_data': product_data,
            'analysis': analysis,
            'inr_result': inr_result
        }
    
    # Create the LangChain sequential chain using LCEL
    chain = (
        RunnableLambda(extract_nutrition_step)
        | RunnableLambda(calculate_analysis_step)
        | RunnableLambda(calculate_inr_step)
    )
    
    return chain
