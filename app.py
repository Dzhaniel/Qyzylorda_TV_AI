import os
import sys
import re
from flask import Flask, render_template, request, jsonify
from google import genai

# Windows жүйесіндегі қаріп мәселесін түпкілікті шешу
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY", "Сіздің API кілтіңіз")
client = genai.Client(api_key=API_KEY)

# Базаны жүктейміз
file_path = "news_database.txt"
lines = []

if os.path.exists(file_path):
    try:
        # Ең қауіпсіз UTF-8 оқу форматы
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
    except Exception as e:
        print(f"Файлды оқуда қате: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/archive', methods=['GET'])
def get_archive():
    return jsonify({'news': lines[:30]})

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    total_news = len(lines)
    categories = {'Мәдениет': 0, 'Спорт': 0, 'Технология': 0, 'Қоғам': 0}
    
    for line in lines:
        line_lower = line.lower()
        if any(word in line_lower for word in ['концерт', 'театр', 'мәдениет', 'әнші', 'көрме', 'өнер']):
            categories['Мәдениет'] += 1
        elif any(word in line_lower for word in ['спорт', 'жарыс', 'чемпионат', 'футбол', 'бокс', 'турнир', 'белбеу']):
            categories['Спорт'] += 1
        elif any(word in line_lower for word in ['it', 'технология', 'hub', 'ии', 'робот', 'цифрландыру', 'ai']):
            categories['Технология'] += 1
        else:
            categories['Қоғам'] += 1

    if total_news == 0:
        total_news = 1 

    analytics_data = {
        'total_news': len(lines),
        'views': f"{len(lines) * 150:,}",
        'active_days': max(1, len(lines) // 5),
        'categories': {
            'Мәдениет': round((categories['Мәдениет'] / total_news) * 100),
            'Спорт': round((categories['Спорт'] / total_news) * 100),
            'Технология': round((categories['Технология'] / total_news) * 100),
            'Қоғам': round((categories['Қоғам'] / total_news) * 100)
        }
    }
    return jsonify(analytics_data)

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.json
        user_question = data.get('question', '')
        
        if isinstance(user_question, str):
            user_question = user_question.encode('utf-8', errors='ignore').decode('utf-8')
        user_question = user_question.strip()
        
        if not user_question:
            return jsonify({'response': 'Сұрақ бос болуы мүмкін емес.'})
            
        question_lower = user_question.lower()
        relevant_chunks = []
        
        # КҮН мен АЙ-ды сандар арқылы немесе сөздермен ұстау
        numeric_date_match = re.search(r'(\d{1,2})[\./](\d{1,2})', question_lower)
        text_date_match = re.search(r'(\d{1,2})\s*([а-яәөғқңшіыі]+)', question_lower)
        
        months_dict = {
            'қаңтар': '01', 'ақпан': '02', 'наурыз': '03', 'сәуір': '04', 
            'мамыр': '05', 'маусым': '06', 'шілде': '07', 'тамыз': '08', 
            'қыркүйек': '09', 'қазан': '10', 'қараша': '11', 'желтоқсан': '12'
        }
        
        specific_date_found = False
        target_day = ""
        target_month_num = ""
        target_month_name = ""
        
        if numeric_date_match:
            target_day = numeric_date_match.group(1).zfill(2)
            target_month_num = numeric_date_match.group(2).zfill(2)
            specific_date_found = True
            for name, num in months_dict.items():
                if num == target_month_num:
                    target_month_name = name
                    break
        elif text_date_match:
            day_potential = text_date_match.group(1).zfill(2)
            month_word = text_date_match.group(2)
            for name, num in months_dict.items():
                if name in month_word:
                    target_day = day_potential
                    target_month_num = num
                    target_month_name = name
                    specific_date_found = True
                    break

        # Күн анықталса, сол күнге тиесілі блокты толық ұстаймыз
        if specific_date_found:
            search_pattern1 = f"{target_day}.{target_month_num}" # "05.12"
            search_pattern2 = f"{target_day} {target_month_name}" # "05 желтоқсан"
            
            for i, line in enumerate(lines):
                line_lower = line.lower()
                if search_pattern1 in line_lower or search_pattern2 in line_lower:
                    relevant_chunks.append(line)
                    # Мәтіннің жалғасы болып табылатын астындағы 5 жолды қоса ала кетеміз
                    for offset in range(1, 6):
                        if i + offset < len(lines):
                            next_line = lines[i + offset]
                            if not re.match(r'^\d{2}\.\d{2}\.\d{4}', next_line.strip()) and next_line not in relevant_chunks:
                                relevant_chunks.append(next_line)

        # Егер күн табылмаса, кілт сөздермен іздеу
        if not relevant_chunks:
            keywords = [word.lower() for word in user_question.split() if len(word) > 2 and not word.isdigit()]
            for line in lines:
                if any(keyword in line.lower() for keyword in keywords) or question_lower in line.lower():
                    if line not in relevant_chunks:
                        relevant_chunks.append(line)
                if len(relevant_chunks) >= 25:
                    break
                    
        context_data = "\n".join(relevant_chunks)
        
        if not context_data:
            return jsonify({'response': 'Бұл туралы соңғы 6 айда жаңалық шыққан жоқ немесе архивте бұл мәлімет табылмады.'})

        system_instruction = (
            "Сіз «Қызылорда ТВ» телеарнасының жаңалықтар архиві бойынша ресми ИИ Агентсіз.\n"
            "Пайдаланушы берген архив мәліметтеріне ғана сүйеніп, сұраққа тек қазақ тілінде толық әрі нақты жауап беріңіз.\n\n"
            "МҰҚЫЯТ ОРЫНДАҢЫЗ:\n"
            "1. Егер сұраныс нақты бір күнге қатысты болса, жауаптың ең басын мына форматта бастаңыз:\n"
            "   \"📅 **[Күн] [Ай] күнгі жаңалықтар архиві:**\\n\\n\"\n"
            "2. Сол күнге қатысты архивтегі барлық оқиғаларды қамтып, тезис түрінде көрсетіңіз.\n"
            "3. Өз ойыңыздан фактілер қоспаңыз, тек берілген мәтінді пайдаланыңыз.\n"
        )

        full_prompt = (
            f"{system_instruction}\n"
            f"Архив мәліметтері:\n{context_data}\n\n"
            f"Сұрақ: {user_question}\n"
            "Жауап:"
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt,
        )
        return jsonify({'response': response.text})
        
    except Exception as e:
        err_msg = str(e).encode('utf-8', errors='ignore').decode('utf-8')
        return jsonify({'response': f'Қателік орын алды: {err_msg}'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
