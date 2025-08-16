# app/main/routes.py
from flask import render_template, flash, redirect, url_for, request, current_app, abort, g, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import time
from app.main import bp
from app.main.forms import (
    PostForm, EditProfileForm, CommentForm, EmptyForm,
    SearchForm, ChangePasswordForm, RequestResetForm, ResetPasswordForm
)
from app import db, mail
from flask_mail import Message
from app.models import Post, Category, User, Comment, Vote, Notification
import json
from sqlalchemy import or_
from datetime import datetime, timezone

@bp.before_app_request
def before_request():
    g.search_form = SearchForm()

def send_password_reset_email(user):
    token = user.get_reset_password_token()
    msg = Message('Password Reset Request', sender=current_app.config['MAIL_USERNAME'], recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('main.reset_token', token=token, _external=True)}
If you did not make this request then simply ignore this email and no changes will be made.'''
    mail.send(msg)

def save_picture(form_picture, user_id):
    if current_user.profile_picture != 'default.jpg':
        old_picture_path = os.path.join(current_app.root_path, 'static/uploads/profiles', current_user.profile_picture)
        if os.path.exists(old_picture_path):
            os.remove(old_picture_path)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = f"user_{user_id}{f_ext}"
    picture_path = os.path.join(current_app.root_path, 'static/uploads/profiles', picture_fn)
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)
    form_picture.save(picture_path)
    return picture_fn

@bp.route('/')
@bp.route('/index')
def index():
    page = request.args.get('page', 1, type=int)
    category_id_str = request.args.get('category_id', '')

    all_categories_query = db.select(Category).order_by(Category.name)
    all_categories = db.session.scalars(all_categories_query).all()
    idea_category = next((c for c in all_categories if c.name.lower() == 'idea'), None)
    story_categories = [c for c in all_categories if c.name.lower() != 'idea']

    query = db.select(Post).order_by(Post.created_at.desc())

    if not category_id_str and idea_category:
        category_id_str = str(idea_category.id)

    if category_id_str.isdigit():
        category_id = int(category_id_str)
        query = query.filter(Post.category_id == category_id)
    elif category_id_str == 'all_stories':
        story_cat_ids = [c.id for c in story_categories]
        if story_cat_ids:
            query = query.filter(Post.category_id.in_(story_cat_ids))
        else:
            query = query.filter(Post.id == -1) # No stories to show

    posts = db.paginate(query, page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)

    total_posts = db.session.scalar(db.select(db.func.count(Post.id)))
    all_users = db.session.scalars(db.select(User)).all()
    top_contributors = sorted(all_users, key=lambda u: u.total_points, reverse=True)[:5]

    stats = {
        'total_posts': total_posts,
        'categories': all_categories,
        'top_contributors': top_contributors
    }

    return render_template(
        'index.html',
        title='Home',
        posts=posts,
        idea_category=idea_category,
        story_categories=story_categories,
        stats=stats,
        current_category_id=category_id_str
    )

@bp.route('/search')
def search():
    query = request.args.get('q', '', type=str).strip()
    if not query:
        return redirect(url_for('main.index'))
    if g.search_form:
        g.search_form.q.data = query
    page = request.args.get('page', 1, type=int)
    search_query = db.select(Post).join(Post.author).filter(
        or_(
            Post.title.ilike(f'%{query}%'),
            Post.content.ilike(f'%{query}%'),
            User.username.ilike(f'%{query}%')
        )
    ).order_by(Post.created_at.desc())
    posts = db.paginate(search_query, page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    return render_template('search_results.html', title=f'Search Results for "{query}"', posts=posts, query=query)

@bp.route('/vote/<int:post_id>/<string:vote_type>', methods=['POST'])
@login_required
def vote(post_id, vote_type):
    post = db.get_or_404(Post, post_id)
    if vote_type not in ['like', 'dislike']:
        return jsonify({'status': 'error', 'message': 'Invalid vote type'}), 400
    existing_vote = db.session.scalar(db.select(Vote).where(Vote.user_id == current_user.id, Vote.post_id == post_id))
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            db.session.delete(existing_vote)
        else:
            existing_vote.vote_type = vote_type
    else:
        new_vote = Vote(user_id=current_user.id, post_id=post_id, vote_type=vote_type)
        db.session.add(new_vote)
        if post.author != current_user and vote_type == 'like':
            post.author.add_notification('new_like', {
                'liker_username': current_user.username,
                'post_id': post.id,
                'post_title': post.title
            })
    db.session.commit()
    return jsonify({'status': 'success', 'likes': post.likes, 'dislikes': post.dislikes})

@bp.route('/user/<username>')
def user_profile(username):
    user = db.session.scalar(db.select(User).where(User.username == username))
    if user is None:
        abort(404)
    page = request.args.get('page', 1, type=int)
    posts_query = db.select(Post).where(Post.author == user).order_by(Post.created_at.desc())
    posts = db.paginate(posts_query, page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    return render_template('user_profile.html', user=user, posts=posts, title=f"{user.username}'s Profile")

@bp.route('/profile')
@login_required
def profile():
    return redirect(url_for('main.user_profile', username=current_user.username))

@bp.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = db.get_or_404(Post, post_id)
    form = CommentForm()
    if request.method == 'POST':
        if not current_user.is_authenticated:
            return jsonify({'status': 'error', 'message': 'login_required'}), 401
        if form.validate_on_submit():
            parent_id_str = request.form.get('parent_id')
            parent_id = int(parent_id_str) if parent_id_str else None
            comment = Comment(content=form.content.data, author=current_user, post=post, parent_id=parent_id)
            db.session.add(comment)
            if parent_id:
                parent_comment = db.session.get(Comment, parent_id)
                if parent_comment.author != current_user:
                    parent_comment.author.add_notification('new_reply', {
                        'replier_username': current_user.username,
                        'post_id': post.id,
                        'post_title': post.title,
                        'comment_id': comment.id
                    })
            else:
                if post.author != current_user:
                    post.author.add_notification('new_comment', {
                        'commenter_username': current_user.username,
                        'post_id': post.id,
                        'post_title': post.title,
                        'comment_id': comment.id
                    })
            db.session.commit()
            comment_html = render_template('_comment.html', comment=comment, post=post, form=form, current_user=current_user)
            return jsonify({'status': 'success', 'comment_html': comment_html, 'parent_id': parent_id})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid form data'}), 400
    comments = db.session.scalars(
        db.select(Comment).where(Comment.post_id == post_id, Comment.parent_id.is_(None)).order_by(Comment.created_at.asc())
    ).all()
    return render_template('post_detail.html', title=post.title, post=post, form=form, comments=comments)

@bp.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user, category_id=form.category_id.data)
        if form.post_image.data:
            file = form.post_image.data
            filename = secure_filename(f"{current_user.id}_{int(time.time())}_{file.filename}")
            file_path = os.path.join(current_app.root_path, 'static/uploads/posts', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            post.image = filename
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('main.index', category_id=post.category_id))
    return render_template('create_post.html', title='Create Post', form=form)

@bp.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = db.get_or_404(Post, post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm(obj=post)
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        post.category_id = form.category_id.data
        if form.post_image.data:
            pass
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('main.post_detail', post_id=post.id))
    return render_template('edit_post.html', title='Edit Post', form=form)

@bp.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = db.get_or_404(Post, post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Post has been deleted.', 'success')
    next_page = request.args.get('next') or url_for('main.index')
    return redirect(next_page)

@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.bio = form.bio.data
        telegram_user = form.telegram_username.data
        current_user.telegram_link = telegram_user.lstrip('@') if telegram_user else None
        if form.profile_picture.data:
            picture_file = save_picture(form.profile_picture.data, current_user.id)
            current_user.profile_picture = picture_file
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('main.user_profile', username=current_user.username))
    return render_template('edit_profile.html', title='Edit Profile', form=form)

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Your password has been changed successfully!', 'success')
        return redirect(url_for('main.user_profile', username=current_user.username))
    return render_template('change_password.html', title='Change Password', form=form)

@bp.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).filter_by(email=form.email.data))
        if user:
            send_password_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('reset_request.html', title='Reset Password', form=form)

@bp.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_password_token(token)
    if user is None:
        flash('That is an invalid or expired token.', 'warning')
        return redirect(url_for('main.reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been updated! You are now able to log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

@bp.route('/notifications')
@login_required
def notifications():
    notifications_query = db.select(Notification).where(
        Notification.user_id == current_user.id
    ).order_by(Notification.timestamp.desc())
    notifications = db.session.scalars(notifications_query).all()
    
    current_user.last_notification_read_time = time.time()
    db.session.commit()
    
    return render_template('notifications.html', notifications=notifications)

@bp.route('/login_required')
def login_required_page():
    """লগইন করার জন্য কাস্টম পেজ"""
    return render_template('login_required.html'), 401
