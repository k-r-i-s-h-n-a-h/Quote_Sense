# backend/models/schema.py
from pydantic import BaseModel, Field
from typing import List, Optional

class WorkItem(BaseModel):
    # Notice the updated description here!
    sub_service: str = Field(description="MUST perfectly match one of the sub-services listed in the MASTER TAXONOMY under the chosen category.")
    work_title: Optional[str] = Field(description="The title or specific notes attached to the work item")
    description: Optional[str] = Field(description="The detailed scope or material description")
    quantity: float = Field(description="The numeric value in the QTY column")
    pricing_method: str = Field(description="The text in the PRICING column, e.g., 'Square Feet'")
    rate: float = Field(description="The unit rate in the RATE column")
    amount: float = Field(description="The total amount for this specific line item")

class MainService(BaseModel):
    # Notice the updated description here!
    service_category: str = Field(description="MUST perfectly match one of the 11 Main Categories from the MASTER TAXONOMY (e.g., 'Residential Construction', 'Plumbing Services').")
    items: List[WorkItem] = Field(description="A list of all the work items listed under this specific service category")

class ExtractedQuote(BaseModel):
    vendor_name: str = Field(description="The company providing the quote.")
    client_name: str = Field(description="The customer receiving the quote.")
    quote_date: str = Field(description="The date of the quote.")
    grand_total: float = Field(description="The final total price including GST.")
    services: List[MainService] = Field(description="A list of all the main service categories added to this quote")