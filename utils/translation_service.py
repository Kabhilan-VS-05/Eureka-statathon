import requests
import json
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranslationService:
    """Translation service that uses both Lingua and Bhashini APIs"""
    
    def __init__(self):
        # Bhashini API configuration
        self.bhashini_base_url = "https://meity-auth.ulcacontrib.org/ulca/apis/v0"
        self.bhashini_api_key = None  # Set your Bhashini API key here
        self.bhashini_user_id = None  # Set your Bhashini user ID here
        
        # Lingua API configuration
        self.lingua_base_url = "https://lingva.ml/api/v1"
    
    def set_bhashini_credentials(self, api_key: str, user_id: str):
        """Set Bhashini API credentials"""
        self.bhashini_api_key = api_key
        self.bhashini_user_id = user_id
    
    def translate_with_lingua(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """
        Translate text using Lingua API
        Args:
            text: Text to translate
            source_lang: Source language code (default: "auto")
            target_lang: Target language code (default: "en")
        Returns:
            Translated text or original text if translation fails
        """
        try:
            url = f"{self.lingua_base_url}/{source_lang}/{target_lang}/{requests.utils.quote(text)}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('translation', text)
            else:
                logger.warning(f"Lingua API error: {response.status_code}")
                return text
                
        except Exception as e:
            logger.error(f"Lingua translation error: {str(e)}")
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
                  preferred_service: str = "lingua") -> str:
        """
        Translate text using preferred service with fallback
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            preferred_service: Preferred service ("lingua" or "bhashini")
        Returns:
            Translated text or original text if all services fail
        """
        if not text or not text.strip():
            return text
        
        text = text.strip()
        
        # Try preferred service first
        if preferred_service == "bhashini":
            result = self.translate_with_bhashini(text, source_lang, target_lang)
            if result != text:  # Translation successful
                return result
            # Fallback to Lingua
            return self.translate_with_lingua(text, source_lang, target_lang)
        else:
            result = self.translate_with_lingua(text, source_lang, target_lang)
            if result != text:  # Translation successful
                return result
            # Fallback to Bhashini
            return self.translate_with_bhashini(text, source_lang, target_lang)
    
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
