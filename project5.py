import streamlit as st
from groq import Groq
import json
from duckduckgo_search import DDGS
from datetime import datetime

st.set_page_config(page_title="Job Application Agent", layout="wide")
st.title("💼 Job Application Agent")
st.markdown("**Search jobs • Analyze descriptions • Tailor resume • Write cover letters • Rank by match**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("📝 Your Profile")
    resume_text = st.text_area(
        "Paste your resume / key skills",
        value=st.session_state.get("resume_text", ""),
        height=200,
        placeholder="e.g. Python developer with 2 years experience in ML, Flask, FastAPI, SQL..."
    )
    if resume_text:
        st.session_state.resume_text = resume_text

    desired_role = st.text_input(
        "Desired Role",
        value=st.session_state.get("desired_role", ""),
        placeholder="e.g. Machine Learning Engineer"
    )
    if desired_role:
        st.session_state.desired_role = desired_role

    preferred_location = st.text_input(
        "Preferred Location",
        value=st.session_state.get("preferred_location", ""),
        placeholder="e.g. Remote, Bangalore, USA"
    )
    if preferred_location:
        st.session_state.preferred_location = preferred_location

# ====================== SESSION STATE ======================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # Memory of all applications
if "applications" not in st.session_state:
    st.session_state.applications = []  # Track applied jobs

# ====================== TOOLS ======================
def search_jobs(query: str) -> str:
    """Search the web for job openings"""
    try:
        results = list(DDGS().text(query + " job openings hiring", max_results=5))
        if not results:
            return "No job results found."
        output = []
        for i, r in enumerate(results, 1):
            output.append(f"**Job {i}:**\nTitle: {r['title']}\nDescription: {r['body']}\nLink: {r['href']}")
        return "\n\n".join(output)
    except Exception:
        return "Error searching for jobs. Please try again."


def tailor_resume(job_description: str, resume: str) -> str:
    """Tailor resume bullet points for a specific job description"""
    return json.dumps({
        "job_description_summary": job_description[:300],
        "original_resume_snippet": resume[:300],
        "instruction": "Based on the job description, rewrite and prioritize the most relevant resume bullet points. Highlight matching skills and quantify achievements where possible."
    })


def generate_cover_letter(job_title: str, company: str, key_requirements: str) -> str:
    """Generate a customized cover letter"""
    resume = st.session_state.get("resume_text", "No resume provided")
    return json.dumps({
        "job_title": job_title,
        "company": company,
        "key_requirements": key_requirements,
        "candidate_resume": resume[:500],
        "instruction": "Write a professional, personalized cover letter for this role. Keep it under 300 words. Reference specific skills from the resume that match the requirements."
    })


def rank_jobs(jobs_json: str) -> str:
    """Rank jobs by match score based on candidate's profile"""
    resume = st.session_state.get("resume_text", "")
    role = st.session_state.get("desired_role", "")
    return json.dumps({
        "jobs": jobs_json,
        "candidate_resume": resume[:400],
        "desired_role": role,
        "instruction": "Score each job from 0-100 based on how well it matches the candidate's skills and desired role. Return a ranked list with scores and reasoning."
    })


def save_application(job_title: str, company: str, status: str) -> str:
    """Log a job application to memory"""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "job_title": job_title,
        "company": company,
        "status": status
    }
    st.session_state.applications.append(entry)
    return f"✅ Application logged: {job_title} at {company} — Status: {status}"


# ====================== REACT AGENT ======================
def run_job_agent(user_query: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    resume = st.session_state.get("resume_text", "Not provided")
    role = st.session_state.get("desired_role", "Not specified")
    location = st.session_state.get("preferred_location", "Any")
    past_apps = json.dumps(st.session_state.applications[-5:]) if st.session_state.applications else "None yet"

    system_prompt = f"""You are a smart Job Application Agent that helps users find and apply to jobs.
    
    Candidate Profile:
    - Resume/Skills: {resume[:600]}
    - Desired Role: {role}
    - Preferred Location: {location}
    - Past Applications: {past_apps}
    
    Your capabilities:
    1. Search for relevant job openings on the web
    2. Analyze job descriptions to extract key requirements
    3. Tailor resume bullet points for specific jobs
    4. Write customized cover letters
    5. Rank jobs by match score
    6. Log applications for tracking
    
    Always provide structured, actionable output. Use JSON format for reports when appropriate."""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "search_jobs",
            "description": "Search the web for job openings matching a query",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Job search query"}}, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "tailor_resume",
            "description": "Tailor resume bullet points to match a specific job description",
            "parameters": {"type": "object", "properties": {
                "job_description": {"type": "string", "description": "The job description to tailor for"},
                "resume": {"type": "string", "description": "The candidate's resume text"}
            }, "required": ["job_description", "resume"]}
        }},
        {"type": "function", "function": {
            "name": "generate_cover_letter",
            "description": "Generate a customized cover letter for a specific job",
            "parameters": {"type": "object", "properties": {
                "job_title": {"type": "string"},
                "company": {"type": "string"},
                "key_requirements": {"type": "string"}
            }, "required": ["job_title", "company", "key_requirements"]}
        }},
        {"type": "function", "function": {
            "name": "rank_jobs",
            "description": "Rank a list of jobs by match score against candidate's profile",
            "parameters": {"type": "object", "properties": {
                "jobs_json": {"type": "string", "description": "JSON string of jobs to rank"}
            }, "required": ["jobs_json"]}
        }},
        {"type": "function", "function": {
            "name": "save_application",
            "description": "Log a job application to the tracking system",
            "parameters": {"type": "object", "properties": {
                "job_title": {"type": "string"},
                "company": {"type": "string"},
                "status": {"type": "string", "description": "Status: Applied, Interested, Shortlisted, Interview"}
            }, "required": ["job_title", "company", "status"]}
        }}
    ]

    tool_functions = {
        "search_jobs": search_jobs,
        "tailor_resume": tailor_resume,
        "generate_cover_letter": generate_cover_letter,
        "rank_jobs": rank_jobs,
        "save_application": save_application
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
            args = json.loads(tool_call.function.arguments)
            result = tool_functions[func_name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

    return messages[-1]["content"]

# ====================== MAIN UI ======================
st.subheader("What would you like help with?")

user_input = st.text_area(
    "Type your request:",
    placeholder="Find ML Engineer jobs in Bangalore and tailor my resume\nOR\nWrite a cover letter for Google Data Scientist role\nOR\nRank these jobs by how well they match my profile",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("🚀 Run Job Agent", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        elif not st.session_state.get("resume_text"):
            st.warning("Please paste your resume in the sidebar for best results")
        else:
            with st.spinner("Searching jobs & preparing your application materials..."):
                response = run_job_agent(user_input)

            # Save to history
            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })

            st.subheader("📋 Agent Response")
            st.markdown(response)

with col2:
    if st.button("Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.applications = []
        st.rerun()

# ====================== APPLICATION TRACKER ======================
if st.session_state.applications:
    st.divider()
    st.subheader("📊 Application Tracker")
    for app in reversed(st.session_state.applications):
        st.markdown(f"**{app['job_title']}** at {app['company']} — _{app['status']}_ ({app['timestamp']})")

# ====================== HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Previous Sessions")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq + DuckDuckGo • No LangChain")
