# backend/models/taxonomy.py

"""
TATVAOPS MASTER TAXONOMY
This dictionary maps the 11 Main Service Categories to their 137 Official Sub-Services.
It is injected into the LLM prompt to prevent hallucinated service names.
"""

TATVAOPS_TAXONOMY = {
    "Residential Construction": [
        "Soil Test & Geotechnical Analysis",
        "Site Clearing & Excavation",
        "Foundation (Isolated / Raft / Pile)",
        "Footings",
        "Plinth Beam",
        "Backfilling & Compaction",
        "Sill Level",
        "Columns",
        "Lintel",
        "Slab (Ground / First / Terrace)",
        "Staircase Construction",
        "Masonry (Blockwork / Brickwork)",
        "Parapet Wall",
        "Reinforcement (Rebar Work)",
        "Shuttering & Formwork",
        "Concrete Pouring",
        "Waterproofing (Basement / Terrace)",
        "Plastering (Internal / External)",
        "Flooring Base Screed",
        "Terrace Treatment",
        "Compound Wall",
        "Septic Tank / STP",
        "Borewell / Sump",
        "Overhead Tank"
    ],
    "Interiors": [
        "2D Floor Planning",
        "3D Visualization",
        "Concept Design",
        "BOQ Preparation",
        "Material Selection Assistance",
        "Modular Kitchen",
        "Wardrobes",
        "TV Units",
        "Crockery Units",
        "Vanity Units",
        "Storage Solutions",
        "False Ceiling",
        "Flooring Replacement",
        "Tiling",
        "Partition Walls",
        "Structural Alterations",
        "Bathroom Renovation",
        "Kitchen Renovation",
        "Wallpaper",
        "Wall Panels",
        "Soft Furnishings",
        "Custom Furniture",
        "Lighting Design"
    ],
    "Painting": [
        "Interior Painting",
        "Exterior Painting",
        "Texture Painting",
        "Waterproof Coating",
        "Wood Polishing",
        "PU Coating",
        "Metal Painting",
        "Enamel Painting",
        "Anti-Fungal Treatment",
        "Crack Filling & Surface Preparation"
    ],
    "Electrical Services": [
        "Wiring (Concealed / Surface)",
        "DB Installation",
        "Earthing",
        "Lighting Installation",
        "Fan & Fixture Installation",
        "UPS / Inverter Installation",
        "Generator Installation",
        "Load Enhancement",
        "Electrical Safety Audit",
        "EV Charger Installation"
    ],
    "Plumbing Services": [
        "Water Supply Piping",
        "Drainage Piping",
        "Bathroom Fittings Installation",
        "Kitchen Plumbing",
        "Borewell Plumbing",
        "STP / Septic Connections",
        "Water Heater Installation",
        "Leakage Detection",
        "Pressure Testing",
        "Plumbing Maintenance"
    ],
    "Solar Services": [
        "Solar Feasibility Study",
        "On-Grid Solar Installation",
        "Off-Grid Solar Installation",
        "Hybrid Solar System",
        "Net Metering Assistance",
        "Solar Panel Cleaning",
        "Solar Maintenance",
        "Solar Battery Setup",
        "Solar Water Heater",
        "Solar Carport"
    ],
    "Event Management": [
        "Wedding Planning",
        "Corporate Events",
        "Birthday Events",
        "Stage Setup",
        "Lighting & Sound",
        "Catering",
        "Décor",
        "Photography & Videography",
        "Venue Booking",
        "Event Staffing"
    ],
    "Property Development": [
        "Land Acquisition Advisory",
        "Layout Planning",
        "Approvals & Compliance",
        "Joint Development Agreements",
        "Villa Development",
        "Apartment Development",
        "Commercial Development",
        "Feasibility Study",
        "Project Marketing",
        "Property Valuation"
    ],
    "Home Automation": [
        "Smart Lighting",
        "Smart Switches",
        "Smart Curtains",
        "CCTV Installation",
        "Video Door Phone",
        "Access Control",
        "Smart Locks",
        "HVAC Automation",
        "Voice Control Integration",
        "Centralized Control Systems"
    ],
    "Farm Infrastructure Setup": [
        "Cow Shed Construction",
        "Poultry Shed",
        "Goat Shed",
        "Storage Sheds",
        "Fencing",
        "Borewell Installation",
        "Solar Pump Setup",
        "Compost Pit Setup",
        "Biogas Plant",
        "Farm Roads"
    ],
    "Irrigation Automation": [
        "Drip Irrigation Setup",
        "Sprinkler System",
        "Smart Irrigation Controllers",
        "Soil Moisture Sensors",
        "Automated Pump Control",
        "Fertigation Systems",
        "Rainwater Harvesting",
        "Water Level Monitoring",
        "IoT-Based Irrigation",
        "Irrigation Maintenance"
    ]
}