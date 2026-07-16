import os
import httpx
from typing import Optional, Dict

class ExotelService:
    def __init__(self):
        self.api_key = os.getenv("EXOTEL_API_KEY")
        self.api_token = os.getenv("EXOTEL_API_TOKEN")
        self.account_sid = os.getenv("EXOTEL_ACCOUNT_SID", "your_sid_here") # Should be in .env too
        self.subdomain = os.getenv("EXOTEL_SUBDOMAIN", "api.exotel.com")
        
        self.base_url = f"https://{self.api_key}:{self.api_token}@{self.subdomain}/v1/Accounts/{self.account_sid}"

    async def make_call(self, from_number: str, to_number: str, callback_url: str) -> Dict:
        """
        Initiates a call using Exotel Click-to-Call API
        """
        url = f"{self.base_url}/Calls/connect.json"
        payload = {
            'From': from_number,
            'To': to_number,
            'CallerId': os.getenv("EXOTEL_CALLER_ID"),
            'StatusCallback': callback_url
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Exotel Call Error: {str(e)}")
            return {"error": str(e)}

    async def make_outbound_ai_call(self, lead_number: str, exophone: str, app_url: str) -> Dict:
        """
        Initiates an outbound call to a lead and connects them to the AI Flow (Exotel App)
        """
        url = f"{self.base_url}/Calls/connect.json"
        public_url = os.getenv("PUBLIC_URL", "")
        
        status_callback = ""
        if public_url:
            status_callback = f"{public_url.rstrip('/')}/ws/status-callback"

        payload = {
            'From': lead_number,
            'CallerId': exophone,
            'Url': app_url,
        }
        
        if status_callback:
            payload['StatusCallback'] = status_callback
        
        try:
            print("Calling:", lead_number)
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=payload)
                print("Exotel response:", response.status_code)
                print(response.text)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Exotel Outbound AI Call Error: {str(e)}")
            return {"error": str(e)}

    async def get_call_details(self, call_sid: str) -> Dict:
        url = f"{self.base_url}/Calls/{call_sid}.json"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Exotel Details Error: {str(e)}")
            return {"error": str(e)}

    async def get_all_calls(self, limit: int = 50) -> Dict:
        """
        Fetches all call history from Exotel account
        """
        url = f"{self.base_url}/Calls.json?Limit={limit}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                # Handle possible structures (Call array inside response)
                calls = data.get("Call", []) if isinstance(data, dict) else []
                if not calls and "Calls" in data:
                    calls = data["Calls"]
                    
                return {"calls": calls}
        except Exception as e:
            print(f"Exotel All Calls Error: {str(e)}")
            return {"error": str(e), "calls": []}

    async def get_calls_by_number(self, virtual_number: str, limit: int = 100) -> Dict:
        """
        Fetches Exotel call history filtered by a specific virtual (ExoPhone) number.
        Strips non-digits for comparison so formatting differences don't matter.
        """
        url = f"{self.base_url}/Calls.json?Limit={limit}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                calls = data.get("Call", []) if isinstance(data, dict) else []
                if not calls and "Calls" in data:
                    calls = data["Calls"]

                # Normalise: keep last 10 digits for comparison
                def last10(num: str) -> str:
                    digits = ''.join(c for c in (num or '') if c.isdigit())
                    return digits[-10:] if len(digits) >= 10 else digits

                target = last10(virtual_number)

                filtered = [
                    c for c in calls
                    if last10(c.get("To", "")) == target or 
                       last10(c.get("From", "")) == target or 
                       last10(c.get("PhoneNumber", "")) == target
                ]

                return {"calls": filtered}
        except Exception as e:
            print(f"Exotel Calls By Number Error: {str(e)}")
            return {"error": str(e), "calls": []}

    async def get_available_numbers(self, country: Optional[str] = None, number_type: Optional[str] = None) -> Dict:
        """
        Fetches owned ExoPhones (IncomingPhoneNumbers) from Exotel account
        """
        url = f"https://{self.api_key}:{self.api_token}@{self.subdomain}/v2_beta/Accounts/{self.account_sid}/IncomingPhoneNumbers"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return {"numbers": []}
                response.raise_for_status()
                data = response.json()
                
                numbers = []
                incoming_numbers = data.get("incoming_phone_numbers", [])
                print(f"[DEBUG] Exotel raw item keys: {list(incoming_numbers[0].keys()) if incoming_numbers else 'empty'}")
                print(f"[DEBUG] Exotel sample item: {incoming_numbers[0] if incoming_numbers else 'none'}")
                for item in incoming_numbers:
                    phone_number = item.get("phone_number")
                    if phone_number:
                        # Pass the full raw item from Exotel, only filling defaults for missing fields
                        number_dict = dict(item)
                        number_dict.setdefault("friendly_name", phone_number)
                        number_dict.setdefault("rental_price", "0.000000")
                        numbers.append(number_dict)
                return {"numbers": numbers}
        except Exception as e:
            logger.error(f"Failed to fetch available numbers from Exotel API: {str(e)}")
            return {"error": str(e)}
