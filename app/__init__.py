# app/__init__.py

import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
# --- Flask-Admin এর জন্য নতুন ইম্পোর্ট ---
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
mail = Mail()
csrf = CSRFProtect()
# --- অ্যাডমিন অবজেক্ট তৈরি করা ---
admin = Admin(name='XForum Admin', template_mode='bootstrap4')

login.login_view = 'auth.login'

@login.unauthorized_handler
def unauthorized_callback():
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(status='error', message='login_required'), 401
    
    # --- এই endpoint টি এখন main ব্লুপ্রিন্টের অংশ ---
    return redirect(url_for('main.login_required_page'))

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.jinja_env.add_extension('jinja2.ext.do')

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    # --- অ্যাপের সাথে অ্যাডমিন প্যানেল যুক্ত করা ---
    admin.init_app(app)

    # ব্লুপ্রিন্ট রেজিস্টার করার আগে মডেল ইম্পোর্ট করা ভালো অভ্যাস
    from app import models

    # --- একটি কাস্টম ModelView তৈরি করা যা অ্যাক্সেস কন্ট্রোল করবে ---
    class AdminModelView(ModelView):
        def is_accessible(self):
            # শুধুমাত্র লগইন করা এবং is_admin ফ্ল্যাগ True থাকা ব্যবহারকারীরাই অ্যাক্সেস পাবে
            return current_user.is_authenticated and hasattr(current_user, 'is_admin') and current_user.is_admin

        def inaccessible_callback(self, name, **kwargs):
            # যদি অ্যাক্সেস না থাকে, তাহলে হোমপেজে পাঠিয়ে দেওয়া হবে
            return redirect(url_for('main.index'))

    # --- আমাদের মডেলগুলোর জন্য অ্যাডমিন প্যানেলে ভিউ যোগ করা ---
    admin.add_view(AdminModelView(models.User, db.session))
    admin.add_view(AdminModelView(models.Post, db.session))
    admin.add_view(AdminModelView(models.Comment, db.session))
    admin.add_view(AdminModelView(models.Category, db.session))
    admin.add_view(AdminModelView(models.Vote, db.session))
    admin.add_view(AdminModelView(models.Notification, db.session))

    # --- ব্লুপ্রিন্ট রেজিস্টার করা ---
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp) # url_prefix এখন auth/__init__.py থেকে আসছে

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app
