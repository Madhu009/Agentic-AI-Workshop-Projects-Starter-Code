import streamlit as st
from groq import Groq
import json
from duckduckgo_search import DDGS
from datetime import datetime

st.set_page_config(page_title="Multi-Agent Team", layout="wide")
st.title("🤖 Multi-Agent Team (Advanced)")
st.markdown("**Supervisor + Researcher + Writer + Critic • Collaborate on complex tasks • Business plans & more**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("⚙️ Team Settings")
    max_rounds = st.slider("Max Collaboration Rounds", 1, 5, 3)
    show_agent_logs = st.checkbox("Show Agent-by-Agent Logs", value=True)

# ====================== SESSION STATE ======================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_logs" not in st.session_state:
    st.session_state.agent_logs = []

# ====================== TOOLS (shared) ======================
def search_web(query: str) -> str:
    """Search the web for latest information"""
    try:
        results = list(DDGS().text(query, max_results=5))
        if not results:
            return "No results found."
        return "\n\n".join([f"**{r['title']}**\n{r['body']}" for r in results])
    except Exception:
        return "Error searching. Please try again."

# ====================== INDIVIDUAL AGENTS ======================
def run_single_agent(client, agent_name: str, agent_role: str, task: str, context: str = "") -> str:
    """Run a single specialized agent and return its output"""
    
    tool_schemas = [
        {"type": "function", "function": {
            "name": "search_web",
            "description": "Search the internet for latest information, data, and facts",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }}
    ]

    messages = [
        {"role": "system", "content": f"You are the {agent_name}. {agent_role}\n\nPrevious context from team:\n{context or 'None yet — you are starting fresh.'}"},
        {"role": "user", "content": task}
    ]

    for step in range(5):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tool_schemas if agent_name == "Researcher" else None,
            tool_choice="auto" if agent_name == "Researcher" else None,
            temperature=0.4,
            max_tokens=1500
        )

        msg = response.choices[0].message
        messages.append({"role": "assistant", "content": msg.content or ""})

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            args = json.loads(tool_call.function.arguments) or {}
            result = search_web(**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

    return messages[-1]["content"]


# ====================== SUPERVISOR ORCHESTRATOR ======================
def run_multi_agent_team(user_task: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)
    logs = []

    # ---- STEP 1: Supervisor plans the work ----
    supervisor_plan_prompt = f"""You are the Supervisor Agent. You manage a team of 3 agents:
    1. **Researcher** — Searches the web, gathers data, finds facts and statistics
    2. **Writer** — Takes research and creates professional, well-structured content
    3. **Critic** — Reviews the Writer's output, finds weaknesses, suggests improvements

    The user wants: {user_task}

    Create a brief plan: what should each agent do? Output a JSON with keys: researcher_task, writer_task, critic_task."""

    supervisor_plan = run_single_agent(client, "Supervisor", 
        "You plan and delegate work to your team. Be concise and strategic.", 
        supervisor_plan_prompt)
    
    logs.append({"agent": "🧠 Supervisor", "output": supervisor_plan})
    
    if show_agent_logs:
        st.info("**🧠 Supervisor** — Plan created")
        with st.expander("Supervisor's Plan"):
            st.markdown(supervisor_plan)

    # Try to parse tasks from supervisor
    try:
        # Find JSON in the response
        json_start = supervisor_plan.find("{")
        json_end = supervisor_plan.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            plan = json.loads(supervisor_plan[json_start:json_end])
            researcher_task = plan.get("researcher_task", user_task)
            writer_task = plan.get("writer_task", f"Write about: {user_task}")
            critic_task = plan.get("critic_task", "Review and improve the draft")
        else:
            researcher_task = f"Research: {user_task}"
            writer_task = f"Write a comprehensive output for: {user_task}"
            critic_task = "Review and critique the draft, suggest improvements"
    except (json.JSONDecodeError, KeyError):
        researcher_task = f"Research: {user_task}"
        writer_task = f"Write a comprehensive output for: {user_task}"
        critic_task = "Review and critique the draft, suggest improvements"

    # ---- Iterative collaboration rounds ----
    research_output = ""
    writer_output = ""
    critic_output = ""

    for round_num in range(1, max_rounds + 1):
        if show_agent_logs:
            st.subheader(f"Round {round_num} of {max_rounds}")

        # ---- STEP 2: Researcher gathers data ----
        research_context = f"Previous research: {research_output[:500]}\nCritic feedback: {critic_output[:500]}" if round_num > 1 else ""
        research_output = run_single_agent(client, "Researcher",
            "You are a thorough researcher. Search the web, gather facts, data, stats, and trends. "
            "Provide well-organized research notes with sources.",
            researcher_task + (f"\n\nAddress this feedback: {critic_output}" if critic_output else ""),
            research_context)
        
        logs.append({"agent": f"🔍 Researcher (Round {round_num})", "output": research_output})
        if show_agent_logs:
            st.success(f"**🔍 Researcher** — Research complete (Round {round_num})")
            with st.expander(f"Research Output (Round {round_num})"):
                st.markdown(research_output)

        # ---- STEP 3: Writer creates content ----
        writer_context = f"Research from Researcher:\n{research_output}\n\nPrevious draft: {writer_output[:500]}\nCritic feedback: {critic_output[:500]}"
        writer_output = run_single_agent(client, "Writer",
            "You are a professional writer. Use the research provided to create polished, "
            "well-structured, comprehensive content. Use headings, bullet points, and clear formatting.",
            writer_task + (f"\n\nAddress this feedback: {critic_output}" if critic_output else ""),
            writer_context)
        
        logs.append({"agent": f"✍️ Writer (Round {round_num})", "output": writer_output})
        if show_agent_logs:
            st.success(f"**✍️ Writer** — Draft complete (Round {round_num})")
            with st.expander(f"Writer's Draft (Round {round_num})"):
                st.markdown(writer_output)

        # ---- STEP 4: Critic reviews ----
        if round_num < max_rounds:  # Skip critic on last round
            critic_context = f"Writer's draft to review:\n{writer_output}"
            critic_output = run_single_agent(client, "Critic",
                "You are a sharp critic. Review the draft for accuracy, completeness, structure, and clarity. "
                "Point out weaknesses and suggest specific improvements. Be constructive.",
                critic_task + f"\n\nReview this draft:\n{writer_output[:2000]}",
                critic_context)
            
            logs.append({"agent": f"🔎 Critic (Round {round_num})", "output": critic_output})
            if show_agent_logs:
                st.warning(f"**🔎 Critic** — Review complete (Round {round_num})")
                with st.expander(f"Critic's Feedback (Round {round_num})"):
                    st.markdown(critic_output)

    # ---- STEP 5: Supervisor delivers final output ----
    final_prompt = f"""The team has completed their work. Here is the final draft from the Writer:

{writer_output}

Polish this into the final deliverable. Add any missing sections. 
Format it professionally with clear headings and structure.
Add a brief executive summary at the top."""

    final_output = run_single_agent(client, "Supervisor",
        "You are the Supervisor. Compile and polish the team's work into a final professional deliverable.",
        final_prompt,
        f"Original task: {user_task}")
    
    logs.append({"agent": "🧠 Supervisor (Final)", "output": final_output})

    # Save all logs
    st.session_state.agent_logs = logs

    return final_output


# ====================== MAIN UI ======================
st.subheader("Give your AI team a complex task")

user_input = st.text_area(
    "What should the team work on?",
    placeholder="Create a full business plan for an AI tutoring startup\nOR\nWrite a comprehensive market analysis report on electric vehicles in India\nOR\nDevelop a content marketing strategy for a new SaaS product",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("🚀 Deploy Agent Team", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        else:
            with st.spinner("Multi-agent team is collaborating..."):
                response = run_multi_agent_team(user_input)

            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })

            st.divider()
            st.subheader("📄 Final Deliverable")
            st.markdown(response)

with col2:
    if st.button("Clear All", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.agent_logs = []
        st.rerun()

# ====================== HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Previous Sessions")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq • Multi-Agent Supervisor Pattern • No LangChain")
