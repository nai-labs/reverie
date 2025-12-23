const API_BASE = '/api';

// State
const urlParams = new URLSearchParams(window.location.search);
let user = urlParams.get('user') || "User";
let character = urlParams.get('character') || "Anika";
let sessionPassword = null;

// Elements
const messagesDiv = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const genImageBtn = document.getElementById('gen-image-btn');
const genVideoBtn = document.getElementById('gen-video-btn');
const videoModelSelect = document.getElementById('video-model-select');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const backgroundLayer = document.getElementById('background-layer');

// Password Elements
const passwordModal = document.getElementById('password-modal');
const passwordInput = document.getElementById('remote-password');
const submitPasswordBtn = document.getElementById('submit-password-btn');

// Initialization
async function init() {
    try {
        // Check if we have URL params (Launcher)
        const urlParams = new URLSearchParams(window.location.search);
        const paramUser = urlParams.get('user');
        const paramChar = urlParams.get('character');

        if (paramUser && paramChar) {
            // We are the launcher/host, force init
            user = paramUser;
            character = paramChar;
            await initializeSession(user, character);
        } else {
            // We are a remote client, check for existing session
            try {
                const sessionResp = await fetch(`${API_BASE}/session`);
                const sessionData = await sessionResp.json();

                if (sessionData.character && sessionData.session_id) {
                    // Join existing session
                    user = sessionData.user;
                    character = sessionData.character;
                    console.log('Joining existing session:', sessionData);

                    if (sessionData.requires_password) {
                        passwordModal.classList.remove('hidden');
                    } else {
                        addSystemMessage(`Joined session with ${character}.`);
                        await loadHistory();
                    }
                } else {
                    // No active session, fallback to default init
                    console.log('No active session, initializing default.');
                    await initializeSession(user, character);
                }
            } catch (e) {
                console.error('Failed to check session:', e);
                await initializeSession(user, character);
            }
        }
    } catch (error) {
        console.error('Init failed:', error);
        addSystemMessage('Failed to connect to server.');
    }
}

async function authenticate() {
    const password = passwordInput.value;
    try {
        const response = await fetch(`${API_BASE}/auth`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });
        const data = await response.json();

        if (data.success) {
            sessionPassword = password;
            passwordModal.classList.add('hidden');
            addSystemMessage(`Joined session with ${character}.`);
            await loadHistory();
        } else {
            alert("Incorrect password");
        }
    } catch (e) {
        console.error("Auth failed:", e);
        alert("Authentication failed");
    }
}

async function loadHistory() {
    try {
        const headers = {};
        if (sessionPassword) {
            headers['X-Remote-Password'] = sessionPassword;
        }

        const response = await fetch(`${API_BASE}/history`, { headers });
        if (response.ok) {
            const data = await response.json();
            messagesDiv.innerHTML = ''; // Clear existing messages

            data.history.forEach(msg => {
                if (msg.role === 'user') {
                    addMessage(user, msg.content, 'user');
                } else if (msg.role === 'assistant') {
                    addMessage(character, msg.content, 'bot');
                } else if (msg.role === 'system') {
                    addSystemMessage(msg.content);
                }
            });
            scrollToBottom();
        }
    } catch (e) {
        console.error("Failed to load history:", e);
    }
}

async function initializeSession(user, character) {
    const response = await fetch(`${API_BASE}/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user, character })
    });
    const data = await response.json();
    console.log('Session initialized:', data);
    addSystemMessage(`Connected to ${character}.`);

    if (data.initial_message) {
        addMessage(character, data.initial_message, 'bot');
    }
}

// Chat Functions
async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    // UI Update
    addMessage(user, text, 'user');
    messageInput.value = '';

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const data = await response.json();

        // Bot Response
        addMessage(character, data.response, 'bot', data.tts_url);

    } catch (error) {
        console.error('Chat failed:', error);
        addSystemMessage('Error sending message.');
    }
}

function addMessage(sender, content, type, audioFile = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;

    // Format content (simple markdown-like)
    // Convert *italics* to <em>
    let formattedContent = content.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Convert newlines to <br>
    formattedContent = formattedContent.replace(/\n/g, '<br>');

    let html = `<div class="content">${formattedContent}</div>`;

    if (audioFile) {
        // Add audio player
        html += `
            <div class="audio-player">
                <audio controls autoplay>
                    <source src="${audioFile}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            </div>
        `;
    } else if (type === 'bot') {
        // Add generate audio button for bot messages
        const btnId = `tts-btn-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const safeText = encodeURIComponent(content).replace(/'/g, "%27");

        html += `
            <div class="message-actions">
                <button id="${btnId}" class="icon-btn" onclick="generateAudio('${btnId}', '${safeText}')" title="Generate Audio">
                    🔊
                </button>
            </div>
        `;
    }

    msgDiv.innerHTML = html;
    messagesDiv.appendChild(msgDiv);
    scrollToBottom();
}

async function generateAudio(btnId, encodedText) {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    const text = decodeURIComponent(encodedText);

    // Show loading state
    btn.innerHTML = '⏳';
    btn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/generate/tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) throw new Error('TTS generation failed');

        const data = await response.json();

        // Replace button with audio player
        const container = btn.parentElement;
        container.innerHTML = `
            <div class="audio-player">
                <audio controls autoplay>
                    <source src="${data.tts_url}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            </div>
        `;

    } catch (error) {
        console.error('TTS failed:', error);
        btn.innerHTML = '⚠️';
        btn.title = 'Failed to generate audio';
        setTimeout(() => {
            btn.innerHTML = '🔊';
            btn.disabled = false;
        }, 2000);
    }
}

function addSystemMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system';
    msgDiv.innerHTML = `<div class="content">${text}</div>`;
    messagesDiv.appendChild(msgDiv);
    scrollToBottom();
}

function addImage(url, prompt) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot';
    msgDiv.innerHTML = `
        <div class="content">
            <img src="${url}" alt="${prompt}" onclick="window.open('${url}', '_blank')">
        </div>
    `;
    messagesDiv.appendChild(msgDiv);
    scrollToBottom();

    // Update background
    backgroundLayer.style.backgroundImage = `url('${url}')`;
}

function addVideo(url, prompt) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot';
    msgDiv.innerHTML = `
        <div class="content">
            <video controls autoplay loop>
                <source src="${url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
    `;
    messagesDiv.appendChild(msgDiv);
    scrollToBottom();
}

function scrollToBottom() {
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Media Generation
async function generateImage() {
    addSystemMessage('Generating image...');
    try {
        const response = await fetch(`${API_BASE}/generate/image`, { method: 'POST' });
        if (!response.ok) throw new Error('Generation failed');
        const data = await response.json();
        addImage(data.image_url, data.prompt);
    } catch (error) {
        console.error('Image gen failed:', error);
        addSystemMessage('Failed to generate image.');
    }
}

async function generateVideo() {
    const model = videoModelSelect ? videoModelSelect.value : 'infinitetalk';
    const modelName = videoModelSelect ? videoModelSelect.options[videoModelSelect.selectedIndex].text : 'InfiniteTalk';

    addSystemMessage(`Generating video with ${modelName} (this may take a few minutes)...`);
    try {
        const response = await fetch(`${API_BASE}/generate/video/wavespeed?model=${model}`, { method: 'POST' });
        if (!response.ok) throw new Error('Generation failed');
        const data = await response.json();
        addVideo(data.video_url, data.prompt);
    } catch (error) {
        console.error('Video gen failed:', error);
        addSystemMessage('Failed to generate video. Ensure you have a recent image and audio.');
    }
}

// Settings
async function openSettings() {
    try {
        const response = await fetch(`${API_BASE}/settings`);
        const data = await response.json();

        document.getElementById('system-prompt').value = data.system_prompt;
        document.getElementById('image-prompt').value = data.image_prompt;
        document.getElementById('tts-url').value = data.tts_url;
        document.getElementById('read-narration').checked = data.read_narration;
        document.getElementById('pov-mode').checked = data.pov_mode;
        document.getElementById('first-person-mode').checked = data.first_person_mode;
        document.getElementById('sd-mode').value = data.sd_mode || 'xl';

        settingsModal.classList.remove('hidden');
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings() {
    const settings = {
        system_prompt: document.getElementById('system-prompt').value,
        image_prompt: document.getElementById('image-prompt').value,
        tts_url: document.getElementById('tts-url').value,
        read_narration: document.getElementById('read-narration').checked,
        pov_mode: document.getElementById('pov-mode').checked,
        first_person_mode: document.getElementById('first-person-mode').checked,
        sd_mode: document.getElementById('sd-mode').value
    };

    try {
        await fetch(`${API_BASE}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        settingsModal.classList.add('hidden');
        addSystemMessage('Settings saved.');
    } catch (error) {
        console.error('Failed to save settings:', error);
        addSystemMessage('Failed to save settings.');
    }
}

// Event Listeners
if (submitPasswordBtn) {
    submitPasswordBtn.addEventListener('click', authenticate);
}
if (passwordInput) {
    passwordInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') authenticate();
    });
}

if (sendBtn) sendBtn.addEventListener('click', sendMessage);
if (messageInput) {
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize
    messageInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value === '') {
            this.style.height = '24px'; // Reset to default
        }
    });
}

if (genImageBtn) genImageBtn.addEventListener('click', generateImage);
if (genVideoBtn) genVideoBtn.addEventListener('click', generateVideo);

if (settingsBtn) settingsBtn.addEventListener('click', openSettings);
if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
if (saveSettingsBtn) saveSettingsBtn.addEventListener('click', saveSettings);

// Start
document.addEventListener('DOMContentLoaded', init);
