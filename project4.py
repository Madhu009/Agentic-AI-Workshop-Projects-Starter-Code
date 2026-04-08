import streamlit as st
from groq import Groq
import json
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Personal Academic Assistant", layout="wide")
st.title("📚 Personal Academic Assistant")
st.markdown("**Your AI Tutor • RAG on your notes • Study plans • Quizzes • Remembers your weak areas**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("📄 Upload Lecture Notes / PDFs")
    uploaded_files = st.file_uploader("Upload your lecture notes or PDFs", 
                                    accept_multiple_files=True, 
                                    type=["pdf"])
    
    st.divider()
    st.header("📌 My Subjects & Weak Areas")
    subjects = st.text_input("Subjects you are studying (comma separated)", 
                           value=st.session_state.get("subjects", "Agentic AI, Machine Learning, Data Science"))
    weak_areas = st.text_input("Your weak areas (comma separated)", 
                             value=st.session_state.get("weak_areas", "Multi-agent systems, RAG implementation"))

    if st.button("Save Profile"):
        st.session_state.subjects = subjects
        st.session_state.weak_areas = weak_areas
        st.success("Profile saved!")

# ====================== SESSION STATE ======================
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None
    st.session_state.chunks = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # Remembers previous sessions
if "subjects" not in st.session_state:
    st.session_state.subjects = "Agentic AI, Machine Learning"
if "weak_areas" not in st.session_state:
    st.session_state.weak_areas = "Multi-agent systems"

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
        chunk_size = 700
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i+chunk_size])
    
    if chunks:
        embeddings = embedding_model.encode(chunks, show_progress_bar=False)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings.astype(np.float32))
        
        st.session_state.vectorstore = index
        st.session_state.chunks = chunks
        st.success(f"✅ {len(chunks)} chunks from notes added to knowledge base")
    return chunks

if uploaded_files and st.session_state.vectorstore is None:
    with st.spinner("Processing your lecture notes..."):
        process_pdfs(uploaded_files)

# ====================== TOOLS ======================
def retrieve_from_notes(query: str) -> str:
    """RAG - Search your uploaded lecture notes"""
    if st.session_state.vectorstore is None:
        return "No lecture notes uploaded yet. Please upload PDFs first."
    
    query_embedding = embedding_model.encode([query])[0].astype(np.float32).reshape(1, -1)
    distances, indices = st.session_state.vectorstore.search(query_embedding, k=4)
    
    relevant = [st.session_state.chunks[i] for i in indices[0]]
    return "\n\n---\n\n".join(relevant)

def create_study_plan(subject: str, days: int) -> str:
    """Create a personalized study plan"""
    weak = st.session_state.get("weak_areas", "")
    return f"""📅 {days}-Day Study Plan for **{subject}**

Focus Areas: {weak}

Day 1-2: Basics & Fundamentals
Day 3-4: Core Concepts & Examples
Day 5-6: Practice & Weak Areas
Day {days}: Revision & Mock Test

Tip: Spend more time on {weak}"""

def generate_quiz(topic: str) -> str:
    """Generate quiz questions with answers"""
    return f"""🧠 Quiz on **{topic}**

Q1: What is the main difference between Chain-of-Thought and ReAct?
Q2: How does RAG help reduce hallucinations?
Q3: Explain the Agent loop (Reason → Act → Observe).

(Answers will be revealed after you attempt)"""

# ====================== REACT AGENT ======================
def run_academic_agent(user_query: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    system_prompt = f"""You are a friendly and helpful Personal Academic Assistant for college students.
    You know the student's subjects: {st.session_state.subjects}
    Weak areas: {st.session_state.weak_areas}
    
    Use tools to:
    - Answer from uploaded lecture notes (RAG)
    - Create study plans
    - Generate quizzes
    Always be encouraging and clear."""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "retrieve_from_notes",
            "description": "Search the student's uploaded lecture notes",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "create_study_plan",
            "description": "Create a personalized study plan",
            "parameters": {"type": "object", "properties": {"subject": {"type": "string"}, "days": {"type": "integer"}}, "required": ["subject", "days"]}
        }},
        {"type": "function", "function": {
            "name": "generate_quiz",
            "description": "Generate quiz questions on a topic",
            "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}
        }}
    ]

    tool_functions = {
        "retrieve_from_notes": retrieve_from_notes,
        "create_study_plan": create_study_plan,
        "generate_quiz": generate_quiz
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    for step in range(10):
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
            temperature=0.4,
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
st.subheader("Ask your AI Tutor anything")

user_input = st.text_area(
    "Type your question, request, or command:",
    placeholder="Create a 7-day study plan for Agentic AI\nOR\nExplain RAG from my notes\nOR\nGenerate quiz on Multi-Agent Systems",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("🚀 Ask AI Tutor", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        else:
            with st.spinner("Thinking like your personal tutor..."):
                response = run_academic_agent(user_input)
            
            # Save to history
            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })
            
            st.subheader("📝 Tutor Response")
            st.markdown(response)

with col2:
    if st.button("Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# ====================== HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Previous Tutoring Sessions")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq + FAISS RAG • Remembers your profile")