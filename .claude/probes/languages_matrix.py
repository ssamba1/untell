"""languages routing matrix: script detection + catalogue selection for many scripts."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.languages import dominant_script, catalogue_for, registered

out = {}
probes = {
    "english": "The system reads the file and processes the records in order.",
    "german": "Der Dienst läuft hinter einem Lastverteiler und die Zustandsprüfung muss antworten.",
    "french": "Le système lit le fichier et traite les enregistrements dans l'ordre.",
    "spanish": "El sistema lee el archivo y procesa los registros en orden.",
    "chinese": "系统读取文件并按顺序处理记录。",
    "japanese": "システムはファイルを読み取り、レコードを順番に処理します。",
    "russian": "Система читает файл и обрабатывает записи по порядку.",
    "arabic": "يقرأ النظام الملف ويعالج السجلات بالترتيب.",
    "greek": "Το σύστημα διαβάζει το αρχείο και επεξεργάζεται τις εγγραφές με τη σειρά.",
    "hindi": "सिस्टम फ़ाइल पढ़ता है और रिकॉर्ड क्रम से संसाधित करता है।",
    "korean": "시스템은 파일을 읽고 레코드를 순서대로 처리합니다.",
    "hebrew": "המערכת קוראת את הקובץ ומעבדת את הרשומות בסדר.",
    "mixed_latin_cyrillic": "The system reads the file. Система читает файл.",
}
for name, t in probes.items():
    script = dominant_script(t)
    cat = catalogue_for(t)
    out[name] = {"script": script, "has_catalogue": cat is not None}
print(json.dumps(out, indent=1))
