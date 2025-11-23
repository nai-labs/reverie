const API_BASE = 'http://localhost:8000/api';

// State
let user = "User";
let character = "Anika";

// Elements
const messagesDiv = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const genImageBtn = document.getElementById('gen-image-btn');
const genVideoBtn = document.getElementById('gen-video-btn');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const backgroundLayer = document.getElementById('background-layer');

// Initialization
async function init() {
    try {
        const response = await fetch(`${API_BASE}/init`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user, character })
        });
        const data = await response.json();
        console.log('Session initialized:', data);
        addSystemMessage(`Connected to ${character}.`);
    } catch (error) {
        console.error('Init failed:', error);
        addSystemMessage('Failed to connect to server.');
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
        // We use a unique ID for the button to replace it later
        const btnId = `tts-btn-${Date.now()}`;
        // Store the text content in a data attribute (safe encoding)
        // encodeURIComponent doesn't escape single quotes, so we must do it manually to avoid breaking the onclick attribute
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
    addSystemMessage('Generating selfie...');
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
    addSystemMessage('Generating video (this may take a minute)...');
    try {
        const response = await fetch(`${API_BASE}/generate/video`, { method: 'POST' });
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

        settingsModal.classList.remove('hidden');
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings() {
    const settings = {
        system_prompt: document.getElementById('system-prompt').value,
        image_prompt: document.getElementById('image-prompt').value,
        tts_url: document.getElementById('tts-url').value
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
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

genImageBtn.addEventListener('click', generateImage);
genVideoBtn.addEventListener('click', generateVideo);

settingsBtn.addEventListener('click', openSettings);
closeSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
saveSettingsBtn.addEventListener('click', saveSettings);

// Start
init();
