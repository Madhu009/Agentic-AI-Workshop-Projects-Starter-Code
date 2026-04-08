import streamlit as st
from groq import Groq
import json
from duckduckgo_search import DDGS
import os
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Research Intelligence Agent", layout="wide")
st.title("🔍 Research Intelligence Agent")
st.markdown("**Gathers latest web data + RAG on your PDFs • Delivers professional insights report**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("📄 Upload Documents (RAG)")
    uploaded_files = st.file_uploader("Upload PDFs for your research", 
                                    accept_multiple_files=True, 
                                    type=["pdf"])
    
    if uploaded_files:
        st.success(f"{len(uploaded_files)} PDF(s) uploaded")

# ====================== SESSION STATE ======================
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None
    st.session_state.chunks = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # For remembering previous research sessions

# ====================== BUILD RAG (FAISS) ======================
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

embedding_model = load_embedding_model()

def process_pdfs(files):
    chunks = []
    for file in files:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        # Simple chunking
        chunk_size = 800
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i+chunk_size])
    
    if chunks:
        embeddings = embedding_model.encode(chunks, show_progress_bar=False)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings.astype(np.float32))
        
        st.session_state.vectorstore = index
        st.session_state.chunks = chunks
        st.success(f"✅ Processed {len(chunks)} document chunks into knowledge base")
    return chunks

# Process uploaded PDFs
if uploaded_files and st.session_state.vectorstore is None:
    with st.spinner("Processing PDFs for RAG..."):
        process_pdfs(uploaded_files)

# ====================== TOOLS ======================
def search_web(query: str) -> str:
    """Search latest information from the web"""
    try:
        results = list(DDGS().text(query, max_results=4))
        return "\n\n".join([f"Source: {r['title']}\n{r['body']}" for r in results])
    except:
        return "No web results found."

def retrieve_from_documents(query: str) -> str:
    """Retrieve relevant information from uploaded PDFs (RAG)"""
    if st.session_state.vectorstore is None:
        return "No documents uploaded yet."
    
    query_embedding = embedding_model.encode([query])[0].astype(np.float32).reshape(1, -1)
    distances, indices = st.session_state.vectorstore.search(query_embedding, k=3)
    
    relevant_chunks = [st.session_state.chunks[i] for i in indices[0]]
    return "\n\n---\n\n".join(relevant_chunks)

# ====================== REACT AGENT ======================
def run_research_agent(topic: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    system_prompt = """You are a professional Research Intelligence Agent.
    Your job is to:
    1. Gather latest information using web search
    2. Use internal documents (RAG) when available
    3. Analyze trends and summarize key points
    4. Generate a clean, professional insights report with sources"""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "search_web",
            "description": "Search the latest information on the internet",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "retrieve_from_documents",
            "description": "Retrieve relevant information from the uploaded research documents",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }}
    ]

    tool_functions = {
        "search_web": search_web,
        "retrieve_from_documents": retrieve_from_documents
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Research topic: {topic}\nProvide a professional insights report with sources."}
    ]

    for step in range(10):  # Max 10 steps
        response = client.chat.completions.create(
            model="llama3-70b-8192",
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
            args = json.loads(tool_call.function.arguments)
            result = tool_functions[func_name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

    return messages[-1]["content"]

# ====================== MAIN UI ======================
st.subheader("What would you like to research?")

research_topic = st.text_input(
    "Research Topic",
    placeholder="Latest advancements in Agentic AI in 2026",
    value="Latest advancements in Agentic AI in 2026"
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("🚀 Run Research Intelligence Agent", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter your Groq API key")
        else:
            with st.spinner("Researching on web + analyzing your documents..."):
                final_report = run_research_agent(research_topic)
            
            # Save to history
            st.session_state.chat_history.append({
                "timestamp": datetime.now().strftime("%H:%M"),
                "topic": research_topic,
                "report": final_report
            })
            
            st.subheader("📊 Professional Insights Report")
            st.markdown(final_report)

with col2:
    if st.button("Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# ====================== PREVIOUS RESEARCH SESSIONS ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📚 Previous Research Sessions")
    for i, entry in enumerate(reversed(st.session_state.chat_history)):
        with st.expander(f"[{entry['timestamp']}] {entry['topic'][:60]}..."):
            st.write(entry["report"])

st.caption("Built for Agentic AI Workshop • Pure Groq + FAISS RAG • No LangChain")