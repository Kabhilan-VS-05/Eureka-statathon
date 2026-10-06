from indic_transliteration import sanscript
from indic_transliteration.sanscript import SchemeMap, SCHEMES, transliterate

# Try OPTITRANS, which handles common english romanizations nicely
tamil_text = transliterate("naan oru nadikan", sanscript.OPTITRANS, sanscript.TAMIL)
hindi_text = transliterate("main ek software engineer hoon", sanscript.OPTITRANS, sanscript.DEVANAGARI)

with open("scratch_indic_out.txt", "w", encoding="utf-8") as f:
    f.write(f"Tamil (Optitrans): {tamil_text}\n")
    f.write(f"Hindi (Optitrans): {hindi_text}\n")

# Try ITRANS
tamil_text2 = transliterate("naan oru nadikan", sanscript.ITRANS, sanscript.TAMIL)
hindi_text2 = transliterate("main ek software engineer hoon", sanscript.ITRANS, sanscript.DEVANAGARI)

with open("scratch_indic_out.txt", "a", encoding="utf-8") as f:
    f.write(f"Tamil (Itrans): {tamil_text2}\n")
    f.write(f"Hindi (Itrans): {hindi_text2}\n")
