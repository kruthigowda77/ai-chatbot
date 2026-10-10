console.log("script.js v8 loaded (sidebar)");

// ===== Find the page elements we need =====
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const statusEl = document.getElementById("status");
const newChatButton = document.getElementById("new-chat-button");
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const menuButton = document.getElementById("menu-button");
const conversationListEl = document.getElementById("conversation-list");
const conversationEmptyEl = document.getElementById("conversation-empty");

const CHAT_STREAM_URL = "/api/chat/stream";
const CONVERSATIONS_URL = "/api/conversations";
const REQUEST_TIMEOUT_MS = 60000;
const WELCOME_MESSAGE = "Hi! I'm your AI assistant. Ask me anything.";

// ===== Which conversation is open =====
// Messages live in the database; the browser only remembers the open chat's ID.
const STORAGE_KEY = "chatbot.conversationId";
let conversationId = null;
let conversations = []; // the latest list from the server, for the sidebar

function setConversationId(id) {
    conversationId = id;
    try {
        if (id) {
            localStorage.setItem(STORAGE_KEY, id);
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    } catch {
        // Storage can be blocked (e.g. private browsing); the app still works without it
    }
}

function getSavedConversationId() {
    try {
        return localStorage.getItem(STORAGE_KEY);
    } catch {
        return null;
    }
}

function isBusy() {
    return sendButton.disabled; // true while a reply is streaming
}


// ===== Markdown setup =====
const markdownReady = typeof marked !== "undefined" && typeof DOMPurify !== "undefined";

if (markdownReady) {
    marked.use({ gfm: true, breaks: true });
    DOMPurify.addHook("afterSanitizeAttributes", (node) => {
        if (node.tagName === "A") {
            node.setAttribute("target", "_blank");
            node.setAttribute("rel", "noopener noreferrer");
        }
    });
} else {
    console.warn("Markdown libraries not loaded - showing replies as plain text.");
}

function renderBotText(bubble, text) {
    if (markdownReady) {
        bubble.classList.add("markdown");
        bubble.innerHTML = DOMPurify.sanitize(marked.parse(text));
    } else {
        bubble.textContent = text;
    }
}

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


// ===== Building the chat on screen =====

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

function addBotMessage(text) {
    const bubble = addMessage("", "bot");
    renderBotText(bubble, text);
    addCopyButtons(bubble);
    return bubble;
}

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

function clearChat() {
    messagesEl.replaceChildren();
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
        // Not JSON
    }
    return `Something went wrong (error ${response.status}). Please try again.`;
}


// ===== Sidebar: open and close (on phones) =====

function openSidebar() {
    sidebar.classList.add("open");
    sidebarBackdrop.hidden = false;
    menuButton.setAttribute("aria-expanded", "true");
}

function closeSidebar() {
    sidebar.classList.remove("open");
    sidebarBackdrop.hidden = true;
    menuButton.setAttribute("aria-expanded", "false");
}


// ===== Sidebar: the conversation list =====

// "9:42 PM" for today, "9 Oct" for older days, shown in the user's local time
function formatDate(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }
    return date.toLocaleDateString([], { day: "numeric", month: "short" });
}

// Ask the server for the latest list, then redraw the sidebar
async function refreshConversationList() {
    try {
        const response = await fetch(CONVERSATIONS_URL);
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }
        conversations = await response.json();
        renderConversationList();
    } catch (error) {
        console.error("Couldn't load the conversation list:", error);
    }
}

function renderConversationList() {
    conversationListEl.replaceChildren();
    conversationEmptyEl.hidden = conversations.length > 0;

    for (const convo of conversations) {
        const item = document.createElement("li");
        item.className = "conversation-item";

        // The main clickable area: title and date
        const openButton = document.createElement("button");
        openButton.type = "button";
        openButton.className = "conversation-open";

        const title = document.createElement("span");
        title.className = "conversation-title";
        title.textContent = convo.title; // textContent: titles come from user input
        title.title = convo.title;       // full title appears on hover

        const date = document.createElement("span");
        date.className = "conversation-date";
        date.textContent = formatDate(convo.updated_at);

        openButton.append(title, date);
        openButton.addEventListener("click", () => switchConversation(convo.id));

        if (convo.id === conversationId) {
            item.classList.add("active");
            openButton.setAttribute("aria-current", "true");
        }

        // Rename button
        const renameButton = document.createElement("button");
        renameButton.type = "button";
        renameButton.className = "conversation-action";
        renameButton.textContent = "✎";
        renameButton.setAttribute("aria-label", `Rename "${convo.title}"`);
        renameButton.title = "Rename";
        renameButton.addEventListener("click", () => renameConversation(convo));

        // Delete button
        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "conversation-action";
        deleteButton.textContent = "🗑";
        deleteButton.setAttribute("aria-label", `Delete "${convo.title}"`);
        deleteButton.title = "Delete";
        deleteButton.addEventListener("click", () => deleteConversation(convo));

        item.append(openButton, renameButton, deleteButton);
        conversationListEl.appendChild(item);
    }
}


// ===== Opening, starting, renaming, and deleting chats =====

async function switchConversation(id) {
    if (isBusy()) return;
    closeSidebar();
    if (id === conversationId) return; // already open

    await loadConversation(id);
    renderConversationList(); // move the highlight to the newly opened chat
}

function startNewChat() {
    if (isBusy()) return;

    setConversationId(null); // the next message will create a new conversation
    clearChat();
    addBotMessage(WELCOME_MESSAGE);
    renderConversationList(); // no chat is highlighted now
    closeSidebar();
    input.focus();
}

async function loadConversation(id) {
    try {
        const response = await fetch(`${CONVERSATIONS_URL}/${encodeURIComponent(id)}`);

        if (response.status === 404) {
            setConversationId(null);
            return;
        }
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }

        const conversation = await response.json();

        clearChat();
        addBotMessage(WELCOME_MESSAGE);
        for (const msg of conversation.messages) {
            if (msg.role === "user") {
                addMessage(msg.content, "user");
            } else {
                addBotMessage(msg.content);
            }
        }
        setConversationId(conversation.id);
        scrollToBottom();
    } catch (error) {
        console.error("Failed to load conversation:", error);
        addMessage("Couldn't load that chat. Please try again.", "bot", true);
    }
}

async function renameConversation(convo) {
    const newTitle = prompt("Rename chat:", convo.title);
    if (newTitle === null) return; // the user pressed Cancel

    const title = newTitle.trim().slice(0, 200);
    if (!title || title === convo.title) return;

    try {
        const response = await fetch(`${CONVERSATIONS_URL}/${encodeURIComponent(convo.id)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
        });
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }
        await refreshConversationList();
    } catch (error) {
        alert(error.message);
    }
}

async function deleteConversation(convo) {
    if (isBusy()) return;
    if (!confirm(`Delete "${convo.title}"? This can't be undone.`)) return;

    try {
        const response = await fetch(`${CONVERSATIONS_URL}/${encodeURIComponent(convo.id)}`, {
            method: "DELETE",
        });
        // 404 means it was already gone, which is fine
        if (!response.ok && response.status !== 404) {
            throw new Error(await getErrorMessage(response));
        }

        if (convo.id === conversationId) {
            startNewChat(); // the open chat was deleted
        }
        await refreshConversationList();
    } catch (error) {
        alert(error.message);
    }
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
            response = await fetch(CHAT_STREAM_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text, conversation_id: conversationId }),
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
            if (response.status === 404) {
                setConversationId(null);
            }
            throw new Error(await getErrorMessage(response));
        }

        const returnedId = response.headers.get("X-Conversation-Id");
        if (returnedId) {
            setConversationId(returnedId);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullReply = "";

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                fullReply += decoder.decode(value, { stream: true });
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
            return;
        }

        addCopyButtons(bubble);
        scrollToBottom();
    } finally {
        setStatus("Online");
    }
}


// ===== Events =====

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (isBusy()) return;

    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";
    resizeInput();

    sendButton.disabled = true;
    newChatButton.disabled = true;

    try {
        await streamMessage(text);
    } catch (error) {
        console.error("Chat error:", error);
        addMessage(error.message, "bot", true);
    } finally {
        sendButton.disabled = false;
        newChatButton.disabled = false;
        input.focus();
        // A new chat may have been created, or this one moved to the top
        refreshConversationList();
    }
});

newChatButton.addEventListener("click", startNewChat);

menuButton.addEventListener("click", () => {
    if (sidebar.classList.contains("open")) {
        closeSidebar();
    } else {
        openSidebar();
    }
});

sidebarBackdrop.addEventListener("click", closeSidebar);

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeSidebar();
    }
});

input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});

function resizeInput() {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
}
input.addEventListener("input", resizeInput);


// ===== On page load =====
async function init() {
    const savedId = getSavedConversationId();
    if (savedId) {
        await loadConversation(savedId); // reopen the last chat first...
    }
    await refreshConversationList();     // ...so the sidebar can highlight it
}

init();