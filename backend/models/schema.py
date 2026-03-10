from pydantic import BaseModel, Field
from typing import List

class NormalizedItem(BaseModel):
    room: str = Field(description="The space where the work is happening, e.g., 'Master Bedroom', 'Kitchen', 'Office Floor'. If unknown, use 'General'.")
    element: str = Field(description="The specific furniture or item, e.g., 'Swing Wardrobe', 'Base cabinet', 'Reception Desk'.")
    specifications: str = Field(description="The material specs, e.g., '16 MM MARINE BOARD', '18mm MR Grade 303 ply', 'Hettich hardware'.")
    quantity: float = Field(description="The numeric area, quantity, or SQFT. Must be a number.")
    unit_rate: float = Field(description="The cost per unit or per sqft. Must be a number.")
    total_amount: float = Field(description="The total final cost for this specific line item.")

class ExtractedQuote(BaseModel):
    vendor_name: str = Field(description="The company providing the quote.")
    client_name: str = Field(description="The customer receiving the quote.")
    quote_date: str = Field(description="The date of the quote.")
    grand_total: float = Field(description="The final total price including GST.")
    items: List[NormalizedItem] = Field(description="The list of all individual furniture and woodwork items.")