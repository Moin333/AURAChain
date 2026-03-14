"""
AURAChain Test Dataset Generator
Generates realistic retail inventory + sales data designed to exercise all agents.
"""
import csv
import random
import math
import os
from datetime import datetime, timedelta

random.seed(42)

# ── Configuration ──

STORES = [
    {"id": "STR_MUM_01", "name": "Mumbai Central", "region": "West"},
    {"id": "STR_DEL_02", "name": "Delhi Connaught", "region": "North"},
    {"id": "STR_BLR_03", "name": "Bangalore Koramangala", "region": "South"},
    {"id": "STR_KOL_04", "name": "Kolkata Park Street", "region": "East"},
]

PRODUCTS = [
    {"id": "SKU_SNK_001", "name": "AuraFlex Sneakers", "category": "Footwear", "base_price": 3499, "base_demand": 18},
    {"id": "SKU_SNK_002", "name": "StreetRun Pro", "category": "Footwear", "base_price": 4299, "base_demand": 12},
    {"id": "SKU_TSH_003", "name": "DryFit Training Tee", "category": "Apparel", "base_price": 999, "base_demand": 30},
    {"id": "SKU_TSH_004", "name": "Classic Polo Shirt", "category": "Apparel", "base_price": 1499, "base_demand": 22},
    {"id": "SKU_JKT_005", "name": "WindBlock Jacket", "category": "Apparel", "base_price": 2999, "base_demand": 8},
    {"id": "SKU_BAG_006", "name": "Urban Backpack", "category": "Accessories", "base_price": 1799, "base_demand": 15},
    {"id": "SKU_CAP_007", "name": "Sport Cap", "category": "Accessories", "base_price": 599, "base_demand": 25},
    {"id": "SKU_WAT_008", "name": "FitTrack Smartwatch", "category": "Electronics", "base_price": 7999, "base_demand": 5},
    {"id": "SKU_EAR_009", "name": "BassBoost Earbuds", "category": "Electronics", "base_price": 2499, "base_demand": 10},
    {"id": "SKU_SHO_010", "name": "FlexiRun Sandals", "category": "Footwear", "base_price": 1299, "base_demand": 20},
    {"id": "SKU_TRK_011", "name": "TrackFit Joggers", "category": "Apparel", "base_price": 1999, "base_demand": 16},
    {"id": "SKU_SOK_012", "name": "CoolStride Socks (3-Pack)", "category": "Accessories", "base_price": 349, "base_demand": 40},
    {"id": "SKU_SHR_013", "name": "Performance Shorts", "category": "Apparel", "base_price": 899, "base_demand": 18},
    {"id": "SKU_BOT_014", "name": "Hydra Flask 750ml", "category": "Accessories", "base_price": 699, "base_demand": 20},
    {"id": "SKU_SNK_015", "name": "RetroKick Limited", "category": "Footwear", "base_price": 5999, "base_demand": 6},
]

# Indian holidays/festivals (approximate dates for 2024-2025)
HOLIDAYS = {
    # 2024
    "2024-01-15": "Makar Sankranti", "2024-01-26": "Republic Day",
    "2024-03-25": "Holi", "2024-03-29": "Good Friday",
    "2024-04-11": "Eid ul-Fitr", "2024-04-14": "Baisakhi",
    "2024-08-15": "Independence Day", "2024-08-26": "Janmashtami",
    "2024-09-07": "Onam", "2024-10-02": "Gandhi Jayanti",
    "2024-10-12": "Dussehra", "2024-10-20": "Karwa Chauth",
    "2024-10-29": "Dhanteras", "2024-10-31": "Diwali",
    "2024-11-01": "Diwali_Day2", "2024-11-02": "Bhai Dooj",
    "2024-11-15": "Guru Nanak Jayanti",
    "2024-12-25": "Christmas",
    # 2025
    "2025-01-14": "Makar Sankranti", "2025-01-26": "Republic Day",
    "2025-03-14": "Holi", "2025-03-31": "Eid ul-Fitr",
    "2025-04-14": "Baisakhi",
    "2025-08-15": "Independence Day", "2025-08-16": "Janmashtami",
    "2025-09-22": "Onam", "2025-10-02": "Gandhi Jayanti",
    "2025-10-02": "Dussehra", "2025-10-17": "Dhanteras",
    "2025-10-19": "Diwali", "2025-10-20": "Diwali_Day2",
    "2025-10-21": "Bhai Dooj",
    "2025-11-05": "Guru Nanak Jayanti",
    "2025-12-25": "Christmas",
}

def is_near_holiday(date, days_before=5, days_after=2):
    """Check if date is near a holiday (pre-holiday shopping surge)."""
    for hd_str in HOLIDAYS:
        hd = datetime.strptime(hd_str, "%Y-%m-%d")
        diff = (date - hd).days
        if -days_before <= diff <= days_after:
            return True, HOLIDAYS[hd_str]
    return False, None

def is_diwali_season(date):
    """Oct 1 – Nov 10 each year."""
    return date.month == 10 or (date.month == 11 and date.day <= 10)

def is_monsoon(date):
    """Jul – Sep."""
    return date.month in [7, 8, 9]

def is_summer(date):
    """Apr – Jun."""
    return date.month in [4, 5, 6]

def seasonal_factor(date, category):
    """Product-specific seasonal multipliers."""
    month = date.month
    
    if category == "Footwear":
        # Sneakers peak: Oct-Nov (Diwali/festivals), Apr-May (new season)
        if is_diwali_season(date): return 1.45
        if month in [4, 5]: return 1.2
        if is_monsoon(date): return 0.75  # Rain reduces footwear sales
        return 1.0
    
    elif category == "Apparel":
        # Jackets peak in winter, T-shirts in summer
        if month in [11, 12, 1, 2]: return 1.3
        if is_summer(date): return 1.15
        return 1.0
    
    elif category == "Electronics":
        # Diwali gifting spike, year-end shopping
        if is_diwali_season(date): return 1.6
        if month == 12: return 1.3
        return 1.0
    
    elif category == "Accessories":
        # Steady with festival bump
        if is_diwali_season(date): return 1.25
        return 1.0
    
    return 1.0

def trend_factor(date, start_date):
    """Gradual upward trend ~0.5% per month."""
    months_elapsed = (date - start_date).days / 30.0
    return 1.0 + (months_elapsed * 0.005)

def day_of_week_factor(date):
    """Weekend spike."""
    dow = date.weekday()
    if dow == 5: return 1.35  # Saturday
    if dow == 6: return 1.25  # Sunday
    if dow == 0: return 0.85  # Monday dip
    return 1.0

def promotion_schedule(date, product_id):
    """Deterministic promotions: end-of-season sales, festival sales."""
    month, day = date.month, date.day
    
    # End-of-season clearance (Jan, Jul)
    if month == 1 and 10 <= day <= 25: return True
    if month == 7 and 15 <= day <= 31: return True
    
    # Diwali mega sale (Oct 25 – Nov 5)
    if (month == 10 and day >= 25) or (month == 11 and day <= 5): return True
    
    # Republic Day sale
    if month == 1 and 24 <= day <= 28: return True
    
    # Random flash sale (seeded by product)
    hash_val = hash(f"{date.isoformat()}_{product_id}")
    if hash_val % 47 == 0: return True
    
    return False

def competitor_price(base_price, date, product_id):
    """Competitor pricing: generally ±15%, aggressive during sales."""
    noise = random.gauss(0, 0.05)
    month = date.month
    
    # Competitors aggressive during sale seasons
    if month in [1, 7, 10, 11]:
        return round(base_price * (0.85 + noise), 2)
    
    return round(base_price * (0.95 + noise + random.uniform(-0.05, 0.1)), 2)

def supplier_delay(date, region):
    """Supplier delays: monsoon disruptions, year-end congestion."""
    base_delay = 0
    
    if is_monsoon(date):
        base_delay = random.choices([0, 1, 2, 3, 5, 7], weights=[30, 25, 20, 15, 7, 3])[0]
    elif date.month in [10, 11]:  # Festival congestion
        base_delay = random.choices([0, 1, 2, 3], weights=[50, 25, 15, 10])[0]
    else:
        base_delay = random.choices([0, 0, 1, 2], weights=[60, 20, 15, 5])[0]
    
    # East region has slightly worse logistics
    if region == "East":
        base_delay += random.choices([0, 1, 2], weights=[60, 30, 10])[0]
    
    return base_delay

def inject_messiness(value, field, row_idx):
    """Inject realistic data quality issues."""
    # ~2% missing values
    if random.random() < 0.02:
        return ""
    
    # Inconsistent casing for text fields (~3%)
    if field in ["product_name", "category", "region"] and random.random() < 0.03:
        if isinstance(value, str):
            choice = random.choice(["upper", "lower", "title_weird"])
            if choice == "upper": return value.upper()
            if choice == "lower": return value.lower()
            return value.swapcase()
    
    # Outliers in numeric fields (~1%)
    if field in ["units_sold", "revenue"] and random.random() < 0.01:
        if isinstance(value, (int, float)) and value > 0:
            return value * random.choice([3.5, 4.0, 0.1])  # Spike or crash
    
    # Occasional negative inventory (data entry error)
    if field == "inventory_level" and random.random() < 0.005:
        return -abs(value)
    
    return value

def generate_dataset():
    """Generate the full dataset."""
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 12, 31)
    
    rows = []
    inventory_tracker = {}  # (store_id, product_id) -> level
    
    # Initialize inventory
    for store in STORES:
        for product in PRODUCTS:
            key = (store["id"], product["id"])
            inventory_tracker[key] = random.randint(80, 200)
    
    current_date = start_date
    row_idx = 0
    
    while current_date <= end_date:
        for store in STORES:
            for product in PRODUCTS:
                key = (store["id"], product["id"])
                
                # ── Demand Calculation ──
                base = product["base_demand"]
                
                # Apply factors
                trend = trend_factor(current_date, start_date)
                season = seasonal_factor(current_date, product["category"])
                dow = day_of_week_factor(current_date)
                
                is_promo = promotion_schedule(current_date, product["id"])
                promo_mult = 1.35 if is_promo else 1.0
                
                near_hol, holiday_name = is_near_holiday(current_date)
                holiday_mult = 1.4 if near_hol else 1.0
                
                # Price elasticity
                comp_price = competitor_price(product["base_price"], current_date, product["id"])
                price_ratio = comp_price / product["base_price"]
                price_effect = 1.0 + (price_ratio - 1.0) * 0.3  # If competitor cheaper, we sell less
                
                # Supplier delay effect on inventory
                delay_days = supplier_delay(current_date, store["region"])
                
                # Customer rating (slowly improving with occasional dips)
                days_elapsed = (current_date - start_date).days
                base_rating = 3.8 + (days_elapsed / 730) * 0.5  # 3.8 → 4.3 over 2 years
                rating = round(min(5.0, max(1.0, base_rating + random.gauss(0, 0.3))), 1)
                
                # Final demand
                demand = base * trend * season * dow * promo_mult * holiday_mult * price_effect
                demand *= random.uniform(0.7, 1.3)  # Random noise
                units_sold = max(0, round(demand))
                
                # ── Inventory Logic ──
                # Restock happens if inventory drops below threshold
                inv = inventory_tracker[key]
                if inv < 30 and delay_days == 0:
                    restock = random.randint(60, 150)
                    inv += restock
                elif inv < 15:  # Emergency even with delay
                    inv += random.randint(20, 40)
                
                # Sell from inventory
                actual_sold = min(units_sold, max(0, inv))
                inv -= actual_sold
                
                # Inventory shortage flag
                shortage = units_sold > inv + actual_sold
                
                inventory_tracker[key] = max(0, inv)
                
                # ── Revenue ──
                effective_price = product["base_price"]
                if is_promo:
                    effective_price *= random.uniform(0.80, 0.90)  # 10-20% discount
                revenue = round(actual_sold * effective_price, 2)
                
                # ── Build Row ──
                row = {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "store_id": store["id"],
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "category": product["category"],
                    "region": store["region"],
                    "inventory_level": inv,
                    "units_sold": actual_sold,
                    "revenue": revenue,
                    "price": round(effective_price, 2),
                    "promotion_flag": 1 if is_promo else 0,
                    "holiday_flag": 1 if near_hol else 0,
                    "competitor_price": comp_price,
                    "supplier_delay_days": delay_days,
                    "customer_rating": rating,
                }
                
                # Inject messiness
                for field in ["product_name", "category", "region", "units_sold", "revenue", "inventory_level", "customer_rating"]:
                    row[field] = inject_messiness(row[field], field, row_idx)
                
                rows.append(row)
                row_idx += 1
        
        current_date += timedelta(days=1)
    
    return rows

def main():
    print("Generating AURAChain test dataset...")
    rows = generate_dataset()
    
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "aurachain_retail_dataset.csv")
    
    fieldnames = [
        "date", "store_id", "product_id", "product_name", "category",
        "region", "inventory_level", "units_sold", "revenue", "price",
        "promotion_flag", "holiday_flag", "competitor_price",
        "supplier_delay_days", "customer_rating"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ Generated {len(rows):,} rows → {output_path}")
    print(f"   Date range: {rows[0]['date']} → {rows[-1]['date']}")
    print(f"   Stores: {len(STORES)}")
    print(f"   Products: {len(PRODUCTS)}")
    print(f"   File size: {os.path.getsize(output_path) / 1024 / 1024:.1f} MB")
    
    # Preview
    print("\n── First 10 rows ──")
    for r in rows[:10]:
        print(f"  {r['date']} | {r['store_id']} | {str(r['product_name'])[:25]:25s} | sold={r['units_sold']:>3} | inv={r['inventory_level']:>4} | rev={r['revenue']:>10} | promo={r['promotion_flag']} | holiday={r['holiday_flag']}")

if __name__ == "__main__":
    main()
