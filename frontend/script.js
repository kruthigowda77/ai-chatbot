// ===== Find the page elements we need (using the ids from index.html) =====
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");

// The backend endpoint. A relative path works because FastAPI serves this page.
const API_URL = "/api/chat";


// ===== Add a message bubble to the chat =====
function addMessage(text, sender) {
    // Build: <div class="message user|bot"><div class="bubble">text</div></div>
    const messageEl = document.createElement("div");
    messageEl.className = `message ${sender}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text; // textContent (not innerHTML) keeps it safe

    messageEl.appendChild(bubble);
    messagesEl.appendChild(messageEl);

    // Scroll down so the newest message is visible
    messagesEl.scrollTop = messagesEl.scrollHeight;
}


// ===== Send a message to the backend and return the AI's reply =====
async function sendMessage(text) {
    const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
    });

    if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`);
    }

    const data = await response.json(); // e.g. { reply: "Hello!" }
    return data.reply;
}


// ===== What happens when the user clicks Send (or presses Enter) =====
form.addEventListener("submit", async (event) => {
    event.preventDefault(); // stop the browser from reloading the page

    if (sendButton.disabled) return; // a request is already in progress

    const text = input.value.trim();
    if (!text) return; // ignore empty messages

    // 1. Show the user's message and clear the input box
    addMessage(text, "user");
    input.value = "";
    resizeInput();

    // 2. Disable the button while waiting, to prevent double-sending
    sendButton.disabled = true;

    try {
        // 3. Ask the backend, then show the reply
        const reply = await sendMessage(text);
        addMessage(reply, "bot");
    } catch (error) {
        console.error("Chat error:", error);
        addMessage("Sorry, something went wrong. Please try again.", "bot");
    } finally {
        // 4. Re-enable the button whether it worked or failed
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