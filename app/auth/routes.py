# app/auth/routes.py

from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm
from app.models import User
from app import db, mail
from flask_mail import Message

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        if not user.confirmed:
            flash('Please confirm your email first! A new confirmation link has been sent.', 'warning')
            # যদি ইউজার লগইন করার চেষ্টা করে কিন্তু ইমেইল কনফার্ম না থাকে,
            # তাহলে একটি নতুন কনফার্মেশন ইমেইল পাঠানো যেতে পারে।
            try:
                token = user.get_confirmation_token()
                msg = Message('Confirm Your Email', sender=current_app.config['MAIL_USERNAME'], recipients=[user.email])
                msg.body = f'Please confirm your email by clicking the link: {url_for("auth.confirm_email", token=token, _external=True)}'
                mail.send(msg)
            except Exception as e:
                flash(f'Failed to send confirmation email: {str(e)}', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.index'))
    return render_template('auth/login.html', title='Login', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        try:
            db.session.add(user)
            db.session.commit()
            
            # --- এখানে মেথডের নাম ঠিক করা হয়েছে ---
            token = user.get_confirmation_token()
            
            msg = Message('Confirm Your Email', sender=current_app.config['MAIL_USERNAME'], recipients=[user.email])
            msg.body = f'Please confirm your email by clicking the link: {url_for("auth.confirm_email", token=token, _external=True)}'
            mail.send(msg)
            flash('A confirmation email has been sent! Please check your inbox.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {str(e)}', 'danger')
            return redirect(url_for('auth.register'))
    
    # ফর্ম ভ্যালিডেশন এররগুলো দেখানোর জন্য
    if request.method == 'POST':
        for field_name, errors in form.errors.items():
            field_label = getattr(form, field_name).label.text
            for error in errors:
                flash(f"Error in {field_label}: {error}", 'danger')

    return render_template('auth/register.html', title='Register', form=form)

@bp.route('/confirm/<token>')
def confirm_email(token):
    # --- এখানে মেথডের নাম ঠিক করা হয়েছে ---
    user = User.verify_confirmation_token(token)
    
    if not user:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.confirmed:
        flash('Your account is already confirmed. Please log in.', 'info')
    else:
        user.confirmed = True
        db.session.commit()
        flash('Your email has been confirmed! You can now log in.', 'success')
        
    return redirect(url_for('auth.login'))
