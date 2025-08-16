# C:\All_data\xforum\app\main\__init__.py

from flask import Blueprint

bp = Blueprint('main', __name__)

# এই ফাইলের শেষে routes এবং forms ইম্পোর্ট করা হয়
from app.main import routes, forms
