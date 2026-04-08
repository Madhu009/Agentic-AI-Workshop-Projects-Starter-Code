import streamlit as st
from groq import Groq
import json
import csv
import io
from datetime import datetime

st.set_page_config(page_title="Personal Finance Coach Agent", layout="wide")
st.title("💰 Personal Finance Coach Agent")
st.markdown("**Track expenses • Analyze spending • Budgeting advice • Savings predictions • Remembers your goals**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("📊 Your Financial Profile")
    monthly_income = st.number_input("Monthly Income (USD)", min_value=0, max_value=100000, 
                                      value=st.session_state.get("monthly_income", 3000), step=100)
    st.session_state.monthly_income = monthly_income

    savings_goal = st.text_input("Savings Goal", 
                                  value=st.session_state.get("savings_goal", ""),
                                  placeholder="e.g. Save $5000 for emergency fund by December")
    if savings_goal:
        st.session_state.savings_goal = savings_goal

    currency = st.selectbox("Currency", ["USD", "INR", "EUR", "GBP"], index=0)
    st.session_state.currency = currency

    st.divider()
    st.header("📂 Upload Expenses CSV")
    uploaded_csv = st.file_uploader("Upload CSV (columns: date, category, amount, description)", type=["csv"])

    st.divider()
    st.header("➕ Quick Add Expense")
    with st.form("add_expense"):
        exp_category = st.selectbox("Category", ["Food", "Transport", "Rent", "Shopping", "Entertainment", 
                                                   "Utilities", "Health", "Education", "Subscriptions", "Other"])
        exp_amount = st.number_input("Amount", min_value=0.0, step=1.0)
        exp_desc = st.text_input("Description", placeholder="e.g. Lunch at cafe")
        if st.form_submit_button("Add Expense"):
            if exp_amount > 0:
                st.session_state.expenses.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "category": exp_category,
                    "amount": exp_amount,
                    "description": exp_desc
                })
                st.success(f"Added: {exp_category} — ${exp_amount}")

# ====================== SESSION STATE ======================
if "expenses" not in st.session_state:
    st.session_state.expenses = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "savings_goal" not in st.session_state:
    st.session_state.savings_goal = ""

# ====================== PROCESS CSV ======================
if uploaded_csv:
    try:
        content = uploaded_csv.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            st.session_state.expenses.append({
                "date": row.get("date", datetime.now().strftime("%Y-%m-%d")),
                "category": row.get("category", "Other"),
                "amount": float(row.get("amount", 0)),
                "description": row.get("description", "")
            })
        st.sidebar.success(f"✅ Loaded {len(list(csv.DictReader(io.StringIO(content))))} expenses from CSV")
    except Exception as e:
        st.sidebar.error(f"Error reading CSV: {e}")

# ====================== TOOLS ======================
def analyze_spending() -> str:
    """Analyze spending patterns from tracked expenses"""
    if not st.session_state.expenses:
        return "No expenses tracked yet. Add expenses in the sidebar or upload a CSV."

    expenses = st.session_state.expenses
    total = sum(e["amount"] for e in expenses)
    by_category = {}
    for e in expenses:
        cat = e["category"]
        by_category[cat] = by_category.get(cat, 0) + e["amount"]

    sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    income = st.session_state.get("monthly_income", 0)

    analysis = {
        "total_expenses": round(total, 2),
        "monthly_income": income,
        "remaining": round(income - total, 2),
        "savings_rate": f"{round((income - total) / income * 100, 1)}%" if income > 0 else "N/A",
        "num_transactions": len(expenses),
        "spending_by_category": {cat: round(amt, 2) for cat, amt in sorted_cats},
        "top_category": sorted_cats[0][0] if sorted_cats else "None",
        "top_category_amount": round(sorted_cats[0][1], 2) if sorted_cats else 0
    }
    return json.dumps(analysis, indent=2)


def calculate_budget(income: float, savings_target_pct: float) -> str:
    """Calculate a recommended budget breakdown"""
    savings = income * (savings_target_pct / 100)
    remaining = income - savings

    budget = {
        "monthly_income": income,
        "savings_target": f"{savings_target_pct}%",
        "savings_amount": round(savings, 2),
        "recommended_budget": {
            "Rent/Housing": round(remaining * 0.30, 2),
            "Food": round(remaining * 0.20, 2),
            "Transport": round(remaining * 0.10, 2),
            "Utilities": round(remaining * 0.10, 2),
            "Entertainment": round(remaining * 0.10, 2),
            "Health": round(remaining * 0.05, 2),
            "Education": round(remaining * 0.05, 2),
            "Miscellaneous": round(remaining * 0.10, 2)
        },
        "tip": "Adjust percentages based on your lifestyle. Aim to increase savings over time."
    }
    return json.dumps(budget, indent=2)


def predict_savings(months: int) -> str:
    """Predict savings for the next N months based on current spending"""
    expenses = st.session_state.expenses
    income = st.session_state.get("monthly_income", 0)

    if not expenses or income == 0:
        return json.dumps({"error": "Need expenses data and income to predict. Add expenses first."})

    total_spent = sum(e["amount"] for e in expenses)
    avg_monthly = total_spent  # Assume current expenses represent one month
    monthly_savings = income - avg_monthly

    predictions = []
    cumulative = 0
    for m in range(1, months + 1):
        cumulative += monthly_savings
        predictions.append({"month": m, "projected_savings": round(cumulative, 2)})

    result = {
        "monthly_income": income,
        "avg_monthly_expenses": round(avg_monthly, 2),
        "monthly_savings": round(monthly_savings, 2),
        "predictions": predictions,
        "goal": st.session_state.get("savings_goal", "Not set")
    }
    return json.dumps(result, indent=2)


def get_saving_tips(category: str) -> str:
    """Get saving tips for a specific spending category"""
    tips = {
        "Food": "Cook at home more, meal prep on weekends, use grocery lists, avoid food delivery apps.",
        "Transport": "Use public transit, carpool, cycle for short distances, compare fuel prices.",
        "Shopping": "Follow the 24-hour rule before purchases, unsubscribe from marketing emails, buy generic.",
        "Entertainment": "Share streaming subscriptions, look for free events, use student discounts.",
        "Subscriptions": "Audit all subscriptions monthly, cancel unused ones, negotiate rates.",
        "Utilities": "Turn off lights, use energy-efficient appliances, optimize AC/heating.",
        "General": "Track every expense, automate savings, set up a separate savings account."
    }
    return tips.get(category, tips["General"])


# ====================== REACT AGENT ======================
def run_finance_agent(user_query: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    expense_summary = analyze_spending() if st.session_state.expenses else "No expenses tracked yet"

    system_prompt = f"""You are a helpful Personal Finance Coach Agent for students and young professionals.
    
    User's Financial Profile:
    - Monthly Income: ${st.session_state.get('monthly_income', 0)} {st.session_state.get('currency', 'USD')}
    - Savings Goal: {st.session_state.get('savings_goal', 'Not set')}
    - Current Expense Summary: {expense_summary}
    
    Your capabilities:
    1. Analyze spending patterns from tracked expenses
    2. Create recommended budget breakdowns
    3. Predict future savings based on current habits
    4. Give practical saving tips by category
    
    Be encouraging, practical, and specific. Use numbers and percentages. Format output clearly."""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "analyze_spending",
            "description": "Analyze the user's spending patterns from tracked expenses",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }},
        {"type": "function", "function": {
            "name": "calculate_budget",
            "description": "Calculate a recommended monthly budget breakdown",
            "parameters": {"type": "object", "properties": {
                "income": {"type": "number", "description": "Monthly income"},
                "savings_target_pct": {"type": "number", "description": "Target savings percentage (e.g. 20)"}
            }, "required": ["income", "savings_target_pct"]}
        }},
        {"type": "function", "function": {
            "name": "predict_savings",
            "description": "Predict savings for the next N months based on current spending",
            "parameters": {"type": "object", "properties": {
                "months": {"type": "integer", "description": "Number of months to predict"}
            }, "required": ["months"]}
        }},
        {"type": "function", "function": {
            "name": "get_saving_tips",
            "description": "Get practical saving tips for a specific spending category",
            "parameters": {"type": "object", "properties": {
                "category": {"type": "string", "description": "Spending category: Food, Transport, Shopping, Entertainment, Subscriptions, Utilities, General"}
            }, "required": ["category"]}
        }}
    ]

    tool_functions = {
        "analyze_spending": lambda: analyze_spending(),
        "calculate_budget": calculate_budget,
        "predict_savings": predict_savings,
        "get_saving_tips": get_saving_tips
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    for step in range(10):  # Max 10 ReAct steps
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=1500
        )

        msg = response.choices[0].message
        messages.append({"role": "assistant", "content": msg.content or ""})

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments) or {}
            result = tool_functions[func_name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

    return messages[-1]["content"]

# ====================== MAIN UI ======================
st.subheader("Ask your Finance Coach")

# Show current expenses summary
if st.session_state.expenses:
    total = sum(e["amount"] for e in st.session_state.expenses)
    income = st.session_state.get("monthly_income", 0)
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Total Expenses", f"${total:,.2f}")
    col_b.metric("Monthly Income", f"${income:,.2f}")
    col_c.metric("Remaining", f"${income - total:,.2f}")
    col_d.metric("Transactions", len(st.session_state.expenses))

user_input = st.text_area(
    "What would you like help with?",
    placeholder="Analyze my spending and suggest where I can save\nOR\nCreate a budget with 20% savings target\nOR\nPredict my savings for the next 6 months",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("🚀 Get Financial Advice", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        else:
            with st.spinner("Analyzing your finances..."):
                response = run_finance_agent(user_input)

            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })

            st.subheader("📈 Finance Coach Response")
            st.markdown(response)

with col2:
    if st.button("Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# ====================== EXPENSE LOG ======================
if st.session_state.expenses:
    st.divider()
    st.subheader("📋 Expense Log")
    for i, e in enumerate(reversed(st.session_state.expenses[-20:]), 1):
        st.markdown(f"{i}. **{e['category']}** — ${e['amount']:.2f} • {e['description']} ({e['date']})")

# ====================== HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Previous Sessions")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq • No LangChain")
