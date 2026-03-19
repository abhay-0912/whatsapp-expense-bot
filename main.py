import re
import os

from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from pydantic import BaseModel
from supabase import Client, create_client

app = FastAPI()

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")

supabase: Client = create_client(url, key)


class WebhookPayload(BaseModel):
    message: str
    user: str


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
def webhook(payload: WebhookPayload):
    try:
        amount, category = parse_expense(payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = payload.user.strip().lower()

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

    return {
        "response": f"Saved ₹{amount} under {category}\nTotal: ₹{total}"
    }