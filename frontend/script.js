console.log("script.js v2 loaded (with memory)");
// ===== Find the page elements we need (using the ids from index.html) =====
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");

// The backend endpoint. A relative path works because FastAPI serves this page.
const API_URL = "/api/chat";

// ===== Conversation memory =====
// Every successful exchange is stored here, oldest first, like:
// [{ role: "user", content: "Hi" }, { role: "assistant", content: "Hello!" }, ...]
// It lives in the browser's memory, so it resets when the page is refreshed.
const history = [];
const MAX_HISTORY_MESSAGES = 20; // must match the backend


// ===== Add a message bubble to the chat =====
function addMessage(text, sender) {
    const messageEl = document.createElement("div");
    messageEl.className = `message ${sender}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text; // textContent (not innerHTML) keeps it safe

    messageEl.appendChild(bubble);
    messagesEl.appendChild(messageEl);

    messagesEl.scrollTop = messagesEl.scrollHeight;
}


// ===== Send a message (plus history) to the backend =====
async function sendMessage(text) {
    const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            message: text,
            history: history, // the conversation so far
        }),
    });

    if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`);
    }

    const data = await response.json();
    return data.reply;
}


// ===== Remember one exchange, keeping only the most recent messages =====
function rememberExchange(userText, botReply) {
    history.push({ role: "user", content: userText });
    history.push({ role: "assistant", content: botReply });

    // Drop the oldest messages if we're over the limit
    while (history.length > MAX_HISTORY_MESSAGES) {
        history.shift(); // removes the first (oldest) item
    }
}


// ===== What happens when the user clicks Send (or presses Enter) =====
form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (sendButton.disabled) return;

    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";
    resizeInput();

    sendButton.disabled = true;

    try {
        const reply = await sendMessage(text);
        addMessage(reply, "bot");

        // Only remember exchanges that succeeded, so failed messages
        // don't confuse the AI later.
        rememberExchange(text, reply);
    } catch (error) {
        console.error("Chat error:", error);
        addMessage("Sorry, something went wrong. Please try again.", "bot");
    } finally {
        sendButton.disabled = false;
        input.focus();
    }
});


// ===== Enter sends the message; Shift+Enter adds a new line =====
input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});


// ===== Grow the input box as the user types multiple lines =====
function resizeInput() {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
}
input.addEventListener("input", resizeInput);