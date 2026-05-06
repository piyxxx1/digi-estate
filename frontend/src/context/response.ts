export async function getGeminiResponse(userMessage: string, history: { role: string, text: string }[]) {
  try {
    const response = await fetch("http://157.173.220.42/api/gemini/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_message: userMessage,
        history: history,
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend Error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.response;
  } catch (error) {
    console.error("Fetch Error:", error);
    throw error;
  }
}
