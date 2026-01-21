# PureCheck - Quick Start Guide

## Features

✅ **Image Upload** - Upload food product images via drag-and-drop or file selection
✅ **AI Analysis** - Automatic nutrition extraction using GPT-4o Vision
✅ **INR Score** - Indian Nutrition Rating calculated using o3-mini reasoning model
✅ **Chat Assistant** - Ask questions about products or FSSAI guidelines
✅ **Real-time Results** - Instant analysis with detailed nutritional breakdown

## How to Run

1. **Ensure environment variables are set** in `.env` file:
   ```
   NETAICONNECT_API_KEY=your_api_key_here
   PINECONE_API_KEY=your_pinecone_key_here
   ```

2. **Install dependencies** (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Open in browser**:
   ```
   http://localhost:5000
   ```

## Using the Application

### Upload & Analyze
1. Click on the upload area or drag-and-drop a food product image
2. Wait for AI analysis to complete
3. View the INR score, nutritional breakdown, and health warnings

### Chat Features
- **Product-specific questions**: After uploading, ask questions about the analyzed product
- **General FSSAI questions**: Ask about food safety regulations, guidelines, etc.
- **Examples**:
  - "Is this product healthy?"
  - "What does the high saturated fat mean?"
  - "What are FSSAI guidelines for sodium?"
  - "Can I consume this daily?"

## Features Overview

### 1. Image Upload
- Supports: PNG, JPG, JPEG, GIF, WEBP
- Max file size: 16MB
- Drag-and-drop or click to select

### 2. Nutrition Analysis
- Energy (kcal)
- Sugars (g)
- Saturated Fat (g)
- Sodium (mg)
- Protein (g)
- Fiber (g)

### 3. INR Score (0-100)
- **Grade A (80-100)**: Excellent
- **Grade B (60-79)**: Good
- **Grade C (40-59)**: Average
- **Grade D (20-39)**: Poor
- **Grade E (0-19)**: Very Poor

### 4. Chat Assistant
- Context-aware responses about uploaded products
- RAG-based answers for FSSAI guidelines
- Powered by GPT-4o

## API Endpoints

- `GET /` - Main page
- `POST /upload` - Upload and analyze image
- `POST /chat` - Send chat message
- `POST /clear-session` - Clear current session

## Troubleshooting

**Issue**: Image upload fails
- Check file format (must be image)
- Check file size (max 16MB)
- Ensure API keys are set correctly

**Issue**: Chat doesn't work
- Check NETAICONNECT_API_KEY is valid
- Ensure Pinecone index "purecheck-index" exists

**Issue**: INR score calculation fails
- Verify o3-mini model access
- Check API quota/limits

## Technology Stack

- **Backend**: Flask, Python
- **AI Models**: GPT-4o (Vision & Chat), o3-mini (Reasoning)
- **Vector DB**: Pinecone
- **Framework**: LangChain
- **Frontend**: HTML, CSS, JavaScript

## Notes

- First-time upload may take longer (model initialization)
- Chat context is maintained per session
- Clear session to analyze a new product
- All uploaded images are stored in `uploads/` folder
