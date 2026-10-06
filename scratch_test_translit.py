import sys
import os

# Add project root to sys.path
PROJECT_ROOT = r"d:\The Project\statathon1.1"
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.translation_service import translation_service

# Test Tamil
tam_text_native = "நான் ஒரு நடிகன்"
tam_text_roman = "naan oru nadikan"

print("Native Tamil -> English:")
print(translation_service.translate_with_nllb(tam_text_native, source_lang="ta", target_lang="en"))

print("\nRomanized Tamil -> English:")
print(translation_service.translate_with_nllb(tam_text_roman, source_lang="ta", target_lang="en"))

# Test Hindi
hin_text_native = "मैं एक सॉफ्टवेयर इंजीनियर हूँ"
hin_text_roman = "main ek software engineer hoon"

print("\nNative Hindi -> English:")
print(translation_service.translate_with_nllb(hin_text_native, source_lang="hi", target_lang="en"))

print("\nRomanized Hindi -> English:")
print(translation_service.translate_with_nllb(hin_text_roman, source_lang="hi", target_lang="en"))
