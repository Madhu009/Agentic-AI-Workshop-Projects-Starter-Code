import streamlit as st
from groq import Groq
import json
from duckduckgo_search import DDGS
from datetime import datetime

st.set_page_config(page_title="Lead Generation Agent", layout="wide")
st.title("🎯 Lead Generation Agent")
st.markdown("**Find prospects • Classify Hot/Warm/Cold • Personalized outreach • Structured reports • Memory**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("🏢 Your Company Info")
    company_name = st.text_input("Your Company Name",
                                  value=st.session_state.get("company_name", ""),
                                  placeholder="e.g. TechStartup AI")
    if company_name:
        st.session_state.company_name = company_name

    product_desc = st.text_area("Product / Service Description",
                                 value=st.session_state.get("product_desc", ""),
                                 placeholder="e.g. We sell AI-powered CRM tools for small businesses",
                                 height=100)
    if product_desc:
        st.session_state.product_desc = product_desc

    target_audience = st.text_input("Target Audience",
                                     value=st.session_state.get("target_audience", ""),
                                     placeholder="e.g. SaaS founders, marketing managers")
    if target_audience:
        st.session_state.target_audience = target_audience

# ====================== SESSION STATE ======================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "leads" not in st.session_state:
    st.session_state.leads = []  # Memory of all leads

# ====================== TOOLS ======================
def search_leads(query: str) -> str:
    """Search the web for potential leads, companies, or people"""
    try:
        results = list(DDGS().text(query, max_results=6))
        if not results:
            return "No results found."
        output = []
        for i, r in enumerate(results, 1):
            output.append(f"**Lead {i}:**\nName/Company: {r['title']}\nInfo: {r['body']}\nSource: {r['href']}")
        return "\n\n".join(output)
    except Exception:
        return "Error searching for leads. Please try again."


def classify_lead(lead_name: str, lead_info: str, relevance_reason: str) -> str:
    """Classify a lead as Hot, Warm, or Cold based on fit with product"""
    product = st.session_state.get("product_desc", "")
    audience = st.session_state.get("target_audience", "")
    return json.dumps({
        "lead_name": lead_name,
        "lead_info": lead_info,
        "relevance_reason": relevance_reason,
        "product": product[:300],
        "target_audience": audience,
        "instruction": "Classify this lead as Hot (high intent, perfect fit), Warm (some fit, needs nurturing), "
                       "or Cold (low fit, unlikely buyer). Provide a score 0-100 and reasoning."
    })


def generate_outreach(lead_name: str, lead_type: str, channel: str) -> str:
    """Generate personalized outreach email or LinkedIn message"""
    company = st.session_state.get("company_name", "Our Company")
    product = st.session_state.get("product_desc", "our product")
    return json.dumps({
        "lead_name": lead_name,
        "lead_type": lead_type,
        "channel": channel,
        "sender_company": company,
        "product": product[:300],
        "instruction": f"Write a personalized {channel} message to {lead_name} ({lead_type} lead) "
                       f"from {company}. Keep it concise, value-driven, and with a clear CTA. "
                       f"Tone: professional but friendly."
    })


def save_lead(lead_name: str, classification: str, score: int, source: str) -> str:
    """Save a lead to memory for future reference"""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "name": lead_name,
        "classification": classification,
        "score": score,
        "source": source
    }
    st.session_state.leads.append(entry)
    return f"✅ Lead saved: {lead_name} — {classification} (Score: {score})"


def get_lead_report() -> str:
    """Generate a structured JSON report of all saved leads"""
    if not st.session_state.leads:
        return json.dumps({"message": "No leads saved yet."})

    leads = st.session_state.leads
    hot = [l for l in leads if l["classification"] == "Hot"]
    warm = [l for l in leads if l["classification"] == "Warm"]
    cold = [l for l in leads if l["classification"] == "Cold"]

    report = {
        "total_leads": len(leads),
        "hot_leads": len(hot),
        "warm_leads": len(warm),
        "cold_leads": len(cold),
        "leads": leads,
        "recommendation": f"Prioritize {len(hot)} Hot leads for immediate outreach."
    }
    return json.dumps(report, indent=2)


# ====================== REACT AGENT ======================
def run_lead_agent(user_query: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    company = st.session_state.get("company_name", "Not specified")
    product = st.session_state.get("product_desc", "Not specified")
    audience = st.session_state.get("target_audience", "Not specified")
    saved_leads = json.dumps(st.session_state.leads[-5:]) if st.session_state.leads else "None yet"

    system_prompt = f"""You are an autonomous Lead Generation Agent for sales teams.
    
    Company: {company}
    Product/Service: {product}
    Target Audience: {audience}
    Saved Leads: {saved_leads}
    
    Your capabilities:
    1. Search the web for target companies or people
    2. Classify leads as Hot / Warm / Cold using analysis
    3. Generate personalized follow-up emails or LinkedIn messages
    4. Save leads to memory for future reference
    5. Return clean structured reports (JSON)
    
    Always be thorough — search, classify, generate outreach, and save leads in one flow."""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "search_leads",
            "description": "Search the web for potential leads, companies, or people",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "classify_lead",
            "description": "Classify a lead as Hot, Warm, or Cold based on fit",
            "parameters": {"type": "object", "properties": {
                "lead_name": {"type": "string"},
                "lead_info": {"type": "string"},
                "relevance_reason": {"type": "string"}
            }, "required": ["lead_name", "lead_info", "relevance_reason"]}
        }},
        {"type": "function", "function": {
            "name": "generate_outreach",
            "description": "Generate a personalized outreach email or LinkedIn message",
            "parameters": {"type": "object", "properties": {
                "lead_name": {"type": "string"},
                "lead_type": {"type": "string", "description": "Hot, Warm, or Cold"},
                "channel": {"type": "string", "description": "Email or LinkedIn"}
            }, "required": ["lead_name", "lead_type", "channel"]}
        }},
        {"type": "function", "function": {
            "name": "save_lead",
            "description": "Save a lead to memory for future reference",
            "parameters": {"type": "object", "properties": {
                "lead_name": {"type": "string"},
                "classification": {"type": "string", "description": "Hot, Warm, or Cold"},
                "score": {"type": "integer", "description": "Match score 0-100"},
                "source": {"type": "string", "description": "Where the lead was found"}
            }, "required": ["lead_name", "classification", "score", "source"]}
        }},
        {"type": "function", "function": {
            "name": "get_lead_report",
            "description": "Generate a structured report of all saved leads",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }}
    ]

    tool_functions = {
        "search_leads": search_leads,
        "classify_lead": classify_lead,
        "generate_outreach": generate_outreach,
        "save_lead": save_lead,
        "get_lead_report": lambda: get_lead_report()
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    for step in range(10):
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
st.subheader("Find & qualify your next customers")

user_input = st.text_area(
    "What leads are you looking for?",
    placeholder="Find AI startups in Bangalore that might need our CRM tool\nOR\nSearch for marketing managers at mid-size SaaS companies\nOR\nGenerate outreach emails for my saved Hot leads",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("🚀 Run Lead Agent", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        else:
            with st.spinner("Searching for leads & preparing outreach..."):
                response = run_lead_agent(user_input)

            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })

            st.subheader("📊 Lead Generation Report")
            st.markdown(response)

with col2:
    if st.button("Clear All", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.leads = []
        st.rerun()

# ====================== SAVED LEADS ======================
if st.session_state.leads:
    st.divider()
    st.subheader("📋 Saved Leads")
    hot = [l for l in st.session_state.leads if l["classification"] == "Hot"]
    warm = [l for l in st.session_state.leads if l["classification"] == "Warm"]
    cold = [l for l in st.session_state.leads if l["classification"] == "Cold"]

    col_h, col_w, col_c = st.columns(3)
    col_h.metric("🔥 Hot", len(hot))
    col_w.metric("🌤️ Warm", len(warm))
    col_c.metric("❄️ Cold", len(cold))

    for lead in reversed(st.session_state.leads):
        icon = "🔥" if lead["classification"] == "Hot" else "🌤️" if lead["classification"] == "Warm" else "❄️"
        st.markdown(f"{icon} **{lead['name']}** — {lead['classification']} (Score: {lead['score']}) • {lead['source'][:50]} ({lead['timestamp']})")

# ====================== HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Previous Sessions")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq + DuckDuckGo • No LangChain")
