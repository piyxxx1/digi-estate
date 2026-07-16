export async function getGeminiResponse(userMessage: string, history: { role: string, text: string }[]) {
  try {
    const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
    const response = await fetch(`${apiBase}/api/gemini/chat`, {
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

export async function sendAudioMessage(audioBlob: Blob, history: { role: string, text: string }[]) {
  try {
    const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.wav");
    formData.append("history", JSON.stringify(history));

    const response = await fetch(`${apiBase}/api/gemini/audio-chat`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Backend Error: ${response.statusText}`);
    }

    const data = await response.json();
    return data; // Returns { response: "bot response", transcript: "user speech" }
  } catch (error) {
    console.error("Audio Upload Error:", error);
    throw error;
  }
}
