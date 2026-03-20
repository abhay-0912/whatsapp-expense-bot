import re
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import Client, create_client

app = FastAPI()

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")

supabase: Client = create_client(url, key)


def infer_category(message: str) -> str:
    text = message.lower()
    if any(word in text for word in ["zomato", "swiggy", "food", "lunch", "dinner", "breakfast", "restaurant"]):
        return "Food"
    if any(word in text for word in ["uber", "ola", "taxi", "metro", "bus", "fuel", "petrol", "diesel"]):
        return "Transport"
    if any(word in text for word in ["movie", "netflix", "party", "entertainment"]):
        return "Entertainment"
    return "Misc"


def parse_expense(message: str) -> tuple[int, str]:
    amount_match = re.search(r"(\d+(?:\.\d+)?)", message)
    if not amount_match:
        raise ValueError("No amount found in message")

    amount_raw = float(amount_match.group(1))
    if not amount_raw.is_integer():
        raise ValueError("Amount must be a whole number")

    amount = int(amount_raw)
    category = infer_category(message)
    return amount, category

@app.get("/")
def home():
    return {"message": "Server is running 🚀"}


@app.post("/webhook")
async def webhook(request: Request):
    form = await request.form()
    message = form.get("Body")
    user = form.get("From")

    if not message or not user:
        raise HTTPException(status_code=400, detail="Missing Body or From in form data")

    try:
        amount, category = parse_expense(message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = user.strip().lower()

    try:
        supabase.table("expenses").insert(
            {
                "user_id": user,
                "amount": amount,
                "category": category,
            }
        ).execute()
    except APIError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    response = supabase.table("expenses").select("*").eq("user_id", user).execute()
    data = response.data or []
    total = sum(int(item.get("amount", 0)) for item in data)

    twiml_response = f"""
<Response>
    <Message>Saved ₹{amount} under {category}. Total: ₹{total}</Message>
</Response>
"""

    return Response(content=twiml_response, media_type="application/xml")