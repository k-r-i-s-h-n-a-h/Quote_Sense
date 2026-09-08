# backend/models/schema.py
from pydantic import BaseModel, Field
from typing import List, Optional

class WorkItem(BaseModel):
    # Notice the updated description here!
    sub_service: str = Field(description="MUST perfectly match one of the sub-services listed in the MASTER TAXONOMY under the chosen category.")
    item_name: Optional[str] = Field(description="The EXACT item label as written in the DESCRIPTION column of the PDF, copied VERBATIM and NOT normalized (e.g. 'Granite', 'Loft', 'Wall Decor', 'Wardrobe', 'Tandem Pullouts'). This is the vendor's original wording.")
    work_title: Optional[str] = Field(description="The room or location the item belongs to, e.g. 'Kitchen', 'Master bedroom', 'Living room', 'Balcony', 'Overall space'.")
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
    quote_number: str = Field(description="The quote/quotation reference number, e.g. 'Q52OW75' (strip any leading '#'). Empty string if not present.")
    quote_date: str = Field(description="The date of the quote, e.g. '07/05/2026'.")
    vendor_phone: str = Field(description="The vendor's contact / WhatsApp number as printed on the quote (digits, with country code if shown). Empty string if not present.")
    subtotal: float = Field(description="The 'Subtotal' amount BEFORE TatvaOps service charges and taxes (the sum of all line-item amounts). Use 0.0 if not present.")
    grand_total: float = Field(description="The final total price including GST.")
    services: List[MainService] = Field(description="A list of all the main service categories added to this quote")