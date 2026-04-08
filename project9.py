import streamlit as st
from groq import Groq
import json
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Customer Support Agent", layout="wide")
st.title("🎧 Customer Support Agent (with RAG)")
st.markdown("**FAQ knowledge base • Accurate answers • Human escalation • Ticket logging • Conversation history**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("📄 Upload Company FAQ / Knowledge Base")
    uploaded_files = st.file_uploader("Upload FAQ or documentation PDFs",
                                      accept_multiple_files=True,
                                      type=["pdf"])

    if uploaded_files:
        st.success(f"{len(uploaded_files)} PDF(s) uploaded")

    st.divider()
    st.header("🏢 Company Settings")
    company_name = st.text_input("Company Name",
                                  value=st.session_state.get("company_name", ""),
                                  placeholder="e.g. TechCorp Inc.")
    if company_name:
        st.session_state.company_name = company_name

    support_email = st.text_input("Escalation Email",
                                   value=st.session_state.get("support_email", ""),
                                   placeholder="e.g. support@techcorp.com")
    if support_email:
        st.session_state.support_email = support_email

# ====================== SESSION STATE ======================
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None
    st.session_state.chunks = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # Conversation history
if "tickets" not in st.session_state:
    st.session_state.tickets = []  # Support ticket log
if "company_name" not in st.session_state:
    st.session_state.company_name = "Our Company"
if "support_email" not in st.session_state:
    st.session_state.support_email = "support@company.com"

# ====================== EMBEDDING MODEL ======================
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

embedding_model = load_embedding_model()

# ====================== PROCESS PDFs (RAG) ======================
def process_pdfs(files):
    chunks = []
    for file in files:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        # Chunking
        chunk_size = 600
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)

    if chunks:
        embeddings = embedding_model.encode(chunks, show_progress_bar=False)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings.astype(np.float32))

        st.session_state.vectorstore = index
        st.session_state.chunks = chunks
        st.success(f"✅ {len(chunks)} chunks loaded into knowledge base")
    return chunks

if uploaded_files and st.session_state.vectorstore is None:
    with st.spinner("Building knowledge base from documents..."):
        process_pdfs(uploaded_files)

# ====================== TOOLS ======================
def search_knowledge_base(query: str) -> str:
    """RAG - Search the company FAQ / knowledge base documents"""
    if st.session_state.vectorstore is None:
        return "No knowledge base loaded. Please upload FAQ/documentation PDFs."

    query_embedding = embedding_model.encode([query])[0].astype(np.float32).reshape(1, -1)
    distances, indices = st.session_state.vectorstore.search(query_embedding, k=4)

    relevant = []
    for idx, (i, d) in enumerate(zip(indices[0], distances[0])):
        relevant.append(f"[Chunk {idx + 1} | Relevance: {1 / (1 + d):.2f}]\n{st.session_state.chunks[i]}")

    return "\n\n---\n\n".join(relevant)


def escalate_to_human(reason: str, customer_query: str) -> str:
    """Escalate to human support when the agent cannot answer"""
    ticket_id = f"TKT-{len(st.session_state.tickets) + 1001}"
    ticket = {
        "ticket_id": ticket_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "customer_query": customer_query,
        "reason": reason,
        "status": "Escalated to Human",
        "escalation_email": st.session_state.get("support_email", "support@company.com")
    }
    st.session_state.tickets.append(ticket)

    return json.dumps({
        "status": "escalated",
        "ticket_id": ticket_id,
        "message": f"Your query has been escalated to our human support team. "
                   f"Ticket ID: {ticket_id}. A support agent will contact you at "
                   f"{st.session_state.get('support_email', 'support@company.com')}.",
        "reason": reason
    }, indent=2)


def log_ticket(customer_query: str, resolution: str, status: str) -> str:
    """Log a support ticket with details"""
    ticket_id = f"TKT-{len(st.session_state.tickets) + 1001}"
    ticket = {
        "ticket_id": ticket_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "customer_query": customer_query[:200],
        "resolution": resolution[:300],
        "status": status
    }
    st.session_state.tickets.append(ticket)
    return f"✅ Ticket {ticket_id} logged — Status: {status}"


# ====================== REACT AGENT ======================
def run_support_agent(user_query: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    company = st.session_state.get("company_name", "Our Company")
    has_kb = st.session_state.vectorstore is not None
    recent_history = st.session_state.chat_history[-5:] if st.session_state.chat_history else []
    history_str = "\n".join([f"Customer: {h['query']}\nAgent: {h['response'][:200]}" for h in recent_history]) or "No previous conversation"

    system_prompt = f"""You are a professional Customer Support Agent for {company}.
    
    Knowledge Base Status: {'Loaded and ready' if has_kb else 'Not loaded — ask customer to wait or escalate'}
    
    Recent Conversation History:
    {history_str}
    
    Your rules:
    1. ALWAYS search the knowledge base first to find accurate answers
    2. Answer ONLY based on information from the knowledge base — do NOT make up answers
    3. If the knowledge base does not contain the answer, clearly say so and ESCALATE to human support
    4. Be polite, professional, and empathetic
    5. Log every resolved or escalated ticket
    6. Maintain conversation context from previous messages
    
    Escalation triggers (MUST escalate):
    - Answer not found in knowledge base
    - Customer is angry or frustrated
    - Technical issues requiring human intervention
    - Billing disputes or refund requests
    - Customer explicitly asks for a human"""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "search_knowledge_base",
            "description": "Search the company FAQ and documentation to find answers to customer queries",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "escalate_to_human",
            "description": "Escalate the query to human support when the agent cannot answer accurately",
            "parameters": {"type": "object", "properties": {
                "reason": {"type": "string", "description": "Why this is being escalated"},
                "customer_query": {"type": "string", "description": "The customer's original query"}
            }, "required": ["reason", "customer_query"]}
        }},
        {"type": "function", "function": {
            "name": "log_ticket",
            "description": "Log a support ticket after resolving or escalating a query",
            "parameters": {"type": "object", "properties": {
                "customer_query": {"type": "string"},
                "resolution": {"type": "string", "description": "How the query was resolved"},
                "status": {"type": "string", "description": "Resolved, Escalated, or Pending"}
            }, "required": ["customer_query", "resolution", "status"]}
        }}
    ]

    tool_functions = {
        "search_knowledge_base": search_knowledge_base,
        "escalate_to_human": escalate_to_human,
        "log_ticket": log_ticket
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    for step in range(10):  # Max 10 ReAct steps
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=1200
        )

        msg = response.choices[0].message
        messages.append({"role": "assistant", "content": msg.content or ""})

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = tool_functions[func_name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

    return messages[-1]["content"]

# ====================== MAIN UI ======================
st.subheader("How can we help you today?")

user_input = st.text_area(
    "Type your question:",
    placeholder="How do I reset my password?\nOR\nI want a refund for my last order\nOR\nWhat are your business hours?",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("💬 Send to Support Agent", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        else:
            with st.spinner("Looking up your answer..."):
                response = run_support_agent(user_input)

            # Save to conversation history
            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })

            st.subheader("💬 Support Response")
            st.markdown(response)

with col2:
    if st.button("Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.tickets = []
        st.rerun()

# ====================== TICKET LOG ======================
if st.session_state.tickets:
    st.divider()
    st.subheader("🎫 Support Tickets")
    for ticket in reversed(st.session_state.tickets):
        status_icon = "✅" if ticket["status"] == "Resolved" else "⚠️" if ticket["status"] == "Escalated to Human" else "🔄"
        st.markdown(
            f"{status_icon} **{ticket['ticket_id']}** — _{ticket['customer_query'][:60]}..._ "
            f"→ {ticket['status']} ({ticket['timestamp']})"
        )

# ====================== CONVERSATION HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Conversation History")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq + FAISS RAG • No LangChain")
