import re
from typing import List, Dict, Any
import json

def extract_numbers_and_dates(text: str) -> List[str]:
    """
    Extracts numbers, percentages, and dates from raw text to verify against extracted structured data.
    """
    if not text:
        return []
        
    findings = []
    
    # Matches numbers (including formats like 75, 75.5, 75,000)
    number_pattern = r'\b\d+(?:,\d+)*(?:\.\d+)?\b'
    # Matches simple lakh/cr patterns like 75L, 7.5Cr
    amount_pattern = r'\b\d+(?:\.\d+)?\s*(?:L|Cr|Lakh|Crore|k|K)\b'
    # Percentages
    pct_pattern = r'\b\d+(?:\.\d+)?\s*%'
    
    # Find all matches
    for m in re.finditer(amount_pattern, text, re.IGNORECASE):
        findings.append(m.group(0))
        
    for m in re.finditer(pct_pattern, text):
        findings.append(m.group(0))
        
    for m in re.finditer(number_pattern, text):
        val = m.group(0)
        # Add if not already part of a found amount/pct
        if not any(val in f for f in findings):
            # Ignore small plain numbers (less than 100) as they are usually noisy (floors, mins, phases)
            try:
                num_val = float(val.replace(',', ''))
                if num_val < 100:
                    continue
            except ValueError:
                pass
            findings.append(val)
            
    return list(set(findings))

def verify_extracted_data(raw_text: str, facts: Dict[str, Any], unit_types: List[Dict[str, Any]], cleaned_text: str) -> List[str]:
    """
    Checks if extracted numbers/dates in raw_text appear in the structured output or cleaned narrative.
    Returns a list of missing items (warnings).
    """
    findings = extract_numbers_and_dates(raw_text)
    
    # Combine everything extracted into one large string for easy substring matching
    structured_content = json.dumps(facts) + " " + json.dumps(unit_types) + " " + str(cleaned_text)
    
    warnings = []
    
    # A simple verification: Normalize and check
    for item in findings:
        # Exact string match as a baseline (in reality, might need normalization like 75L -> 7500000)
        # For this requirement, we'll strip spaces and lowercase to match
        normalized_item = item.replace(" ", "").lower()
        normalized_content = structured_content.replace(" ", "").lower()
        
        if normalized_item not in normalized_content:
            # Maybe the number was converted (e.g. 75L -> 7500000)
            if item.lower().endswith('l') or item.lower().endswith('lakh'):
                try:
                    num_val = float(re.sub(r'[^\d.]', '', item))
                    expanded_val = str(int(num_val * 100000))
                    if expanded_val in normalized_content:
                        continue
                except:
                    pass
            elif item.lower().endswith('cr') or item.lower().endswith('crore'):
                try:
                    num_val = float(re.sub(r'[^\d.]', '', item))
                    expanded_val = str(int(num_val * 10000000))
                    if expanded_val in normalized_content:
                        continue
                except:
                    pass
            elif item.lower().endswith('k'):
                try:
                    num_val = float(re.sub(r'[^\d.]', '', item))
                    expanded_val = str(int(num_val * 1000))
                    if expanded_val in normalized_content:
                        continue
                except:
                    pass
                    
            warnings.append(f"Number/Value '{item}' from raw text was not found in extracted data.")
            
    return warnings
