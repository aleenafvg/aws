"""
bedrock_service.py – Amazon Bedrock integration for two AI tasks:

1. translate_to_english:
   Convert native-language user query into optimized English semantic search terms.

2. generate_response:
   Generate a grounded answer in the user's native language using Kendra context.

Uses Claude 3.5 Sonnet via Amazon Bedrock.

SECURITY:
  - Strict context-only prompting to prevent hallucination
  - No user data logged beyond what's needed
  - Model ID configured via environment variable
"""

import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("yojanasetu")

# ── Configuration ─────────────────────────────────────────────────
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20241022-v2:0"
)

# Language code to language name mapping
LANGUAGE_NAMES = {
    "hi-IN": "Hindi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "mr-IN": "Marathi",
    "bn-IN": "Bengali",
    "gu-IN": "Gujarati",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "pa-IN": "Punjabi",
    "en-IN": "English",
}

# Lazy-initialized client
_bedrock_client = None


def _get_bedrock():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime")
    return _bedrock_client


def translate_to_english(native_text, source_language):
    """
    Translate a native-language user query into optimized English search terms.

    The translation is not word-for-word but semantic – optimized for
    retrieval of government scheme documents via Kendra.

    Args:
        native_text: User's query in their native language
        source_language: Language code (e.g., "hi-IN")

    Returns:
        str: Optimized English search query

    Raises:
        RuntimeError: On Bedrock invocation failure
    """
    lang_name = LANGUAGE_NAMES.get(source_language, "regional Indian language")

    # If already English, just optimize the query
    if source_language == "en-IN":
        prompt = f"""Convert this spoken English query into optimized search terms 
for finding Indian government welfare schemes. Extract key concepts and 
return only the search query, nothing else.

User query: "{native_text}"

Optimized search terms:"""
    else:
        prompt = f"""You are a translation assistant. The following text is in {lang_name}.

1. Translate it to English.
2. Then convert it into optimized semantic search terms for finding 
   Indian government welfare schemes and benefits.
3. Return ONLY the optimized English search terms, nothing else.

{lang_name} text: "{native_text}"

Optimized English search terms:"""

    response_text = _invoke_bedrock(prompt, max_tokens=200)

    if not response_text:
        logger.warning("Empty translation from Bedrock, using native text as fallback")
        return native_text

    return response_text.strip()


def generate_response(native_transcript, english_query, context_passages, target_language):
    """
    Generate a grounded answer in the user's native language.

    CRITICAL RULES (anti-hallucination):
      - Answer MUST use only information from the provided context
      - Answer MUST be under 3 sentences
      - Answer MUST be in the target language
      - If no relevant info found, say so honestly in the target language

    Args:
        native_transcript: Original user query in native language
        english_query: Translated English query
        context_passages: List of relevant passages from Kendra
        target_language: Language code for the response

    Returns:
        str: AI-generated response in the target language
    """
    lang_name = LANGUAGE_NAMES.get(target_language, "the user's language")

    # Format context passages
    if context_passages:
        context_text = "\n\n".join([
            f"[Passage {i+1}]: {passage}"
            for i, passage in enumerate(context_passages[:5])  # Limit to top 5
        ])
    else:
        context_text = "No relevant information found in the database."

    prompt = f"""You are a helpful government schemes assistant for Indian citizens.

STRICT RULES:
1. Answer ONLY using the context provided below. Do NOT add information from your training data.
2. Keep your answer under 3 sentences, simple and clear.
3. Write your response in {lang_name} ({target_language}).
4. If the context does not contain relevant information, honestly say so in {lang_name}.
5. Use simple language suitable for rural citizens with low literacy.
6. Be direct and actionable – tell them what to do or where to go.

CONTEXT FROM GOVERNMENT SCHEMES DATABASE:
{context_text}

USER'S ORIGINAL QUESTION ({lang_name}):
"{native_transcript}"

ENGLISH TRANSLATION OF QUESTION:
"{english_query}"

Respond in {lang_name}:"""

    response_text = _invoke_bedrock(prompt, max_tokens=500)

    if not response_text:
        # Fallback: return a generic "sorry" message in the target language
        fallback_messages = {
            "hi-IN": "क्षमा करें, मुझे आपके प्रश्न का उत्तर नहीं मिल पाया। कृपया फिर से प्रयास करें।",
            "ta-IN": "மன்னிக்கவும், உங்கள் கேள்விக்கு பதில் கண்டுபிடிக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.",
            "te-IN": "క్షమించండి, మీ ప్రశ్నకు సమాధానం కనుగొనడం సాధ్యం కాలేదు. దయచేసి మళ్ళీ ప్రయత్నించండి.",
            "mr-IN": "क्षमस्व, मला तुमच्या प्रश्नाचे उत्तर सापडले नाही. कृपया पुन्हा प्रयत्न करा.",
            "bn-IN": "দুঃখিত, আপনার প্রশ্নের উত্তর খুঁজে পাওয়া যায়নি। আবার চেষ্টা করুন।",
            "gu-IN": "માફ કરશો, તમારા પ્રશ્નનો જવાબ મળ્યો નથી. કૃપા કરીને ફરીથી પ્રયાસ કરો.",
            "kn-IN": "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಪ್ರಶ್ನೆಗೆ ಉತ್ತರ ಸಿಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
            "ml-IN": "ക്ഷമിക്കണം, നിങ്ങളുടെ ചോദ്യത്തിന് ഉത്തരം കണ്ടെത്താനായില്ല. ദയവായി വീണ്ടും ശ്രമിക്കുക.",
            "pa-IN": "ਮਾਫ਼ ਕਰਨਾ, ਤੁਹਾਡੇ ਸਵਾਲ ਦਾ ਜਵਾਬ ਨਹੀਂ ਮਿਲ ਸਕਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
            "en-IN": "Sorry, I could not find an answer to your question. Please try again.",
        }
        return fallback_messages.get(target_language,
            "Sorry, I could not find an answer. Please try again.")

    return response_text.strip()


def _invoke_bedrock(prompt, max_tokens=500):
    """
    Invoke Amazon Bedrock with the given prompt.

    Uses the Anthropic Claude Messages API format.

    Args:
        prompt: Text prompt to send
        max_tokens: Maximum tokens in response

    Returns:
        str: Model response text, or empty string on failure
    """
    bedrock = _get_bedrock()

    try:
        request_body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": 0.1,  # Low temperature for factual, grounded responses
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        })

        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=request_body,
        )

        response_body = json.loads(response["body"].read())

        # Extract text from Claude's response format
        content = response_body.get("content", [])
        if content and isinstance(content, list):
            text_parts = [
                block.get("text", "")
                for block in content
                if block.get("type") == "text"
            ]
            return " ".join(text_parts)

        return ""

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"Bedrock invocation failed: {error_code}")
        if error_code == "ThrottlingException":
            raise RuntimeError("AI service is temporarily busy. Please try again.")
        raise RuntimeError("AI service error")

    except Exception as e:
        logger.error(f"Bedrock error: {str(e)}")
        raise RuntimeError("AI service error")
