console.log("script.js v3 loaded (with error handling)");

// ===== Find the page elements we need (using the ids from index.html) =====
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");

// The backend endpoint. A relative path works because FastAPI serves this page.
const API_URL = "/api/chat";

// Give up waiting for the server after 60 seconds.
const REQUEST_TIMEOUT_MS = 60000;

// ===== Conversation memory =====
// Every successful exchange is stored here, oldest first.
// It lives in the browser's memory, so it resets when the page is refreshed.
const history = [];
const MAX_HISTORY_MESSAGES = 20; // must match the backend


// ===== Add a message bubble to the chat =====
function addMessage(text, sender, isError = false) {
    const messageEl = document.createElement("div");
    messageEl.className = `message ${sender}`;
    if (isError) {
        messageEl.classList.add("error"); // styled red in style.css
    }

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text; // textContent (not innerHTML) keeps it safe

    messageEl.appendChild(bubble);
    messagesEl.appendChild(messageEl);

    messagesEl.scrollTop = messagesEl.scrollHeight;
}


// ===== Turn a failed response into a friendly message =====
async function getErrorMessage(response) {
    // 422 = the backend rejected the data (e.g. message too long)
    if (response.status === 422) {
        return "That message couldn't be sent. It may be too long or contain invalid data.";
    }

    // Our backend sends errors as { "detail": "friendly message" }
    try {
        const data = await response.json();
        if (typeof data.detail === "string") {
            return data.detail;
        }
    } catch {
        // The body wasn't JSON; fall through to the generic message
    }

    return `Something went wrong (error ${response.status}). Please try again.`;
}


// ===== Send a message (plus history) to the backend =====
async function sendMessage(text) {
    // AbortController lets us cancel the request if it takes too long
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    let response;
    try {
        response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, history: history }),
            signal: controller.signal,
        });
    } catch (error) {
        // fetch itself failed: no response at all
        if (error.name === "AbortError") {
            throw new Error("The request took too long. Please try again.");
        }
        throw new Error("Can't reach the server. Please check that it's running and try again.");
    } finally {
        clearTimeout(timeoutId); // stop the timer either way
    }

    if (!response.ok) {
        throw new Error(await getErrorMessage(response));
    }

    const data = await response.json();
    return data.reply;
}


// ===== Remember one exchange, keeping only the most recent messages =====
function rememberExchange(userText, botReply) {
    history.push({ role: "user", content: userText });
    history.push({ role: "assistant", content: botReply });

    while (history.length > MAX_HISTORY_MESSAGES) {
        history.shift(); // removes the oldest item
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
        rememberExchange(text, reply); // only successful exchanges are remembered
    } catch (error) {
        console.error("Chat error:", error);
        addMessage(error.message, "bot", true); // show the specific, friendly message
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