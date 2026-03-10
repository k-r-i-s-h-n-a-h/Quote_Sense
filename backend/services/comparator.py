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
    """Uses Pandas to calculate the true, unbiased market average for materials."""
    print("🧮 Running Pandas mathematical analysis...")
    
    # Clean the element names (e.g., make "Wardrobe" and "wardrobe" match perfectly)
    df['clean_element'] = df['element'].astype(str).str.lower().str.strip()
    
    # Calculate the average unit rate across ALL vendors for each element
    # This removes bias by establishing a baseline market rate
    market_rates = df.groupby('clean_element')['unit_rate'].mean().reset_index()
    market_rates.rename(columns={'unit_rate': 'market_avg_rate'}, inplace=True)
    
    # Merge the market average back into our main table to compare individual vendors
    df = pd.merge(df, market_rates, on='clean_element', how='left')
    
    # Calculate how much a vendor deviates from the market average (Positive = Expensive, Negative = Cheaper)
    df['deviation_from_avg'] = df['unit_rate'] - df['market_avg_rate']
    
    return df, market_rates

def generate_unbiased_insight(df, quotes_df):
    """Sends the mathematical summary to Groq for an objective analysis."""
    print("🧠 Generating unbiased AI insights...")
    
    # Prepare a summary of grand totals to send to the LLM
    vendor_totals = quotes_df[['vendor_name', 'grand_total']].to_dict(orient='records')
    
    # Prepare a sample of the most common items and their price spreads
    top_items = df['clean_element'].value_counts().head(10).index
    item_spreads = df[df['clean_element'].isin(top_items)].groupby(['clean_element', 'vendor_name'])['unit_rate'].mean().reset_index()
    
    prompt = f"""
    You are an impartial, highly analytical Quantity Surveyor in Bengaluru.
    Review the following mathematically calculated interior design market data.
    
    Vendor Grand Totals:
    {vendor_totals}
    
    Unit Rate Variations across Vendors for key elements:
    {item_spreads.to_dict(orient='records')}
    
    Provide a highly objective, unbiased summary comparing the vendors. 
    Do not lean towards any single vendor. State the facts clearly:
    1. Who is the most cost-effective overall?
    2. Who charges the highest premium on specific unit rates (e.g., wardrobes or kitchens)?
    3. Are there any notable outliers in the pricing data?
    
    Keep it professional, concise, and structured.
    """

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2 # Slight temperature for readable writing, but mostly analytical
    )
    
    return response.choices[0].message.content

def main():
    try:
        # 1. Fetch
        raw_df = fetch_data()
        quotes_df = raw_df[['vendor_name', 'grand_total']].drop_duplicates()
        
        # 2. Analyze (Math)
        analyzed_df, market_rates = analyze_market_baseline(raw_df)
        
        # Print a quick terminal report of the Math
        print("\n📊 --- PANDAS MARKET BASELINE (Top 5 common items) ---")
        top_elements = analyzed_df['clean_element'].value_counts().head(5).index
        baseline_display = market_rates[market_rates['clean_element'].isin(top_elements)]
        print(baseline_display.to_string(index=False))
        
        # 3. AI Insights
        ai_report = generate_unbiased_insight(analyzed_df, quotes_df)
        
        print("\n🤖 --- UNBIASED AI MARKET ANALYSIS ---")
        print(ai_report)
        print("\n✅ Comparison Complete!")
        
    except Exception as e:
        print(f"❌ Error during comparison: {e}")

if __name__ == "__main__":
    main()