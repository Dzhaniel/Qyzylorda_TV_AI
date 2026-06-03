import os
import sys
from flask import Flask, render_template, request, jsonify
from google import genai

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY", "ОСЫ ЖЕРГЕ ӨЗ API КІЛТІҢІЗДІ ҚОЙЫҢЫЗ")
client = genai.Client(api_key=API_KEY)

# Базаны жүктейміз
file_path = "news_database.txt"
if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        # Бос жолдарды алып тастап, тізім жасаймыз
        lines = [line.strip() for line in f.readlines() if line.strip()]
else:
    lines = []

@app.route('/')
def home():
    return render_template('index.html')

# 1. Жаңалықтар архиві бөліміне арналған API
@app.route('/api/archive', methods=['GET'])
def get_archive():
    # Алғашқы 30 жаңалықты фронтендке тізім ретінде жібереміз
    return jsonify({'news': lines[:30]})

# 2. Аналитика бөліміне арналған API (Статистикалық мәліметтер)
@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    total_news = len(lines)
    
    # Бастапқы санаттар көрсеткіші
    categories = {
        'Мәдениет': 0,
        'Спорт': 0,
        'Технология': 0,
        'Қоғам': 0
    }
    
    # Кілт сөздер бойынша жаңалықтарды автоматты түрде санаттарға бөлу
    for line in lines:
        line_lower = line.lower()
        if any(word in line_lower for word in ['концерт', 'театр', 'мәдениет', 'әнші', 'көрме', 'өнер']):
            categories['Мәдениет'] += 1
        elif any(word in line_lower for word in ['спорт', 'жарыс', 'чемпионат', 'футбол', 'бокс', 'турнир', 'белбеу']):
            categories['Спорт'] += 1
        elif any(word in line_lower for word in ['it', 'технология', 'hub', 'ии', 'робот', 'цифрландыру', 'ai']):
            categories['Технология'] += 1
        else:
            # Қалған жаңалықтардың бәрін әлеуметтік/қоғамдық салаға жатқызамыз
            categories['Қоғам'] += 1

    # Егер база бос болса, қателік кетпеуі үшін нөлдік тексеріс
    if total_news == 0:
        total_news = 1 

    # Проценттік үлестерін нақты есептейміз
    analytics_data = {
        'total_news': len(lines),  # Файлдан оқылған нақты жаңалық саны
        'views': f"{len(lines) * 150:,}", # Шартты түрде: әр жаңалыққа орташа есеппен 150 қаралымнан бердік
        'active_days': max(1, len(lines) // 5), # Шартты түрде: күніне орташа 5 жаңалық шықты деп алдық
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
    data = request.json
    user_question = data.get('question', '').strip()
    
    if not user_question:
        return jsonify({'response': 'Сұрақ бос болуы мүмкін емес.'})
        
    keywords = [word.lower() for word in user_question.split() if len(word) > 2]
    relevant_chunks = []
    
    for line in lines:
        if any(keyword in line.lower() for keyword in keywords) or user_question.lower() in line.lower():
            relevant_chunks.append(line)
            if len(relevant_chunks) >= 8:
                break
                
    context_data = "\n".join(relevant_chunks)
    
    if not context_data:
        return jsonify({'response': 'Бұл туралы соңғы 6 айда жаңалық шыққан жоқ.'})

    full_prompt = (
        "Сен Қызылорда ТВ телеарнасының жаңалықтар архиві бойынша көмекшісің.\n"
        "Төменде берілген архив мәліметтеріне сүйеніп, қойылған сұраққа тек қазақ тілінде қысқа, нақты жауап бер.\n\n"
        f"Архив мәліметтері:\n{context_data}\n\n"
        f"Сұрақ: {user_question}\n"
        "Жауап:"
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt,
        )
        return jsonify({'response': response.text})
    except Exception as e:
        return jsonify({'response': f'Қателік орын алды: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)