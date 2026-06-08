import requests
import json
import logging
import os
from typing import Optional, Dict, Any
from langdetect import detect, detect_langs, LangDetectException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranslationService:
    """Translation service that uses LibreTranslate and Bhashini APIs"""
    
    def __init__(self):
        # Removed libretranslate urls
        
        # Bhashini API configuration
        self.bhashini_base_url = "https://meity-auth.ulcacontrib.org/ulca/apis/v0"
        self.bhashini_api_key = os.getenv("BHASHINI_API_KEY")
        self.bhashini_user_id = os.getenv("BHASHINI_USER_ID")
    
    def set_bhashini_credentials(self, api_key: str, user_id: str):
        """Set Bhashini API credentials"""
        self.bhashini_api_key = api_key
        self.bhashini_user_id = user_id
    
    def detect_language_with_confidence(self, text: str) -> tuple:
        """
        Detect language with confidence information
        Args:
            text: Text to detect language for
        Returns:
            Tuple of (language_code, is_ambiguous, alternative_language)
        """
        try:
            # For very short text, default to English to avoid misdetection
            if len(text.strip()) < 3:
                logger.info(f"Text too short ({len(text.strip())} chars), assuming English")
                return ("en", False, None)
            
            # Use langdetect to get probabilities
            probabilities = detect_langs(text)
            
            if not probabilities:
                return ("en", False, None)
            
            primary_lang = probabilities[0].lang
            primary_prob = probabilities[0].prob
            
            # Check for ambiguity - if top 2 languages are too close
            # OR if primary is non-English but contains English words
            is_ambiguous = False
            alternative_lang = None
            
            if len(probabilities) > 1 and probabilities[1].prob > 0.3 and (primary_prob - probabilities[1].prob) < 0.15:
                # High ambiguity between top 2 languages
                is_ambiguous = True
                alternative_lang = probabilities[1].lang
                logger.info(f"Language ambiguity detected: {primary_lang}({primary_prob:.2f}) vs {alternative_lang}({probabilities[1].prob:.2f})")
            
            logger.info(f"Detected language: {primary_lang} (confidence: {primary_prob:.2f}), ambiguous: {is_ambiguous}")
            return (primary_lang, is_ambiguous, alternative_lang)
            
        except Exception as e:
            logger.warning(f"Could not detect language for text: {text[:50]}, error: {str(e)}")
            return ("en", False, None)
    
    def detect_language(self, text: str) -> str:
        """
        Detect the language of the text with confidence checking
        Args:
            text: Text to detect language for
        Returns:
            Language code (e.g., 'en', 'hi', 'es') or 'en' if detection fails
        """
        lang, _, _ = self.detect_language_with_confidence(text)
        return lang
    
    def translate_with_google(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """
        Translate using Google Translate (via deep-translator package)
        """
        if source_lang == "auto":
            detected_lang = self.detect_language(text)
            if detected_lang == target_lang or detected_lang == target_lang[:2]:
                logger.info(f"Text is already in {target_lang}, skipping translation")
                return text
            source_lang = detected_lang
        
        if source_lang == "en" or source_lang.startswith("en"):
            logger.info(f"Source language is English, skipping translation")
            return text
            
        logger.info(f"Translating from {source_lang} to {target_lang} using Google Translate...")
        try:
            from deep_translator import GoogleTranslator
            google_source = source_lang if source_lang != "auto" else "auto"
            translator = GoogleTranslator(source=google_source, target=target_lang)
            translated = translator.translate(text)
            
            if translated and translated.strip().lower() != text.strip().lower():
                logger.info(f"Google translation successful: '{text[:40]}' -> '{translated[:40]}'")
                return translated
            else:
                logger.warning(f"Google translation returned unchanged text")
                return text
        except ImportError:
            logger.error("deep-translator is not installed. Please run: pip install deep-translator")
            return text
        except Exception as e:
            logger.error(f"Google translation error: {str(e)}")
            return text
    
    def translate_with_bhashini(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """
        Translate text using Bhashini API
        Args:
            text: Text to translate
            source_lang: Source language code (default: "auto")
            target_lang: Target language code (default: "en")
        Returns:
            Translated text or original text if translation fails
        """
        if not self.bhashini_api_key or not self.bhashini_user_id:
            logger.warning("Bhashini credentials not set")
            return text
        
        try:
            # Language code mapping for Bhashini
            lang_mapping = {
                "en": "en",
                "hi": "hi",
                "ta": "ta",
                "te": "te",
                "bn": "bn",
                "mr": "mr",
                "gu": "gu",
                "kn": "kn",
                "ml": "ml",
                "pa": "pa",
                "ur": "ur",
                "auto": "en"  # Default to English for auto detection
            }
            
            source = lang_mapping.get(source_lang, source_lang)
            target = lang_mapping.get(target_lang, target_lang)
            
            # Get pipeline configuration
            pipeline_url = f"{self.bhashini_base_url}/model/compute"
            headers = {
                "Authorization": f"{self.bhashini_user_id} {self.bhashini_api_key}",
                "Content-Type": "application/json"
            }
            
            # Translation pipeline request
            pipeline_data = {
                "pipelineTasks": [
                    {
                        "taskType": "translation",
                        "config": {
                            "language": {
                                "sourceLanguage": source,
                                "targetLanguage": target
                            }
                        }
                    }
                ],
                "inputData": [
                    {
                        "source": text
                    }
                ]
            }
            
            response = requests.post(pipeline_url, headers=headers, json=pipeline_data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                pipeline_response = result.get('pipelineResponse', [])
                
                if pipeline_response:
                    output = pipeline_response[0].get('output', [])
                    if output:
                        translated_text = output[0].get('target', text)
                        return translated_text
            
            logger.warning(f"Bhashini API error: {response.status_code}")
            return text
            
        except Exception as e:
            logger.error(f"Bhashini translation error: {str(e)}")
            return text
    
    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "en", 
                  preferred_service: str = "bhashini") -> str:
        """
        Translate text with Bhashini primary and Google fallback
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            preferred_service: Kept for compatibility, defaults to "bhashini"
        Returns:
            Translated text or original text if all services fail
        """
        if not text or not text.strip():
            return text
        
        text = text.strip()
        
        # Try Bhashini first (highly accurate for Indian languages)
        result = self.translate_with_bhashini(text, source_lang, target_lang)
        if result and result.strip().lower() != text.strip().lower():  # Translation successful
            return result
            
        # Fallback to Google Translate if Bhashini failed or returned unchanged text
        logger.info("Bhashini translation failed or skipped, falling back to Google Translate")
        return self.translate_with_google(text, source_lang, target_lang)
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get supported languages for translation
        Returns:
            Dictionary of language codes and names
        """
        return {
            "en": "English",
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu",
            "bn": "Bengali",
            "mr": "Marathi",
            "gu": "Gujarati",
            "kn": "Kannada",
            "ml": "Malayalam",
            "pa": "Punjabi",
            "ur": "Urdu"
        }

# Global translation service instance
translation_service = TranslationService()
