from datetime import datetime, timezone
from typing import Optional
import time
import json

from flask import current_app, url_for
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db, login

# ------------------------------
# Vote Model
# ------------------------------
class Vote(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False)
    post_id: Mapped[int] = mapped_column(ForeignKey('post.id'), nullable=False)
    vote_type: Mapped[str] = mapped_column(String(10), nullable=False)

    user: Mapped["User"] = relationship()
    post: Mapped["Post"] = relationship(back_populates="votes")

    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='_user_post_uc'),)


# ------------------------------
# User Model
# ------------------------------
class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    email: Mapped[str] = mapped_column(String(120), index=True, unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    profile_picture: Mapped[Optional[str]] = mapped_column(String(120), default='default.jpg')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_link: Mapped[Optional[str]] = mapped_column(String(120))
    last_notification_read_time: Mapped[Optional[float]] = mapped_column(db.Float)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    posts: Mapped[list["Post"]] = relationship(back_populates="author")
    comments: Mapped[list["Comment"]] = relationship(back_populates="author")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    # Password methods
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Token methods
    def get_confirmation_token(self, expires_sec=1800):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'confirm_user_id': self.id})

    @staticmethod
    def verify_confirmation_token(token, expires_sec=1800):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expires_sec)
            user_id = data.get('confirm_user_id')
            if user_id:
                return db.session.get(User, user_id)
        except:
            return None
        return None

    def get_reset_password_token(self, expires_sec=600):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'reset_user_id': self.id})

    @staticmethod
    def verify_reset_password_token(token, expires_sec=600):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expires_sec)
            user_id = data.get('reset_user_id')
            if user_id:
                return db.session.get(User, user_id)
        except:
            return None
        return None

    # Profile picture URL
    def profile_picture_url(self):
        if self.profile_picture and self.profile_picture != 'default.jpg':
            return url_for('static', filename=f'uploads/profiles/{self.profile_picture}', _external=False) + f'?v={int(time.time())}'
        return url_for('static', filename='uploads/profiles/default.jpg')

    # Notification count
    def new_notifications_count(self):
        last_read = self.last_notification_read_time or 0.0
        return db.session.scalar(
            db.select(db.func.count(Notification.id))
            .where(
                Notification.user_id == self.id,
                Notification.timestamp > last_read
            )
        )

    # Add notification
    def add_notification(self, name, data):
        db.session.query(Notification).filter_by(
            user_id=self.id,
            name=name,
            payload_json=json.dumps(data)
        ).delete()
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)

        notification_count = db.session.scalar(
            db.select(db.func.count(Notification.id)).where(Notification.user_id == self.id)
        )
        if notification_count > 150:
            oldest_notification = db.session.scalars(
                db.select(Notification)
                .where(Notification.user_id == self.id)
                .order_by(Notification.timestamp.asc())
            ).first()
            if oldest_notification:
                db.session.delete(oldest_notification)
        return n

    # --- নতুন প্রোপার্টি ---
    @property
    def post_count(self):
        """ব্যবহারকারীর মোট পোস্ট সংখ্যা রিটার্ন করে।"""
        return db.session.scalar(
            db.select(db.func.count(Post.id)).where(Post.author_id == self.id)
        )

    @property
    def total_likes_received(self):
        """ব্যবহারকারীর সব পোস্টে মোট প্রাপ্ত লাইকের সংখ্যা রিটার্ন করে।"""
        return db.session.scalar(
            db.select(db.func.count(Vote.id))
            .join(Post)
            .where(
                Post.author_id == self.id,
                Vote.vote_type == 'like'
            )
        )

    @property
    def total_points(self):
        """পয়েন্ট সিস্টেম অনুযায়ী মোট পয়েন্ট গণনা করে।"""
        post_points = self.post_count * 2
        like_points = self.total_likes_received * 1
        return post_points + like_points


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


# ------------------------------
# Category Model
# ------------------------------
class Category(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    posts: Mapped[list["Post"]] = relationship(back_populates="category")

    @property
    def post_count(self):
        """এই ক্যাটাগরিতে মোট পোস্ট সংখ্যা রিটার্ন করে।"""
        return len(self.posts)

    def __repr__(self):
        return f"<Category {self.name}>"


# ------------------------------
# Post Model
# ------------------------------
class Post(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    image: Mapped[Optional[str]] = mapped_column(String(120))
    author_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey('category.id'), nullable=False)

    author: Mapped["User"] = relationship(back_populates="posts")
    category: Mapped["Category"] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    votes: Mapped[list["Vote"]] = relationship(back_populates="post", cascade="all, delete-orphan")

    @property
    def likes(self):
        return db.session.query(db.func.count(Vote.id)).filter_by(post_id=self.id, vote_type='like').scalar()

    @property
    def dislikes(self):
        return db.session.query(db.func.count(Vote.id)).filter_by(post_id=self.id, vote_type='dislike').scalar()


# ------------------------------
# Comment Model
# ------------------------------
class Comment(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False)
    post_id: Mapped[int] = mapped_column(ForeignKey('post.id'), nullable=False)

    author: Mapped["User"] = relationship(back_populates="comments")
    post: Mapped["Post"] = relationship(back_populates="comments")

    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey('comment.id'))
    replies: Mapped[list["Comment"]] = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")
    parent: Mapped[Optional["Comment"]] = relationship("Comment", back_populates="replies", remote_side=[id])


# ------------------------------
# Notification Model
# ------------------------------
class Notification(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False)
    timestamp: Mapped[float] = mapped_column(db.Float, index=True, default=time.time)
    payload_json: Mapped[str] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="notifications")

    def get_payload(self):
        return json.loads(self.payload_json)

    def __repr__(self):
        return f'<Notification {self.name}>'
