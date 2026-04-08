import streamlit as st
from groq import Groq
import json
from duckduckgo_search import DDGS
from datetime import datetime

st.set_page_config(page_title="Automation & Notification Agent", layout="wide")
st.title("⚡ Automation & Notification Agent")
st.markdown("**Monitor triggers • Check conditions • Send mock notifications • Action logs • Scheduled tasks**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("🔔 Notification Settings")
    notify_channels = st.multiselect(
        "Notification Channels",
        ["Email", "WhatsApp", "Slack", "SMS"],
        default=["Email", "Slack"]
    )
    notify_email = st.text_input("Notification Email", placeholder="you@example.com",
                                  value=st.session_state.get("notify_email", ""))
    if notify_email:
        st.session_state.notify_email = notify_email

    st.divider()
    st.header("📋 Quick Trigger Setup")
    trigger_type = st.selectbox("Trigger Type", 
                                 ["Stock Price Change", "News Alert", "Weather Alert", 
                                  "New Email Received", "Scheduled Reminder", "Custom Condition"])
    trigger_value = st.text_input("Trigger Condition",
                                   placeholder="e.g. AAPL drops below $150")

# ====================== SESSION STATE ======================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "action_log" not in st.session_state:
    st.session_state.action_log = []  # Log every action with timestamp
if "active_triggers" not in st.session_state:
    st.session_state.active_triggers = []

# ====================== TOOLS ======================
def check_condition(query: str) -> str:
    """Check a condition by searching the web for latest data"""
    try:
        results = list(DDGS().text(query + " latest today 2026", max_results=4))
        if not results:
            return json.dumps({"status": "unknown", "message": "Could not find relevant data."})
        info = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        return json.dumps({
            "status": "checked",
            "query": query,
            "findings": info,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, indent=2)
    except Exception:
        return json.dumps({"status": "error", "message": "Failed to check condition."})


def send_notification(channel: str, recipient: str, subject: str, message: str) -> str:
    """Send a mock notification via Email/WhatsApp/Slack/SMS"""
    notification = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "channel": channel,
        "recipient": recipient,
        "subject": subject,
        "message": message[:500],
        "status": "Sent (Mock)"
    }
    st.session_state.action_log.append({
        "time": notification["timestamp"],
        "action": f"Notification sent via {channel}",
        "details": f"To: {recipient} — {subject}"
    })
    return json.dumps(notification, indent=2)


def log_action(action: str, details: str) -> str:
    """Log an action with timestamp"""
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "details": details
    }
    st.session_state.action_log.append(entry)
    return f"✅ Action logged: {action} at {entry['time']}"


def create_trigger(trigger_name: str, condition: str, action_on_trigger: str, channel: str) -> str:
    """Create a new automation trigger (mock)"""
    trigger = {
        "id": f"TRG-{len(st.session_state.active_triggers) + 1}",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "name": trigger_name,
        "condition": condition,
        "action": action_on_trigger,
        "channel": channel,
        "status": "Active"
    }
    st.session_state.active_triggers.append(trigger)
    st.session_state.action_log.append({
        "time": trigger["created_at"],
        "action": f"Trigger created: {trigger_name}",
        "details": f"Condition: {condition} → Action: {action_on_trigger} via {channel}"
    })
    return json.dumps(trigger, indent=2)


def get_action_log() -> str:
    """Get the full action log with timestamps"""
    if not st.session_state.action_log:
        return json.dumps({"message": "No actions logged yet."})
    return json.dumps(st.session_state.action_log[-20:], indent=2)


# ====================== REACT AGENT ======================
def run_automation_agent(user_query: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    channels = ", ".join(notify_channels)
    active = json.dumps(st.session_state.active_triggers[-3:]) if st.session_state.active_triggers else "None"
    recent_log = json.dumps(st.session_state.action_log[-3:]) if st.session_state.action_log else "None"

    system_prompt = f"""You are an Automation & Notification Agent that monitors triggers and sends notifications.
    
    Settings:
    - Notification Channels: {channels}
    - Email: {st.session_state.get('notify_email', 'Not set')}
    - Active Triggers: {active}
    - Recent Actions: {recent_log}
    
    Your capabilities:
    1. Check conditions by searching the web for latest data (stock prices, news, weather, etc.)
    2. Send mock notifications via Email, WhatsApp, Slack, or SMS
    3. Log every action with timestamp
    4. Create automation triggers (event-driven or scheduled)
    5. View the full action log
    
    Workflow: Check condition → If triggered → Send notification → Log action.
    Always be thorough and log every step."""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "check_condition",
            "description": "Check a condition by searching web for latest data (stocks, news, weather, etc.)",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "send_notification",
            "description": "Send a mock notification via Email, WhatsApp, Slack, or SMS",
            "parameters": {"type": "object", "properties": {
                "channel": {"type": "string", "description": "Email, WhatsApp, Slack, or SMS"},
                "recipient": {"type": "string"},
                "subject": {"type": "string"},
                "message": {"type": "string"}
            }, "required": ["channel", "recipient", "subject", "message"]}
        }},
        {"type": "function", "function": {
            "name": "log_action",
            "description": "Log an action with timestamp for audit trail",
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string"},
                "details": {"type": "string"}
            }, "required": ["action", "details"]}
        }},
        {"type": "function", "function": {
            "name": "create_trigger",
            "description": "Create a new automation trigger that monitors a condition",
            "parameters": {"type": "object", "properties": {
                "trigger_name": {"type": "string"},
                "condition": {"type": "string"},
                "action_on_trigger": {"type": "string", "description": "What to do when triggered"},
                "channel": {"type": "string", "description": "Notification channel"}
            }, "required": ["trigger_name", "condition", "action_on_trigger", "channel"]}
        }},
        {"type": "function", "function": {
            "name": "get_action_log",
            "description": "Get the full action log with timestamps",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }}
    ]

    tool_functions = {
        "check_condition": check_condition,
        "send_notification": send_notification,
        "log_action": log_action,
        "create_trigger": create_trigger,
        "get_action_log": lambda: get_action_log()
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
st.subheader("Set up automations & notifications")

user_input = st.text_area(
    "What would you like to automate?",
    placeholder="Check if Tesla stock dropped today and notify me on Slack\nOR\nCreate a trigger: alert me via email when AI news breaks\nOR\nShow my action log",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("⚡ Run Automation Agent", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        else:
            with st.spinner("Checking conditions & running automations..."):
                response = run_automation_agent(user_input)

            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })

            st.subheader("📬 Agent Response")
            st.markdown(response)

with col2:
    if st.button("Clear All", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.action_log = []
        st.session_state.active_triggers = []
        st.rerun()

# ====================== ACTIVE TRIGGERS ======================
if st.session_state.active_triggers:
    st.divider()
    st.subheader("🔔 Active Triggers")
    for t in reversed(st.session_state.active_triggers):
        st.markdown(
            f"**{t['id']}** — {t['name']} | Condition: _{t['condition']}_ | "
            f"Action: {t['action']} via {t['channel']} ({t['status']})"
        )

# ====================== ACTION LOG ======================
if st.session_state.action_log:
    st.divider()
    st.subheader("📜 Action Log")
    for entry in reversed(st.session_state.action_log[-15:]):
        st.markdown(f"`{entry['time']}` — **{entry['action']}** • {entry['details']}")

# ====================== HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Previous Sessions")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq + DuckDuckGo • No LangChain")
