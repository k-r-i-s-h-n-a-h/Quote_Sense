import sys
import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from groq import Groq

# Ensure Python can find the 'backend' folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Load environment variables
load_dotenv()

# Initialize Clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

def fetch_data():
    """Pulls all baseline quotes and items from Supabase."""
    print("📥 Fetching data from Supabase...")
    quotes_response = supabase.table("quotes").select("id, vendor_name, grand_total").execute()
    items_response = supabase.table("quote_items").select("*").execute()
    
    if not quotes_response.data or not items_response.data:
        raise ValueError("No data found in Supabase! Make sure you ran the extractor first.")
        
    quotes_df = pd.DataFrame(quotes_response.data)
    items_df = pd.DataFrame(items_response.data)
    
    # Merge the tables together so every item knows which vendor it belongs to
    df = pd.merge(items_df, quotes_df, left_on="quote_id", right_on="id", suffixes=('_item', '_quote'))
    return df

def analyze_market_baseline(df):
    """Uses Pandas to calculate the true market average for materials."""
    print("🧮 Running Pandas mathematical analysis...")
    
    df['clean_element'] = df['element'].astype(str).str.lower().str.strip()
    
    # Calculate the average unit rate across ALL vendors for each element
    market_rates = df.groupby('clean_element')['unit_rate'].mean().reset_index()
    market_rates.rename(columns={'unit_rate': 'market_avg_rate'}, inplace=True)
    
    df = pd.merge(df, market_rates, on='clean_element', how='left')
    df['deviation_from_avg'] = df['unit_rate'] - df['market_avg_rate']
    
    return df, market_rates

def generate_customer_recommendation(df, quotes_df):
    """Sends the expanded mathematical summary to Groq for a final customer recommendation."""
    print("🧠 Generating Expert AI Recommendation...")
    
    # Prepare a summary of grand totals
    vendor_totals = quotes_df[['vendor_name', 'grand_total']].sort_values(by='grand_total').to_dict(orient='records')
    
    # INCREASED TO 30: Grab a much larger sample of the most common items across the 4 quotes
    top_items = df['clean_element'].value_counts().head(30).index
    item_spreads = df[df['clean_element'].isin(top_items)].groupby(['clean_element', 'vendor_name'])['unit_rate'].mean().reset_index()
    
    prompt = f"""
    You are 'QuoteSense', an expert Interior Design Consultant in Bengaluru advising a customer.
    Review the following mathematically calculated market data comparing multiple vendor quotes.
    
    Vendor Grand Totals (Sorted Lowest to Highest):
    {vendor_totals}
    
    Unit Rate Variations across Vendors for Top 30 Key Elements:
    {item_spreads.to_dict(orient='records')}
    
    Your job is to analyze this data and give the customer a definitive recommendation on who to hire.
    Structure your response exactly like this:
    
    ### 🏆 Final Recommendation
    (Explicitly state: "We recommend you choose [Vendor Name]." and give a 2-sentence justification based on price and fairness).
    
    ### 💰 Cost Overview
    (Briefly summarize who is the cheapest and who is the most expensive overall).
    
    ### 🕵️ Tactical Pricing & Red Flags
    (Look deeply at the unit rates. Is a vendor offering cheap woodwork (like wardrobes/lofts) but sneakily marking up hardware, profiles, mirrors, or handling fees to recover their margin? Call out any vendor doing this so the customer is warned).
    
    Speak directly to the customer in a professional, helpful, and decisive tone.
    """

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3 # Slightly higher temperature to make it sound like a friendly consultant
    )
    
    return response.choices[0].message.content

def main():
    try:
        raw_df = fetch_data()
        quotes_df = raw_df[['vendor_name', 'grand_total']].drop_duplicates()
        
        analyzed_df, market_rates = analyze_market_baseline(raw_df)
        
        print("\n📊 --- PANDAS MARKET BASELINE (Top 5 Display) ---")
        top_elements = analyzed_df['clean_element'].value_counts().head(5).index
        baseline_display = market_rates[market_rates['clean_element'].isin(top_elements)]
        print(baseline_display.to_string(index=False))
        
        # Call the newly updated AI function
        ai_report = generate_customer_recommendation(analyzed_df, quotes_df)
        
        print("\n🤖 --- QUOTESENSE EXPERT RECOMMENDATION ---")
        print(ai_report)
        print("\n✅ Comparison Complete!")
        
    except Exception as e:
        print(f"❌ Error during comparison: {e}")

if __name__ == "__main__":
    main()