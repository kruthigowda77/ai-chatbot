console.log("script.js v5 loaded (with typing indicator)");

// ===== Find the page elements we need (using the ids from index.html) =====
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const statusEl = document.getElementById("status");

// The streaming endpoint. A relative path works because FastAPI serves this page.
const API_URL = "/api/chat/stream";

// Give up if the server doesn't START replying within 60 seconds.
const REQUEST_TIMEOUT_MS = 60000;

// ===== Conversation memory =====
// Every successful exchange is stored here, oldest first.
// It lives in the browser's memory, so it resets when the page is refreshed.
const history = [];
const MAX_HISTORY_MESSAGES = 20; // must match the backend


// ===== Add a message bubble to the chat; returns the bubble element =====
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
    scrollToBottom();

    return bubble;
}


// ===== Typing indicator: a bot bubble containing three animated dots =====
function addTypingIndicator() {
    const bubble = addMessage("", "bot");

    const dots = document.createElement("div");
    dots.className = "typing-indicator";
    dots.setAttribute("role", "status");
    dots.setAttribute("aria-label", "AI is typing"); // read aloud by screen readers

    for (let i = 0; i < 3; i++) {
        dots.appendChild(document.createElement("span"));
    }

    bubble.appendChild(dots);
    scrollToBottom();
    return bubble;
}


// Remove a whole message (used to remove the typing bubble if an error happens)
function removeMessage(bubble) {
    bubble.parentElement.remove();
}


function setStatus(text) {
    statusEl.textContent = text;
}


function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}


// ===== Turn a failed response into a friendly message =====
async function getErrorMessage(response) {
    if (response.status === 422) {
        return "That message couldn't be sent. It may be too long or contain invalid data.";
    }

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


// ===== Send a message and stream the reply into a bubble =====
// Returns the complete reply text once streaming finishes.
async function streamMessage(text) {
    // Show the dots right away, before anything comes back
    const bubble = addTypingIndicator();
    setStatus("Typing...");

    try {
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
            removeMessage(bubble); // take the dots away before showing the error
            if (error.name === "AbortError") {
                throw new Error("The request took too long. Please try again.");
            }
            throw new Error("Can't reach the server. Please check that it's running and try again.");
        } finally {
            clearTimeout(timeoutId);
        }

        if (!response.ok) {
            removeMessage(bubble);
            throw new Error(await getErrorMessage(response));
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullReply = "";

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                fullReply += decoder.decode(value, { stream: true });

                // Setting textContent replaces everything inside the bubble,
                // so the first piece of text automatically removes the dots.
                bubble.textContent = fullReply;
                scrollToBottom();
            }
        } catch (error) {
            console.error("Stream reading error:", error);
            fullReply += "\n\n[The connection was interrupted.]";
            bubble.textContent = fullReply;
        }

        if (!fullReply.trim()) {
            bubble.textContent = "The AI returned an empty response. Please try again.";
            bubble.parentElement.classList.add("error");
            return null;
        }

        return fullReply;
    } finally {
        // Whatever happened (success or error), the bot is no longer typing
        setStatus("Online");
    }
}


// ===== Remember one exchange, keeping only the most recent messages =====
function rememberExchange(userText, botReply) {
    history.push({ role: "user", content: userText });
    history.push({ role: "assistant", content: botReply });

    while (history.length > MAX_HISTORY_MESSAGES) {
        history.shift();
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
        const reply = await streamMessage(text);
        if (reply) {
            rememberExchange(text, reply);
        }
    } catch (error) {
        console.error("Chat error:", error);
        addMessage(error.message, "bot", true);
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