from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
import os
SECRET = os.getenv("SECRET_KEY", "dev-only-secret-change-me")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(s): return pwd.hash(s)
def check_password(s, h): return pwd.verify(s, h)
def make_token(uid): return jwt.encode({"sub": str(uid), "exp": datetime.now(timezone.utc)+timedelta(hours=2)}, SECRET, algorithm="HS256")
def token_user(token):
    try: return jwt.decode(token, SECRET, algorithms=["HS256"]).get("sub")
    except JWTError: return None
