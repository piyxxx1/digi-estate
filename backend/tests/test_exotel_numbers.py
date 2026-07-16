import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

async def test_exotel():
    api_key = os.getenv("EXOTEL_API_KEY")
    api_token = os.getenv("EXOTEL_API_TOKEN")
    account_sid = os.getenv("EXOTEL_ACCOUNT_SID")
    subdomain = os.getenv("EXOTEL_SUBDOMAIN", "api.exotel.com")
    
    test_cases = [
        ("SG", "Landline"),
        ("SG", "Mobile"),
        ("IN", "Landline"),
        ("IN", "Mobile")
      ]
    
    output = []
    async with httpx.AsyncClient() as client:
        for country, num_type in test_cases:
            url = f"https://{api_key}:{api_token}@{subdomain}/v2_beta/Accounts/{account_sid}/AvailablePhoneNumbers/{country}/{num_type}"
            output.append(f"Requesting: GET {url.replace(api_key, 'API_KEY').replace(api_token, 'API_TOKEN')}")
            try:
                response = await client.get(url)
                output.append(f"Status Code: {response.status_code}")
                try:
                    data = response.json()
                    output.append(f"Response: {data}")
                except Exception as je:
                    output.append(f"Failed to parse JSON: {je}. Raw: {response.text[:500]}")
            except Exception as e:
                output.append(f"Error: {e}")
            output.append("-" * 50)
            
    with open("test_out_py.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    asyncio.run(test_exotel())
