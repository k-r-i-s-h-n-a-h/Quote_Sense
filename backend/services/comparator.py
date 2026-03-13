import sys
import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from groq import Groq

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

def fetch_data(session_id):
    print(f"📥 Fetching data for Session: {session_id}...")
    # Only grab quotes for this specific session
    quotes_response = supabase.table("quotes").select("id, vendor_name, grand_total").eq("session_id", session_id).execute()
    
    if not quotes_response.data:
        raise ValueError("No data found for this session!")
        
    quotes_df = pd.DataFrame(quotes_response.data)
    quote_ids = quotes_df['id'].tolist()
    
    items_response = supabase.table("quote_items").select("*").in_("quote_id", quote_ids).execute()
    items_df = pd.DataFrame(items_response.data)
    
    df = pd.merge(items_df, quotes_df, left_on="quote_id", right_on="id", suffixes=('_item', '_quote'))
    return df

def analyze_market_baseline(df):
    print("🧮 Running Pandas mathematical analysis...")
    df['clean_element'] = df['element'].astype(str).str.lower().str.strip()
    market_rates = df.groupby('clean_element')['unit_rate'].mean().reset_index()
    market_rates.rename(columns={'unit_rate': 'market_avg_rate'}, inplace=True)
    df = pd.merge(df, market_rates, on='clean_element', how='left')
    df['deviation_from_avg'] = df['unit_rate'] - df['market_avg_rate']
    return df, market_rates

def generate_customer_recommendation(df, quotes_df):
    print("🧠 Generating Expert AI Recommendation...")
    
    # 1. Grab all the vendor totals
    vendor_totals = quotes_df[['vendor_name', 'grand_total']].sort_values(by='grand_total').to_dict(orient='records')
    
    # 2. NEW LOGIC: Calculate the "Ground Truth" Mean (Average) of all quotes
    mean_grand_total = quotes_df['grand_total'].mean()
    
    # 3. Get the item spreads and material specs
    top_items = df['clean_element'].value_counts().head(30).index
    item_spreads = df[df['clean_element'].isin(top_items)].groupby(['clean_element', 'vendor_name'])['unit_rate'].mean().reset_index()
    item_specs = df[df['clean_element'].isin(top_items)][['clean_element', 'vendor_name', 'specifications']].drop_duplicates().to_dict(orient='records')

    prompt = f"""
    You are 'QuoteSense', an elite Interior Design Consultant in Bengaluru advising a customer.
    We have calculated the mathematical "Ground Truth" (Mean Average) of the submitted quotes to establish a fair market baseline.
    
    Project Ground Truth (Average Cost): ₹{mean_grand_total:,.2f}
    
    Vendor Grand Totals:
    {vendor_totals}
    
    Unit Rate Variations across Vendors:
    {item_spreads.to_dict(orient='records')}

    Extracted Material Specifications:
    {item_specs}
    
    CRITICAL RULE: "Cheapest does NOT equal Best." A quote drastically below the Ground Truth often means low-grade materials (like cheap MDF instead of BWP Plywood) or hidden costs. 
    Your goal is to find the most FAIR and RELIABLE quote by comparing how much each vendor deviates from the Ground Truth average. The ideal "Best Value" is usually the vendor closest to the mean, offering consistent unit rates and good materials.
    
    Structure your response EXACTLY like this using markdown:
    
    ### ⚖️ Market Baseline Analysis
    (State the Ground Truth average. Briefly discuss how the vendors deviate from this mean—who is suspiciously below it, and who is way above it).
    
    ### 🏆 The 'Fair Value' Recommendation
    (Recommend the vendor that is closest to the ground truth mean with consistent unit rates and quality materials. Explain why this is the safest, most transparent choice).
    
    ### 💸 The Budget Pick (With High-Risk Warnings)
    (Identify the cheapest vendor. Strictly warn the customer that being drastically below the market mean often signals compromised material quality, untrained labor, or hidden fees later).
    
    ### 🕵️ Tactical Pricing & Red Flags
    (Identify vendors marking up specific items like hardware/mirrors to recover margins, or explicitly point out if a cheap vendor is using inferior materials based on the specifications).

    ### 🎯 Final Verdict
    (Do not waffle or give multiple options here. Based on all the data, explicitly state exactly ONE vendor the customer should hire today and in one sentence say why.)
    """

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2 # Low temperature for highly analytical reasoning
    )
    return response.choices[0].message.content

def run_comparison(session_id):
    """This is the function FastAPI was looking for!"""
    try:
        raw_df = fetch_data(session_id)
        quotes_df = raw_df[['vendor_name', 'grand_total']].drop_duplicates()
        analyzed_df, market_rates = analyze_market_baseline(raw_df)
        ai_report = generate_customer_recommendation(analyzed_df, quotes_df)

        #math for the nextjs chart
        chart_data = []
        for index, row in quotes_df.iterrows():
            chart_data.append({
                "vendor": row['vendor_name'],
                "total": float(row['grand_total'])
            })

        # Sort so the chart goes from cheapest to most expensive
        chart_data = sorted(chart_data, key=lambda x: x['total'])

        return {
            "report": ai_report,
            "chart_data": chart_data
        }
    except Exception as e:
        return {
            "report": f"❌ Error during comparison: {e}",
            "chart_data": []
        }
    
def handle_chat_query(session_id, user_message):
    """Feeds the user's specific session data to the LLM to answer their chat question."""
    print(f"💬 Processing chat query for Session: {session_id}...")
    try:
        # 1. Fetch the exact data for this specific user
        raw_df = fetch_data(session_id)
        
        # ✅ THE FIX: We must run the cleaning function to create the 'clean_element' column!
        analyzed_df, _ = analyze_market_baseline(raw_df)
        
        quotes_df = raw_df[['vendor_name', 'grand_total']].drop_duplicates()
        
        # 2. Summarize the totals and key items so the LLM has perfect context
        vendor_totals = quotes_df.to_dict(orient='records')
        
        # Notice we are now using analyzed_df instead of raw_df!
        top_items = analyzed_df['clean_element'].value_counts().head(20).index
        item_spreads = analyzed_df[analyzed_df['clean_element'].isin(top_items)].groupby(['clean_element', 'vendor_name'])['unit_rate'].mean().reset_index().to_dict(orient='records')

        item_specs = analyzed_df[analyzed_df['clean_element'].isin(top_items)][['clean_element', 'vendor_name', 'specifications']].drop_duplicates().to_dict(orient='records')
        # 3. Create the Agentic Prompt
        prompt = f"""
        You are 'QuoteSense', an expert interior design AI assistant.
        The user has uploaded and compared several quotes. Here is the exact mathematical data for their session:
        
        Vendor Totals: {vendor_totals}
        
        Key Item Rates across Vendors: {item_spreads}

        Material Specifications: {item_specs}

        User Question: "{user_message}"

        CRITICAL RULES:
        1. Answer the question accurately based ONLY on the provided data. 
        2. Be concise, professional, and helpful. 
        3. Do not guess. If the data doesn't contain the answer, politely say you don't have that specific detail in the current quotes.
        """

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"❌ Sorry, I encountered an error while accessing your data: {e}"