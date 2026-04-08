import streamlit as st
from groq import Groq
import json
from duckduckgo_search import DDGS
from datetime import datetime

st.set_page_config(page_title="Content Creation Agent", layout="wide")
st.title("📱 Content Creation Agent")
st.markdown("**Research trends • Generate LinkedIn, Twitter/X, Instagram posts • 3 tones • Mock scheduling**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("🎯 Content Settings")
    platforms = st.multiselect(
        "Target Platforms",
        ["LinkedIn", "Twitter/X", "Instagram"],
        default=["LinkedIn", "Twitter/X", "Instagram"]
    )
    tones = st.multiselect(
        "Content Tones",
        ["Professional", "Casual", "Viral"],
        default=["Professional", "Casual", "Viral"]
    )
    brand_voice = st.text_area(
        "Brand Voice / Style Notes",
        value=st.session_state.get("brand_voice", ""),
        placeholder="e.g. Friendly, tech-savvy, uses emojis sparingly, data-driven",
        height=80
    )
    if brand_voice:
        st.session_state.brand_voice = brand_voice

    st.divider()
    st.header("📅 Mock Schedule")
    schedule_date = st.date_input("Schedule Post Date", value=datetime.now().date())
    schedule_time = st.time_input("Schedule Post Time")

# ====================== SESSION STATE ======================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "scheduled_posts" not in st.session_state:
    st.session_state.scheduled_posts = []

# ====================== TOOLS ======================
def search_trends(query: str) -> str:
    """Search latest trends on the web for content inspiration"""
    try:
        results = list(DDGS().text(query + " latest trends 2026", max_results=5))
        if not results:
            return "No trending results found."
        output = []
        for r in results:
            output.append(f"**{r['title']}**\n{r['body']}")
        return "\n\n".join(output)
    except Exception:
        return "Error searching trends. Please try again."


def generate_content(topic: str, platform: str, tone: str) -> str:
    """Generate social media content for a specific platform and tone"""
    char_limits = {
        "LinkedIn": 3000,
        "Twitter/X": 280,
        "Instagram": 2200
    }
    limit = char_limits.get(platform, 1000)
    brand = st.session_state.get("brand_voice", "professional and engaging")

    return json.dumps({
        "topic": topic,
        "platform": platform,
        "tone": tone,
        "char_limit": limit,
        "brand_voice": brand,
        "instruction": f"Create a {tone.lower()} {platform} post about '{topic}'. "
                       f"Include relevant hashtags, call-to-action, and emojis where appropriate. "
                       f"Stay within {limit} characters for the main post. "
                       f"Brand voice: {brand}"
    })


def generate_multi_format(topic: str, platforms_str: str, tones_str: str) -> str:
    """Generate content in multiple formats and tones at once"""
    platform_list = [p.strip() for p in platforms_str.split(",")]
    tone_list = [t.strip() for t in tones_str.split(",")]

    output = {"topic": topic, "versions": []}
    for platform in platform_list:
        for tone in tone_list:
            output["versions"].append({
                "platform": platform,
                "tone": tone,
                "instruction": f"Write a {tone} {platform} post about {topic}"
            })

    return json.dumps(output, indent=2)


def schedule_post(platform: str, content_summary: str, date: str, time: str) -> str:
    """Mock-schedule a post for publishing"""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "platform": platform,
        "content": content_summary[:200],
        "scheduled_for": f"{date} {time}",
        "status": "Scheduled"
    }
    st.session_state.scheduled_posts.append(entry)
    return f"✅ Post scheduled on {platform} for {date} at {time}"


# ====================== REACT AGENT ======================
def run_content_agent(user_query: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    scheduled = json.dumps(st.session_state.scheduled_posts[-3:]) if st.session_state.scheduled_posts else "None"

    system_prompt = f"""You are a professional Content Creation Agent for social media.
    
    Settings:
    - Target Platforms: {', '.join(platforms)}
    - Tones: {', '.join(tones)}
    - Brand Voice: {st.session_state.get('brand_voice', 'Not specified')}
    - Scheduled Posts: {scheduled}
    
    Your capabilities:
    1. Research latest trends on any topic using web search
    2. Generate platform-specific posts (LinkedIn, Twitter/X, Instagram)
    3. Create 3 different versions: Professional, Casual, and Viral
    4. Add relevant hashtags, captions, and calls-to-action
    5. Mock-schedule posts for publishing
    
    Guidelines:
    - LinkedIn: Professional, longer form, industry insights, thought leadership
    - Twitter/X: Concise (280 chars), punchy, engaging hooks, trending hashtags
    - Instagram: Visual-first captions, storytelling, emojis, 20-30 hashtags
    
    Always output all requested versions clearly labeled. Use structured format."""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "search_trends",
            "description": "Search the web for latest trends and inspiration on a topic",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "generate_content",
            "description": "Generate a social media post for a specific platform and tone",
            "parameters": {"type": "object", "properties": {
                "topic": {"type": "string"},
                "platform": {"type": "string", "description": "LinkedIn, Twitter/X, or Instagram"},
                "tone": {"type": "string", "description": "Professional, Casual, or Viral"}
            }, "required": ["topic", "platform", "tone"]}
        }},
        {"type": "function", "function": {
            "name": "generate_multi_format",
            "description": "Generate content in multiple platforms and tones at once",
            "parameters": {"type": "object", "properties": {
                "topic": {"type": "string"},
                "platforms_str": {"type": "string", "description": "Comma-separated platforms"},
                "tones_str": {"type": "string", "description": "Comma-separated tones"}
            }, "required": ["topic", "platforms_str", "tones_str"]}
        }},
        {"type": "function", "function": {
            "name": "schedule_post",
            "description": "Mock-schedule a post for publishing on a specific date and time",
            "parameters": {"type": "object", "properties": {
                "platform": {"type": "string"},
                "content_summary": {"type": "string", "description": "Brief summary of the post content"},
                "date": {"type": "string", "description": "Publish date YYYY-MM-DD"},
                "time": {"type": "string", "description": "Publish time HH:MM"}
            }, "required": ["platform", "content_summary", "date", "time"]}
        }}
    ]

    tool_functions = {
        "search_trends": search_trends,
        "generate_content": generate_content,
        "generate_multi_format": generate_multi_format,
        "schedule_post": schedule_post
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
            temperature=0.5,
            max_tokens=2000
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
st.subheader("What content do you want to create?")

user_input = st.text_area(
    "Enter your topic or product:",
    placeholder="Create posts about 'Agentic AI in 2026' for all platforms\nOR\nWrite a viral Twitter thread about our new product launch\nOR\nResearch trending topics in AI and create LinkedIn content",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("🚀 Generate Content", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        else:
            with st.spinner("Researching trends & crafting your content..."):
                response = run_content_agent(user_input)

            # Save to history
            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })

            st.subheader("✨ Generated Content")
            st.markdown(response)

with col2:
    if st.button("Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.scheduled_posts = []
        st.rerun()

# ====================== SCHEDULED POSTS ======================
if st.session_state.scheduled_posts:
    st.divider()
    st.subheader("📅 Scheduled Posts")
    for post in reversed(st.session_state.scheduled_posts):
        st.markdown(
            f"**{post['platform']}** — _{post['content'][:80]}..._ "
            f"→ Scheduled for **{post['scheduled_for']}** ({post['status']})"
        )

# ====================== HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Previous Content Sessions")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq + DuckDuckGo • No LangChain")
