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
    """Translation service using local NLLB model"""
    
    def __init__(self):
        pass
    
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
    
    def _get_nllb_model(self):
        """Lazy load the NLLB model to save memory if not needed"""
        if not hasattr(self, '_nllb_model'):
            logger.info("Loading NLLB-200-distilled-600M model locally (this may take a moment)...")
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            model_name = "facebook/nllb-200-distilled-600M"
            self._nllb_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._nllb_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            logger.info("NLLB model loaded successfully.")
        return self._nllb_tokenizer, self._nllb_model

    def _transliterate_if_romanized(self, text: str, lang_code: str) -> str:
        """
        If text is written in English letters but meant for an Indian language,
        transliterate it to native script before passing to NLLB.
        """
        import re
        
        # If text doesn't have many english letters, it's already native script
        english_letters = re.findall(r'[a-zA-Z]', text)
        if len(english_letters) < len(text.strip()) * 0.3:
            return text
            
        try:
            from indic_transliteration import sanscript
            
            # Map ISO code to indic_transliteration script name
            script_map = {
                "hi": sanscript.DEVANAGARI,
                "mr": sanscript.DEVANAGARI,
                "ta": sanscript.TAMIL,
                "te": sanscript.TELUGU,
                "bn": sanscript.BENGALI,
                "gu": sanscript.GUJARATI,
                "kn": sanscript.KANNADA,
                "ml": sanscript.MALAYALAM,
                "pa": sanscript.GURMUKHI,
            }
            
            target_script = script_map.get(lang_code)
            if not target_script:
                return text
                
            logger.info(f"Romanized text detected. Transliterating '{text}' to {target_script}...")
            # OPTITRANS is good for generic english-style spelling (e.g. naan oru nadikan)
            transliterated = sanscript.transliterate(text, sanscript.OPTITRANS, target_script)
            logger.info(f"Transliteration result: {transliterated}")
            return transliterated
        except ImportError:
            logger.warning("indic_transliteration not installed. Skipping transliteration.")
            return text
        except Exception as e:
            logger.error(f"Transliteration error: {e}")
            return text

    def translate_with_nllb(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """
        Translate using local NLLB model (No Language Left Behind)
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
            
        # Transliterate Romanized Indian languages to native script
        base_lang = source_lang.split("-")[0] if "-" in source_lang else source_lang
        text = self._transliterate_if_romanized(text, base_lang)
            
        # Map ISO codes to NLLB FLORES-200 codes
        nllb_lang_map = {
            "en": "eng_Latn",
            "hi": "hin_Deva",
            "ta": "tam_Taml",
            "te": "tel_Telu",
            "bn": "ben_Beng",
            "mr": "mar_Deva",
            "gu": "guj_Gujr",
            "kn": "kan_Knda",
            "ml": "mal_Mlym",
            "pa": "pan_Guru",
            "ur": "urd_Arab"
        }
        
        src_nllb = nllb_lang_map.get(source_lang, "eng_Latn")
        tgt_nllb = nllb_lang_map.get(target_lang, "eng_Latn")
        
        if src_nllb == tgt_nllb:
            return text
            
        logger.info(f"Translating from {src_nllb} to {tgt_nllb} using local NLLB...")
        try:
            tokenizer, model = self._get_nllb_model()
            
            tokenizer.src_lang = src_nllb
            inputs = tokenizer(text, return_tensors="pt")
            
            forced_bos_token_id = tokenizer.convert_tokens_to_ids(tgt_nllb)
            translated_tokens = model.generate(
                **inputs, forced_bos_token_id=forced_bos_token_id, max_length=150
            )
            
            translated = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
            
            if translated and translated.strip().lower() != text.strip().lower():
                logger.info(f"NLLB translation successful: '{text[:40]}' -> '{translated[:40]}'")
                return translated
            else:
                logger.warning(f"NLLB translation returned unchanged text")
                return text
                
        except ImportError:
            logger.error("transformers or torch is not installed. Please run: pip install transformers torch")
            return text
        except Exception as e:
            logger.error(f"NLLB translation error: {str(e)}")
            return text
    
    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "en", 
                  preferred_service: str = "nllb") -> str:
        """
        Translate text using the local NLLB model
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            preferred_service: Kept for compatibility, defaults to "nllb"
        Returns:
            Translated text or original text if translation fails
        """
        if not text or not text.strip():
            return text
        
        text = text.strip()
        return self.translate_with_nllb(text, source_lang, target_lang)
    
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
