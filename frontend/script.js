console.log("script.js v6 loaded (with markdown)");

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
const history = [];
const MAX_HISTORY_MESSAGES = 20; // must match the backend


// ===== Markdown setup =====
// marked and DOMPurify are loaded from a CDN in index.html.
// If they failed to load (e.g. no internet), we fall back to plain text.
const markdownReady = typeof marked !== "undefined" && typeof DOMPurify !== "undefined";

if (markdownReady) {
    // gfm: GitHub-style Markdown (tables etc.); breaks: single newlines become line breaks
    marked.use({ gfm: true, breaks: true });

    // After sanitizing, make every link open in a new tab, safely.
    DOMPurify.addHook("afterSanitizeAttributes", (node) => {
        if (node.tagName === "A") {
            node.setAttribute("target", "_blank");
            node.setAttribute("rel", "noopener noreferrer");
        }
    });
} else {
    console.warn("Markdown libraries not loaded - showing replies as plain text.");
}


// Show bot text in a bubble: as safe formatted HTML if possible, otherwise plain text.
function renderBotText(bubble, text) {
    if (markdownReady) {
        bubble.classList.add("markdown");
        const unsafeHtml = marked.parse(text);           // Markdown -> HTML
        bubble.innerHTML = DOMPurify.sanitize(unsafeHtml); // remove anything dangerous
    } else {
        bubble.textContent = text;
    }
}


// Add a "Copy" button to every code block inside a bubble.
function addCopyButtons(bubble) {
    bubble.querySelectorAll("pre").forEach((pre) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "copy-button";
        button.textContent = "Copy";

        button.addEventListener("click", async () => {
            const code = pre.querySelector("code");
            const textToCopy = code ? code.innerText : pre.innerText;
            try {
                await navigator.clipboard.writeText(textToCopy);
                button.textContent = "Copied!";
            } catch {
                button.textContent = "Failed";
            }
            setTimeout(() => (button.textContent = "Copy"), 1500);
        });

        pre.appendChild(button);
    });
}


// ===== Add a message bubble to the chat; returns the bubble element =====
// Used for user messages and errors: always plain text (textContent).
function addMessage(text, sender, isError = false) {
    const messageEl = document.createElement("div");
    messageEl.className = `message ${sender}`;
    if (isError) {
        messageEl.classList.add("error");
    }

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;

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
    dots.setAttribute("aria-label", "AI is typing");

    for (let i = 0; i < 3; i++) {
        dots.appendChild(document.createElement("span"));
    }

    bubble.appendChild(dots);
    scrollToBottom();
    return bubble;
}


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
async function streamMessage(text) {
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
            removeMessage(bubble);
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

                // Re-render the whole reply so far as formatted Markdown.
                // (This also replaces the typing dots on the first piece.)
                renderBotText(bubble, fullReply);
                scrollToBottom();
            }
        } catch (error) {
            console.error("Stream reading error:", error);
            fullReply += "\n\n[The connection was interrupted.]";
            renderBotText(bubble, fullReply);
        }

        if (!fullReply.trim()) {
            bubble.textContent = "The AI returned an empty response. Please try again.";
            bubble.parentElement.classList.add("error");
            return null;
        }

        // Streaming is finished: now it's safe to add Copy buttons.
        // (Adding them earlier would be wiped out by the next re-render.)
        addCopyButtons(bubble);
        scrollToBottom();

        return fullReply;
    } finally {
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