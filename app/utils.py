from app import db
from app.models import User


def add_admin(username):
    """Make an existing user an admin"""
    user = db.session.scalar(
        db.select(User).where(User.username == username)
    )
    if not user:
        print(f"User '{username}' not found")
        return
    if user.is_admin:
        print(f"User '{username}' is already an admin")
        return
    
    user.is_admin = True
    db.session.commit()
    print(f"User '{username}' has been granted admin privileges")


def check_admin(username):
    """Check if a user is admin"""
    user = db.session.scalar(
        db.select(User).where(User.username == username)
    )
    if user:
        print(f"Is '{username}' an admin? {user.is_admin}")
    else:
        print(f"User '{username}' not found")


def delete_admin(username):
    """Remove admin privileges from a user (delete admin role)"""
    user = db.session.scalar(
        db.select(User).where(User.username == username)
    )
    if not user:
        print(f"User '{username}' not found")
        return
    if not user.is_admin:
        print(f"User '{username}' is not an admin")
        return

    confirm = input(f"Are you sure you want to remove admin from '{username}'? (y/n): ")
    if confirm.lower() != "y":
        print("Action cancelled.")
        return

    user.is_admin = False
    db.session.commit()
    print(f"User '{username}' is no longer an admin")
