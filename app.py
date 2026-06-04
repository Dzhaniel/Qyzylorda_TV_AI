# -*- coding: utf-8 -*-
import os
import re
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

GLOBAL_ARCHIVE_TEXT = ""

def load_archive_into_memory():
    global GLOBAL_ARCHIVE_TEXT
    archive_path = "news_database.txt"
    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                GLOBAL_ARCHIVE_TEXT = f.read()
        except Exception:
            with open(archive_path, "r", encoding="utf-8", errors="ignore") as f:
                GLOBAL_ARCHIVE_TEXT = f.read()
    else:
        GLOBAL_ARCHIVE_TEXT = ""

# Сервер қосылғанда файлды бір-ақ рет жадқа оқимыз
load_archive_into_memory()

# Пайдаланушы мәтінмен жазса, санға айналдыруға арналған сөздіктер
MONTHS_MAP = {
    "қаңтар": "01", "ақпан": "02", "наурыз": "03", "сәуір": "04",
    "мамыр": "05", "маусым": "06", "шілде": "07", "тамыз": "08",
    "қыркүйек": "09", "қазан": "10", "қараша": "11", "желтоқсан": "12"
}

WORDS_TO_NUM_MAP = {
    "бірінші": "01", "бірі": "01", "екінші": "02", "екі": "02", "үшінші": "03", "үші": "03",
    "tөртінші": "04", "төрті": "04", "бесінші": "05", "бесі": "05", "алтыншы": "06", "алтысы": "06",
    "жетінші": "07", "жетісі": "07", "сегізінші": "08", "сегізі": "08", "тоғызыншы": "09", "тоғызы": "09",
    "оныншы": "10", "оны": "10", "он бірінші": "11", "он екінші": "12", "он үшінші": "13", 
    "он төртінші": "14", "он бесінші": "15", "он алтыншы": "16", "он жетінші": "17", 
    "он сегізінші": "18", "он тоғызыншы": "19", "жиырмасыншы": "20", "жиырма": "20",
    "жиырма бірінші": "21", "жиырма екінші": "22", "отызыншы": "30", "отыз бірінші": "31"
}

def get_news_by_date(question, full_text):
    """ Пайдаланушы сұрағынан датаны тауып, сол күннің барлық жаңалықтарын жинап қайтару """
    if not full_text:
        return "Мәліметтер базасы бос."
        
    paragraphs = [p.strip() for p in full_text.split('\n') if len(p.strip()) > 10]
    q_lower = question.lower().strip()
    
    detected_day = None
    detected_month = None
    
    # 1. Сұрақтан сандық датаны іздеу (Мысалы: 15.12.2025 немесе 15.12)
    date_match = re.search(r'(\d{1,2})\.(\d{1,2})', q_lower)
    if date_match:
        detected_day = f"{int(date_match.group(1)):02d}"
        detected_month = f"{int(date_match.group(2)):02d}"
    
    # 2. Егер сандық табылса, бірақ сөзбен жазылса (Мысалы: "15 желтоқсан" немесе "он бесінші желтоқсан")
    if not detected_day:
        # Айды анықтау
        for m_name, m_num in MONTHS_MAP.items():
            if m_name in q_lower:
                detected_month = m_num
                break
        
        # Күнді анықтау (Мәтін түрінде)
        for w_day, n_day in WORDS_TO_NUM_MAP.items():
            if w_day in q_lower:
                detected_day = n_day
                break
                
        # Күнді анықтау (Егер санмен жазылса: "15 желтоқсан")
        if not detected_day and detected_month:
            day_num_match = re.search(r'\d{1,2}', q_lower)
            if day_num_match:
                detected_day = f"{int(day_num_match.group()):02d}"

    # Егер дата анықталса, датасеттен сәйкес келетін БАРЛЫҚ абзацтарды жинаймыз
    if detected_day and detected_month:
        search_pattern_1 = f"{detected_day}.{detected_month}"
        search_pattern_2 = f"{int(detected_day)}.{detected_month}" # Басында нөлі жоқ нұсқасы (15.12)
        
        found_news = []
        for p in paragraphs:
            if p.startswith(search_pattern_1) or p.startswith(search_pattern_2) or search_pattern_1 in p[:15] or search_pattern_2 in p[:15]:
                found_news.append(p)
                
        if found_news:
            # Табылған жаңалықтарды әдемі тізім етіп біріктіру
            result_text = f"📅 **{detected_day}.{detected_month} күнгі мұрағаттық жаңалықтар жинағы:**\n\n"
            for idx, news in enumerate(found_news, 1):
                # Басындағы датаны алып тастап, тек таза мәтінді әдемілеп шығару
                clean_news = re.sub(r'^\d{1,2}\.\d{1,2}(\.\d{4})?\s*-\s*', '', news)
                clean_news = re.sub(r'^\d{1,2}\.\d{1,2}(\.\d{4})?\s*', '', clean_news)
                result_text += f"{idx}. {clean_news}\n\n"
            return result_text

    # 3. Егер нақты дата табылмаса, маңызды кілт сөздермен іздеп көру (ИИ, Спорт, т.б.)
    words = q_lower.replace('?', '').replace(',', '').replace('.', '').split()
    stop_words = {"қандай", "болды", "туралы", "айтып", "берші", "екен", "жаңалықтар", "болған", "күні", "не"}
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    
    if keywords:
        found_by_keywords = []
        for p in paragraphs:
            if any(kw in p.lower() for kw in keywords):
                found_by_keywords.append(p)
            if len(found_by_keywords) >= 3: # Ең көп дегенде 3 үзінді
                break
                
        if found_by_keywords:
            result_text = f"🔍 **\"{question}\" сұранысы бойынша мұрағаттан табылған сәйкестіктер:**\n\n"
            for idx, news in enumerate(found_by_keywords, 1):
                result_text += f"{idx}. {news}\n\n"
            return result_text

    return f"Кешіріңіз, мұрағат мәліметтерінде бұл күн немесе сұраныс бойынша ешқандай жаңалық табылмады."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask_bot():
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'response': 'Сұрақ бос.'}), 400
            
        question = data['question'].strip()
        
        # ТІКЕЛЕЙ ДАТАСЕТТЕН СҮЗГІЛЕП ЖАУАП ҚАЙТАРУ (API КІЛТСІЗ)
        reply = get_news_by_date(question, GLOBAL_ARCHIVE_TEXT)
        
        return jsonify({'response': reply})
        
    except Exception as e:
        return jsonify({'response': f"Жүйелік қате орын алды. Қайтадан байқап көріңіз."})

@app.route('/api/archive', methods=['GET'])
def get_archive_list():
    if not GLOBAL_ARCHIVE_TEXT:
        return jsonify({'news': []})
    lines = [line.strip() for line in GLOBAL_ARCHIVE_TEXT.split('\n') if len(line.strip()) > 10]
    return jsonify({'news': lines[:20]})

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    total_chars = len(GLOBAL_ARCHIVE_TEXT)
    total_lines = len([l for l in GLOBAL_ARCHIVE_TEXT.split('\n') if len(l.strip()) > 5])
    return jsonify({
        'total_news': total_lines,
        'views': (total_chars // 150) if total_chars > 0 else 0,
        'active_days': 15,
        'categories': {'Қоғам': 45, 'Мәдениет': 25, 'Технология': 20, 'Спорт': 10}
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
