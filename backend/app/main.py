from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal, get_db
from .models import User, Transaction
from .security import hash_password, check_password, make_token, token_user
from sklearn.ensemble import IsolationForest

app = FastAPI(title="FinSight AI API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    try:
        u = db.query(User).filter_by(email="demo@finsight.local").first()
        if not u:
            u = User(email="demo@finsight.local", name="Demo User", password=hash_password("DemoPass123!"))
            db.add(u); db.commit(); db.refresh(u)
            examples = [
                ("Monthly salary","Income","income",5200,1),("Groceries","Food","expense",126,2),
                ("Electricity","Utilities","expense",88,4),("Bus pass","Transport","expense",42,5),
                ("Freelance payment","Income","income",850,7),("Coffee","Dining","expense",18,8),
                ("Subscription","Services","expense",14,10),("Dinner","Dining","expense",74,12),
                ("Large demo purchase","Shopping","expense",1850,14),("Pharmacy","Health","expense",32,16),
            ]
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for d,c,k,a,days in examples:
                db.add(Transaction(owner_id=u.id, description=d, category=c, kind=k, amount=a, date=now-timedelta(days=days)))
            db.commit()
    finally: db.close()
seed()

class Login(BaseModel):
    email: str
    password: str
class NewTransaction(BaseModel):
    description: str = Field(min_length=2, max_length=180)
    category: str = Field(default="Other", max_length=80)
    kind: str
    amount: float = Field(gt=0, le=100000000)
    date: datetime | None = None
class Question(BaseModel):
    question: str = Field(min_length=2, max_length=500)

def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401, "Sign in required")
    sub = token_user(authorization[7:])
    if not sub: raise HTTPException(401, "Invalid or expired session")
    user = db.query(User).filter_by(id=int(sub)).first()
    if not user: raise HTTPException(401, "User not found")
    return user

@app.get("/")
def home(): return {"message":"FinSight AI API is running","docs":"/docs"}
@app.get("/api/health")
def health(): return {"status":"ok"}
@app.post("/api/auth/login")
def login(data: Login, db: Session=Depends(get_db)):
    u=db.query(User).filter_by(email=data.email.lower().strip()).first()
    if not u or not check_password(data.password,u.password): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":make_token(u.id),"token_type":"bearer"}
@app.get("/api/auth/me")
def me(u: User=Depends(current_user)): return {"id":u.id,"email":u.email,"name":u.name}

def rows_for(db,u):
    return db.query(Transaction).filter_by(owner_id=u.id).order_by(Transaction.date.desc()).all()
def summary(db,u):
    rows=rows_for(db,u)
    income=sum(t.amount for t in rows if t.kind=="income")
    expenses=sum(t.amount for t in rows if t.kind=="expense")
    cats={}
    months={}
    for t in rows:
        if t.kind=="expense": cats[t.category]=cats.get(t.category,0)+t.amount
        m=t.date.strftime("%Y-%m")
        months.setdefault(m,{"month":m,"income":0,"expenses":0})
        months[m]["income" if t.kind=="income" else "expenses"] += t.amount
    return {"total_income":round(income,2),"total_expenses":round(expenses,2),"net_cash_flow":round(income-expenses,2),
            "transaction_count":len(rows),"category_breakdown":[{"category":k,"amount":round(v,2)} for k,v in sorted(cats.items(),key=lambda x:-x[1])],
            "monthly_trend":[{k:round(v,2) if isinstance(v,float) else v for k,v in x.items()} for x in sorted(months.values(),key=lambda x:x["month"])]}
@app.get("/api/dashboard/summary")
def dashboard(db: Session=Depends(get_db),u: User=Depends(current_user)): return summary(db,u)
@app.get("/api/transactions")
def transactions(skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db),u:User=Depends(current_user)):
    return [{"id":t.id,"description":t.description,"category":t.category,"kind":t.kind,"amount":t.amount,"date":t.date.isoformat()} for t in rows_for(db,u)[skip:skip+limit]]
@app.post("/api/transactions",status_code=201)
def add_transaction(data:NewTransaction,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if data.kind not in ("income","expense"): raise HTTPException(422,"kind must be income or expense")
    t=Transaction(owner_id=u.id,description=data.description.strip(),category=data.category.strip() or "Other",kind=data.kind,amount=data.amount,date=(data.date or datetime.now(timezone.utc)).replace(tzinfo=None))
    db.add(t);db.commit();db.refresh(t)
    return {"id":t.id,"description":t.description,"category":t.category,"kind":t.kind,"amount":t.amount,"date":t.date.isoformat()}
@app.get("/api/alerts")
def alerts(db:Session=Depends(get_db),u:User=Depends(current_user)):
    exp=[t for t in rows_for(db,u) if t.kind=="expense"]
    if len(exp)<4:return []
    try:
        preds=IsolationForest(contamination=0.15,random_state=42).fit_predict([[t.amount] for t in exp])
        flagged=[t for t,p in zip(exp,preds) if p==-1]
    except Exception: flagged=[t for t in exp if t.amount>500]
    return [{"id":t.id,"description":t.description,"category":t.category,"amount":t.amount,"date":t.date.isoformat(),"reason":"Unusual amount in this demo dataset; review manually."} for t in flagged]
@app.post("/api/assistant")
def assistant(q:Question,db:Session=Depends(get_db),u:User=Depends(current_user)):
    s=summary(db,u); text=q.question.lower()
    if any(w in text for w in ["expense","spend","spent"]):
        answer=f"Recorded demo expenses total ${s['total_expenses']:,.2f}. Largest category: {s['category_breakdown'][0]['category']}." if s["category_breakdown"] else f"Recorded demo expenses total ${s['total_expenses']:,.2f}."
    elif any(w in text for w in ["income","earn","salary"]): answer=f"Recorded demo income totals ${s['total_income']:,.2f}."
    elif any(w in text for w in ["balance","net","cash flow"]): answer=f"Net cash flow is ${s['net_cash_flow']:,.2f} (income minus expenses)."
    elif any(w in text for w in ["alert","unusual","anomal"]): answer=f"{len(alerts(db,u))} transaction(s) are flagged for manual review; flags do not prove fraud."
    else: answer=f"There are {s['transaction_count']} transactions. Ask about expenses, income, net cash flow, or unusual transactions."
    return {"answer":answer,"disclaimer":"Demo analytics only; not financial advice."}
