console.log("script.js v11 loaded (documents)");

// ===== Page elements =====

// Login screen
const authScreen = document.getElementById("auth-screen");
const authForm = document.getElementById("auth-form");
const authTitle = document.getElementById("auth-title");
const authSubtitle = document.getElementById("auth-subtitle");
const authUsername = document.getElementById("auth-username");
const authPassword = document.getElementById("auth-password");
const authError = document.getElementById("auth-error");
const authSubmit = document.getElementById("auth-submit");
const authSwitchText = document.getElementById("auth-switch-text");
const authSwitchButton = document.getElementById("auth-switch-button");

// Chat app
const chatApp = document.getElementById("chat-app");
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const statusEl = document.getElementById("status");
const botNameEl = document.getElementById("bot-name");
const botAvatarEl = document.getElementById("bot-avatar");
const newChatButton = document.getElementById("new-chat-button");
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const menuButton = document.getElementById("menu-button");
const conversationListEl = document.getElementById("conversation-list");
const conversationEmptyEl = document.getElementById("conversation-empty");
const userNameEl = document.getElementById("user-name");
const logoutButton = document.getElementById("logout-button");

// Documents (Step 21)
const uploadButton = document.getElementById("upload-button");
const fileInput = document.getElementById("file-input");
const uploadStatusEl = document.getElementById("upload-status");
const documentListEl = document.getElementById("document-list");
const documentEmptyEl = document.getElementById("document-empty");
const docsToggle = document.getElementById("docs-toggle");

// ===== Addresses and settings =====
const REGISTER_URL = "/api/auth/register";
const LOGIN_URL = "/api/auth/login";
const ME_URL = "/api/auth/me";
const CHAT_STREAM_URL = "/api/chat/stream";
const PERSONALITIES_URL = "/api/chat/personalities";
const CONVERSATIONS_URL = "/api/conversations";
const DOCUMENTS_URL = "/api/documents";
const MAX_UPLOAD_MB = 10; // must match the backend
const REQUEST_TIMEOUT_MS = 60000;
const WELCOME_MESSAGE = "Hi! I'm your AI assistant. Ask me anything.";
const DEFAULT_PERSONALITY = "assistant";

const TOKEN_KEY = "chatbot.token";
const CONVERSATION_KEY = "chatbot.conversationId";
const USE_DOCUMENTS_KEY = "chatbot.useDocuments";


// ===== Browser storage (wrapped in try/catch: it can be blocked) =====

function storageGet(key) {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

function storageSet(key, value) {
    try {
        if (value === null || value === undefined) {
            localStorage.removeItem(key);
        } else {
            localStorage.setItem(key, value);
        }
    } catch {
        // The app still works without storage; you just won't stay logged in
    }
}


// ===== App state =====
let authToken = storageGet(TOKEN_KEY);
let authMode = "login";
let conversationId = null;        // the open chat
let conversations = [];           // the sidebar list
let personalities = [];           // the available personalities, from the server
let selectedPersonality = DEFAULT_PERSONALITY; // chosen for the next NEW chat
let currentPersonality = DEFAULT_PERSONALITY;  // the open chat's personality
let userDocuments = [];           // the user's uploaded documents, from the server
let useDocuments = storageGet(USE_DOCUMENTS_KEY) === "true"; // the toggle above the input

function setConversationId(id) {
    conversationId = id;
    storageSet(CONVERSATION_KEY, id);
}

function isBusy() {
    return sendButton.disabled;
}


// ===== Talking to the API while logged in =====
async function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (authToken) {
        headers.Authorization = `Bearer ${authToken}`;
    }

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401 && authToken) {
        logout("Your session has expired. Please log in again.");
        const error = new Error("Please log in again.");
        error.authError = true;
        throw error;
    }

    return response;
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


// ===== Personalities =====

function findPersonality(id) {
    return personalities.find((p) => p.id === id);
}

function setHeader(personalityId) {
    const personality = findPersonality(personalityId);
    botNameEl.textContent = personality ? personality.name : "AI Assistant";
    botAvatarEl.textContent = personality ? personality.emoji : "🤖";
}

async function loadPersonalities() {
    try {
        const response = await apiFetch(PERSONALITIES_URL);
        if (response.ok) {
            personalities = await response.json();
        }
    } catch (error) {
        if (!error.authError) {
            console.error("Couldn't load personalities:", error);
        }
    }
}

function addPersonalityPicker() {
    const picker = document.createElement("div");
    picker.className = "persona-picker";
    picker.setAttribute("role", "group");
    picker.setAttribute("aria-label", "Choose who you want to chat with");

    for (const personality of personalities) {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "persona-option";
        option.dataset.id = personality.id;
        option.setAttribute("aria-pressed", String(personality.id === selectedPersonality));

        const emoji = document.createElement("span");
        emoji.className = "persona-emoji";
        emoji.textContent = personality.emoji;

        const text = document.createElement("span");
        const name = document.createElement("span");
        name.className = "persona-name";
        name.textContent = personality.name;
        const description = document.createElement("span");
        description.className = "persona-description";
        description.textContent = personality.description;
        text.append(name, description);

        option.append(emoji, text);
        option.addEventListener("click", () => selectPersonality(personality.id));
        picker.appendChild(option);
    }

    messagesEl.appendChild(picker);
}

function selectPersonality(id) {
    selectedPersonality = id;
    for (const option of messagesEl.querySelectorAll(".persona-option")) {
        option.setAttribute("aria-pressed", String(option.dataset.id === id));
    }
    setHeader(id);
    input.focus();
}

function removePersonalityPicker() {
    messagesEl.querySelector(".persona-picker")?.remove();
}


// ===== Documents (Step 21) =====

function setUseDocuments(on) {
    useDocuments = on;
    docsToggle.setAttribute("aria-pressed", String(on));
    storageSet(USE_DOCUMENTS_KEY, String(on));
}

function showUploadStatus(message, isError = false) {
    uploadStatusEl.textContent = message || "";
    uploadStatusEl.hidden = !message;
    uploadStatusEl.classList.toggle("error", isError);
}

async function refreshDocumentList() {
    if (!authToken) return;
    try {
        const response = await apiFetch(DOCUMENTS_URL);
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }
        userDocuments = await response.json();
        renderDocumentList();
    } catch (error) {
        if (!error.authError) {
            console.error("Couldn't load documents:", error);
        }
    }
}

function renderDocumentList() {
    documentListEl.replaceChildren();
    documentEmptyEl.hidden = userDocuments.length > 0;

    for (const doc of userDocuments) {
        const item = document.createElement("li");
        item.className = "document-item";

        const info = document.createElement("div");
        info.className = "document-info";

        const name = document.createElement("span");
        name.className = "document-name";
        name.textContent = "📄 " + doc.filename; // textContent: filenames come from users
        name.title = doc.filename;

        const meta = document.createElement("span");
        meta.className = "document-meta";
        const pages = doc.num_pages === 1 ? "1 page" : `${doc.num_pages} pages`;
        meta.textContent = `${pages} · ${formatDate(doc.created_at)}`;

        info.append(name, meta);

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "conversation-action";
        deleteButton.textContent = "🗑";
        deleteButton.title = "Delete";
        deleteButton.setAttribute("aria-label", `Delete "${doc.filename}"`);
        deleteButton.addEventListener("click", () => deleteDocument(doc));

        item.append(info, deleteButton);
        documentListEl.appendChild(item);
    }
}

async function uploadDocument(file) {
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
        showUploadStatus(`That file is too large. The limit is ${MAX_UPLOAD_MB} MB.`, true);
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    uploadButton.disabled = true;
    showUploadStatus(`Reading "${file.name}"... this can take a few seconds.`);

    try {
        // No Content-Type header here: the browser sets the right one for FormData
        const response = await apiFetch(DOCUMENTS_URL, { method: "POST", body: formData });
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }
        const doc = await response.json();
        showUploadStatus(`✅ Added "${doc.filename}" (${doc.num_chunks} sections).`);
        setUseDocuments(true); // they probably want to ask about it now
        await refreshDocumentList();
    } catch (error) {
        if (error.authError) return;
        const message = error instanceof TypeError
            ? "Can't reach the server. Please check that it's running."
            : error.message;
        showUploadStatus(message, true);
    } finally {
        uploadButton.disabled = false;
        fileInput.value = ""; // allow choosing the same file again
    }
}

async function deleteDocument(doc) {
    if (!confirm(`Delete "${doc.filename}"? The bot won't be able to use it anymore.`)) return;

    try {
        const response = await apiFetch(`${DOCUMENTS_URL}/${encodeURIComponent(doc.id)}`, {
            method: "DELETE",
        });
        if (!response.ok && response.status !== 404) {
            throw new Error(await getErrorMessage(response));
        }
        showUploadStatus(null);
        await refreshDocumentList();
    } catch (error) {
        if (!error.authError) {
            alert(error.message);
        }
    }
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

function showWelcome() {
    messagesEl.replaceChildren();
    addBotMessage(WELCOME_MESSAGE);

    if (conversationId) {
        setHeader(currentPersonality);
    } else {
        if (personalities.length > 0) {
            addPersonalityPicker();
        }
        setHeader(selectedPersonality);
    }
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


// ===== Login and sign-up =====

function setAuthMode(mode) {
    authMode = mode;
    const isLogin = mode === "login";

    authTitle.textContent = isLogin ? "Welcome back" : "Create your account";
    authSubtitle.textContent = isLogin
        ? "Log in to continue your chats."
        : "Sign up to save your chats.";
    authSubmit.textContent = isLogin ? "Log in" : "Create account";
    authSwitchText.textContent = isLogin ? "New here?" : "Already have an account?";
    authSwitchButton.textContent = isLogin ? "Create an account" : "Log in";
    authPassword.autocomplete = isLogin ? "current-password" : "new-password";

    showAuthError(null);
}

function showAuthError(message) {
    authError.textContent = message || "";
    authError.hidden = !message;
}

function showAuthScreen(message) {
    chatApp.hidden = true;
    authScreen.hidden = false;
    setAuthMode("login");
    if (message) {
        showAuthError(message);
    }
    authUsername.focus();
}

function validateAuthInput(username, password) {
    if (!/^[A-Za-z0-9_.-]{3,30}$/.test(username)) {
        return "Usernames are 3-30 characters: letters, numbers, and _ . - only.";
    }
    if (password.length < 8) {
        return "Passwords must be at least 8 characters.";
    }
    return null;
}

async function handleAuthSubmit(event) {
    event.preventDefault();

    const username = authUsername.value.trim();
    const password = authPassword.value;

    const problem = validateAuthInput(username, password);
    if (problem) {
        showAuthError(problem);
        return;
    }

    authSubmit.disabled = true;
    showAuthError(null);

    try {
        const response = await fetch(authMode === "login" ? LOGIN_URL : REGISTER_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });

        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }

        const data = await response.json();
        authToken = data.access_token;
        storageSet(TOKEN_KEY, authToken);
        authForm.reset();

        await enterChat(data.username);
    } catch (error) {
        const message = error instanceof TypeError
            ? "Can't reach the server. Please check that it's running."
            : error.message;
        showAuthError(message);
    } finally {
        authSubmit.disabled = false;
    }
}

async function enterChat(username) {
    userNameEl.textContent = username;
    authScreen.hidden = true;
    chatApp.hidden = false;

    await loadPersonalities();
    showWelcome();

    const savedId = storageGet(CONVERSATION_KEY);
    if (savedId) {
        await loadConversation(savedId);
    }
    await refreshConversationList();
    await refreshDocumentList();
    input.focus();
}

function logout(message) {
    authToken = null;
    storageSet(TOKEN_KEY, null);
    setConversationId(null);

    conversations = [];
    userDocuments = [];
    renderDocumentList();
    showUploadStatus(null);
    selectedPersonality = DEFAULT_PERSONALITY;
    currentPersonality = DEFAULT_PERSONALITY;
    renderConversationList();
    showWelcome();
    userNameEl.textContent = "";
    closeSidebar();

    showAuthScreen(message);
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

function formatDate(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }
    return date.toLocaleDateString([], { day: "numeric", month: "short" });
}

async function refreshConversationList() {
    if (!authToken) return;
    try {
        const response = await apiFetch(CONVERSATIONS_URL);
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }
        conversations = await response.json();
        renderConversationList();
    } catch (error) {
        if (!error.authError) {
            console.error("Couldn't load the conversation list:", error);
        }
    }
}

function renderConversationList() {
    conversationListEl.replaceChildren();
    conversationEmptyEl.hidden = conversations.length > 0;

    for (const convo of conversations) {
        const item = document.createElement("li");
        item.className = "conversation-item";

        const openButton = document.createElement("button");
        openButton.type = "button";
        openButton.className = "conversation-open";

        const personality = findPersonality(convo.personality);
        const title = document.createElement("span");
        title.className = "conversation-title";
        title.textContent = `${personality ? personality.emoji : "💬"} ${convo.title}`;
        title.title = convo.title;

        const date = document.createElement("span");
        date.className = "conversation-date";
        date.textContent = formatDate(convo.updated_at);

        openButton.append(title, date);
        openButton.addEventListener("click", () => switchConversation(convo.id));

        if (convo.id === conversationId) {
            item.classList.add("active");
            openButton.setAttribute("aria-current", "true");
        }

        const renameButton = document.createElement("button");
        renameButton.type = "button";
        renameButton.className = "conversation-action";
        renameButton.textContent = "✎";
        renameButton.setAttribute("aria-label", `Rename "${convo.title}"`);
        renameButton.title = "Rename";
        renameButton.addEventListener("click", () => renameConversation(convo));

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
    if (id === conversationId) return;

    await loadConversation(id);
    renderConversationList();
}

function startNewChat() {
    if (isBusy()) return;

    setConversationId(null);
    selectedPersonality = DEFAULT_PERSONALITY;
    showWelcome();
    renderConversationList();
    closeSidebar();
    input.focus();
}

async function loadConversation(id) {
    try {
        const response = await apiFetch(`${CONVERSATIONS_URL}/${encodeURIComponent(id)}`);

        if (response.status === 404) {
            setConversationId(null);
            return;
        }
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }

        const conversation = await response.json();

        setConversationId(conversation.id);
        currentPersonality = conversation.personality;

        showWelcome();
        for (const msg of conversation.messages) {
            if (msg.role === "user") {
                addMessage(msg.content, "user");
            } else {
                addBotMessage(msg.content);
            }
        }
        scrollToBottom();
    } catch (error) {
        if (error.authError) return;
        console.error("Failed to load conversation:", error);
        addMessage("Couldn't load that chat. Please try again.", "bot", true);
    }
}

async function renameConversation(convo) {
    const newTitle = prompt("Rename chat:", convo.title);
    if (newTitle === null) return;

    const title = newTitle.trim().slice(0, 200);
    if (!title || title === convo.title) return;

    try {
        const response = await apiFetch(`${CONVERSATIONS_URL}/${encodeURIComponent(convo.id)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
        });
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }
        await refreshConversationList();
    } catch (error) {
        if (!error.authError) {
            alert(error.message);
        }
    }
}

async function deleteConversation(convo) {
    if (isBusy()) return;
    if (!confirm(`Delete "${convo.title}"? This can't be undone.`)) return;

    try {
        const response = await apiFetch(`${CONVERSATIONS_URL}/${encodeURIComponent(convo.id)}`, {
            method: "DELETE",
        });
        if (!response.ok && response.status !== 404) {
            throw new Error(await getErrorMessage(response));
        }

        if (convo.id === conversationId) {
            startNewChat();
        }
        await refreshConversationList();
    } catch (error) {
        if (!error.authError) {
            alert(error.message);
        }
    }
}


// ===== Send a message and stream the reply into a bubble =====
async function streamMessage(text) {
    const bubble = addTypingIndicator();
    setStatus("Typing...");

    const isNewChat = !conversationId;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

        let response;
        try {
            response = await apiFetch(CHAT_STREAM_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId,
                    personality: isNewChat ? selectedPersonality : null,
                    use_documents: useDocuments,
                }),
                signal: controller.signal,
            });
        } catch (error) {
            removeMessage(bubble);
            if (error.authError) throw error;
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
            if (isNewChat) {
                currentPersonality = selectedPersonality;
            }
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

authForm.addEventListener("submit", handleAuthSubmit);

authSwitchButton.addEventListener("click", () => {
    setAuthMode(authMode === "login" ? "register" : "login");
    authUsername.focus();
});

logoutButton.addEventListener("click", () => {
    if (isBusy()) return;
    logout();
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (isBusy()) return;

    const text = input.value.trim();
    if (!text) return;

    removePersonalityPicker();
    addMessage(text, "user");
    input.value = "";
    resizeInput();

    sendButton.disabled = true;
    newChatButton.disabled = true;

    try {
        await streamMessage(text);
    } catch (error) {
        if (!error.authError) {
            console.error("Chat error:", error);
            addMessage(error.message, "bot", true);
        }
    } finally {
        sendButton.disabled = false;
        newChatButton.disabled = false;
        if (authToken) {
            input.focus();
            refreshConversationList();
        }
    }
});

newChatButton.addEventListener("click", startNewChat);

uploadButton.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) {
        uploadDocument(file);
    }
});

docsToggle.addEventListener("click", () => setUseDocuments(!useDocuments));

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


// ===== On page load: are we already logged in? =====
async function init() {
    setUseDocuments(useDocuments); // show the saved toggle state

    if (!authToken) {
        showAuthScreen();
        return;
    }

    try {
        const response = await apiFetch(ME_URL);
        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }
        const user = await response.json();
        await enterChat(user.username);
    } catch (error) {
        if (!error.authError) {
            showAuthScreen("Couldn't connect to the server. Please try again.");
        }
    }
}

init();