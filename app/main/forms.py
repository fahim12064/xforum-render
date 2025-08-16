# app/main/forms.py

from flask_wtf import FlaskForm
# --- এই লাইনে PasswordField যোগ করা হয়েছে ---
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, FileField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Email
from app.models import User
from flask_login import current_user

# --- PostForm ক্লাস ---
class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=100)])
    content = TextAreaField('Content', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    post_image = FileField('Upload Post Image')
    submit = SubmitField('Publish Post')

    def __init__(self, *args, **kwargs):
        super(PostForm, self).__init__(*args, **kwargs)
        from app.models import Category
        self.category_id.choices = [(c.id, c.name) for c in Category.query.order_by('name').all()]

# --- EditProfileForm ক্লাস ---
class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    bio = TextAreaField('Bio', validators=[Length(max=500)])
    telegram_username = StringField('Telegram Username', description='Enter your Telegram username without the @ symbol.')
    profile_picture = FileField('Update Profile Picture')
    submit = SubmitField('Save Changes')

# --- CommentForm ক্লাস ---
class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Submit Comment')

# --- EmptyForm ক্লাস ---
class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')

# --- SearchForm ক্লাস ---
class SearchForm(FlaskForm):
    q = StringField('Search', validators=[DataRequired()])

# --- ChangePasswordForm ক্লাস ---
class ChangePasswordForm(FlaskForm):
    """পাসওয়ার্ড পরিবর্তনের জন্য ফর্ম।"""
    old_password = PasswordField('Old Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long.')
    ])
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Change Password')

    def validate_old_password(self, old_password):
        """পুরোনো পাসওয়ার্ডটি সঠিক কিনা তা যাচাই করে।"""
        if not current_user.check_password(old_password.data):
            raise ValidationError('Incorrect old password. Please try again.')

class RequestResetForm(FlaskForm):
    """পাসওয়ার্ড রিসেটের জন্য ইমেইল চাওয়ার ফর্ম।"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

    def validate_email(self, email):
        """ইমেইলটি ডাটাবেসে আছে কিনা তা যাচাই করে।"""
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('There is no account with that email. You must register first.')

class ResetPasswordForm(FlaskForm):
    """নতুন পাসওয়ার্ড সেট করার ফর্ম।"""
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Reset Password')