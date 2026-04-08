import streamlit as st
from groq import Groq
import json
from duckduckgo_search import DDGS
from datetime import datetime, timedelta

st.set_page_config(page_title="Smart Travel Planner Agent", layout="wide")
st.title("✈️ Smart Travel Planner Agent")
st.markdown("**Plan trips • Search flights & hotels • Day-by-day itinerary • Cost estimates • Remembers preferences**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔑 Setup")
    api_key = st.text_input("Groq API Key", type="password", value=st.session_state.get("groq_key", ""))
    if api_key:
        st.session_state.groq_key = api_key
        st.success("✅ Groq connected")

    st.divider()
    st.header("🧳 Trip Details")
    destination = st.text_input("Destination", value=st.session_state.get("destination", ""), placeholder="e.g. Tokyo, Japan")
    start_date = st.date_input("Start Date", value=datetime.now().date() + timedelta(days=30))
    end_date = st.date_input("End Date", value=datetime.now().date() + timedelta(days=35))
    budget = st.number_input("Budget (USD)", min_value=100, max_value=50000, value=2000, step=100)
    interests = st.multiselect(
        "Your Interests",
        ["Culture & History", "Food & Cuisine", "Adventure & Outdoors", "Shopping", "Nightlife", 
         "Nature & Parks", "Temples & Monuments", "Beach & Relaxation", "Photography", "Art & Museums"],
        default=["Food & Cuisine", "Culture & History"]
    )
    travelers = st.number_input("Number of Travelers", min_value=1, max_value=10, value=1)

    if destination:
        st.session_state.destination = destination

    st.divider()
    st.header("📌 Travel Preferences")
    travel_style = st.selectbox("Travel Style", ["Budget", "Mid-range", "Luxury"])
    dietary = st.text_input("Dietary Restrictions", placeholder="e.g. Vegetarian, No seafood")

# ====================== SESSION STATE ======================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # Remembers past travel sessions
if "past_preferences" not in st.session_state:
    st.session_state.past_preferences = []

# ====================== TOOLS ======================
def search_destination(query: str) -> str:
    """Search the web for destination info, flights, hotels, attractions"""
    try:
        results = list(DDGS().text(query, max_results=5))
        if not results:
            return "No results found."
        output = []
        for r in results:
            output.append(f"**{r['title']}**\n{r['body']}\nSource: {r['href']}")
        return "\n\n".join(output)
    except Exception:
        return "Error searching. Please try again."


def build_itinerary(destination: str, num_days: int, interests_str: str, style: str) -> str:
    """Build a day-by-day travel itinerary (mock planner)"""
    interests_list = [i.strip() for i in interests_str.split(",")]
    itinerary = {"destination": destination, "style": style, "days": []}

    for day in range(1, num_days + 1):
        day_plan = {
            "day": day,
            "theme": interests_list[(day - 1) % len(interests_list)] if interests_list else "Explore",
            "morning": f"Morning activity for Day {day} in {destination}",
            "afternoon": f"Afternoon activity for Day {day} in {destination}",
            "evening": f"Evening activity for Day {day} in {destination}",
            "meals": f"Recommended {style.lower()} restaurants"
        }
        itinerary["days"].append(day_plan)

    return json.dumps(itinerary, indent=2)


def calculate_cost(destination: str, num_days: int, travelers: int, style: str) -> str:
    """Estimate total trip cost"""
    # Mock cost estimation based on style
    daily_costs = {
        "Budget": {"hotel": 40, "food": 25, "transport": 15, "activities": 20},
        "Mid-range": {"hotel": 100, "food": 50, "transport": 30, "activities": 40},
        "Luxury": {"hotel": 250, "food": 100, "transport": 60, "activities": 80}
    }
    costs = daily_costs.get(style, daily_costs["Mid-range"])

    breakdown = {
        "destination": destination,
        "travelers": travelers,
        "num_days": num_days,
        "style": style,
        "daily_breakdown": costs,
        "daily_total_per_person": sum(costs.values()),
        "total_per_person": sum(costs.values()) * num_days,
        "grand_total": sum(costs.values()) * num_days * travelers,
        "note": "Estimates based on average costs. Flight costs not included — search separately."
    }
    return json.dumps(breakdown, indent=2)


def save_preference(destination: str, liked: str, disliked: str) -> str:
    """Save travel preference for future recommendations"""
    pref = {
        "timestamp": datetime.now().strftime("%Y-%m-%d"),
        "destination": destination,
        "liked": liked,
        "disliked": disliked
    }
    st.session_state.past_preferences.append(pref)
    return f"✅ Saved preference: Liked '{liked}' in {destination}"


# ====================== REACT AGENT ======================
def run_travel_agent(user_query: str):
    if not st.session_state.get("groq_key"):
        return "Please enter your Groq API key in the sidebar."

    client = Groq(api_key=st.session_state.groq_key)

    num_days = (end_date - start_date).days
    if num_days <= 0:
        num_days = 5

    past_prefs = json.dumps(st.session_state.past_preferences[-3:]) if st.session_state.past_preferences else "None"

    system_prompt = f"""You are a Smart Travel Planner Agent that helps plan complete trips.
    
    Current Trip Details:
    - Destination: {destination or 'Not specified'}
    - Dates: {start_date} to {end_date} ({num_days} days)
    - Budget: ${budget} USD
    - Travelers: {travelers}
    - Interests: {', '.join(interests)}
    - Style: {travel_style}
    - Dietary: {dietary or 'None'}
    - Past Preferences: {past_prefs}
    
    Your capabilities:
    1. Search for flights, hotels, attractions, and local tips
    2. Build a detailed day-by-day itinerary
    3. Calculate estimated trip costs
    4. Remember the user's travel preferences
    
    Provide practical, well-structured travel plans. Use JSON for structured reports."""

    tool_schemas = [
        {"type": "function", "function": {
            "name": "search_destination",
            "description": "Search the web for destination info, flights, hotels, or attractions",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "build_itinerary",
            "description": "Build a day-by-day travel itinerary",
            "parameters": {"type": "object", "properties": {
                "destination": {"type": "string"},
                "num_days": {"type": "integer"},
                "interests_str": {"type": "string", "description": "Comma-separated interests"},
                "style": {"type": "string", "description": "Budget, Mid-range, or Luxury"}
            }, "required": ["destination", "num_days", "interests_str", "style"]}
        }},
        {"type": "function", "function": {
            "name": "calculate_cost",
            "description": "Estimate total trip cost based on destination, days, travelers and style",
            "parameters": {"type": "object", "properties": {
                "destination": {"type": "string"},
                "num_days": {"type": "integer"},
                "travelers": {"type": "integer"},
                "style": {"type": "string"}
            }, "required": ["destination", "num_days", "travelers", "style"]}
        }},
        {"type": "function", "function": {
            "name": "save_preference",
            "description": "Save a travel preference for future recommendations",
            "parameters": {"type": "object", "properties": {
                "destination": {"type": "string"},
                "liked": {"type": "string", "description": "What the user liked"},
                "disliked": {"type": "string", "description": "What the user disliked"}
            }, "required": ["destination", "liked", "disliked"]}
        }}
    ]

    tool_functions = {
        "search_destination": search_destination,
        "build_itinerary": build_itinerary,
        "calculate_cost": calculate_cost,
        "save_preference": save_preference
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
            temperature=0.4,
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
st.subheader("Plan your next trip")

user_input = st.text_area(
    "What would you like to plan?",
    placeholder="Plan a 5-day trip to Tokyo with focus on food and culture\nOR\nSearch for budget hotels in Bali\nOR\nBuild me a detailed itinerary with cost breakdown",
    height=120
)

col1, col2 = st.columns([3, 1])
with col1:
    if st.button("🚀 Plan My Trip", type="primary", use_container_width=True):
        if not st.session_state.get("groq_key"):
            st.error("Please enter Groq API key")
        else:
            with st.spinner("Planning your perfect trip..."):
                response = run_travel_agent(user_input)

            # Save to history
            st.session_state.chat_history.append({
                "time": datetime.now().strftime("%H:%M"),
                "query": user_input[:80],
                "response": response
            })

            st.subheader("🗺️ Your Travel Plan")
            st.markdown(response)

with col2:
    if st.button("Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.past_preferences = []
        st.rerun()

# ====================== PAST PREFERENCES ======================
if st.session_state.past_preferences:
    st.divider()
    st.subheader("📌 Your Travel Preferences")
    for pref in reversed(st.session_state.past_preferences):
        st.markdown(f"**{pref['destination']}** — Liked: _{pref['liked']}_ | Disliked: _{pref['disliked']}_ ({pref['timestamp']})")

# ====================== HISTORY ======================
if st.session_state.chat_history:
    st.divider()
    st.subheader("📖 Previous Travel Sessions")
    for entry in reversed(st.session_state.chat_history):
        with st.expander(f"[{entry['time']}] {entry['query']}"):
            st.write(entry["response"])

st.caption("Built for Agentic AI Workshop • Pure Groq + DuckDuckGo • No LangChain")
