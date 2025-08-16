# run.py (সঠিক এবং আপডেট করা সংস্করণ)

from app import create_app
from dotenv import load_dotenv
import os

# .env ফাইল থেকে এনভায়রনমেন্ট ভ্যারিয়েবল লোড করুন
load_dotenv()

# এখন create_app() কল করুন
app = create_app()

if __name__ == '__main__':
    # debug=True ব্যবহার করলে Flask এর ডিবাগার চলবে
    # আপনি প্রোডাকশনে এটি False রাখবেন
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')
