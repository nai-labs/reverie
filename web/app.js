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
const genImageDirectBtn = document.getElementById('gen-image-direct-btn');
const genVideoBtn = document.getElementById('gen-video-btn');
const videoModelSelect = document.getElementById('video-model-select');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const backgroundLayer = document.getElementById('background-layer');
const exportBtn = document.getElementById('export-btn');

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
    const imageModel = document.getElementById('image-model-select').value;
    addSystemMessage(`Generating image (${imageModel})...`);
    try {
        const response = await fetch(`${API_BASE}/generate/image?model=${imageModel}`, { method: 'POST' });
        if (!response.ok) throw new Error('Generation failed');
        const data = await response.json();
        addImage(data.image_url, data.prompt);
    } catch (error) {
        console.error('Image gen failed:', error);
        addSystemMessage('Failed to generate image.');
    }
}

async function generateImageDirect() {
    const imageModel = document.getElementById('image-model-select').value;
    addSystemMessage(`Generating image from direct prompt (${imageModel})...`);
    try {
        const response = await fetch(`${API_BASE}/generate/image/direct?model=${imageModel}`, { method: 'POST' });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Generation failed');
        }
        const data = await response.json();
        addImage(data.image_url, data.prompt);
    } catch (error) {
        console.error('Direct image gen failed:', error);
        addSystemMessage(`Failed: ${error.message}`);
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
        first_person_mode: document.getElementById('first-person-mode').checked
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
if (genImageDirectBtn) genImageDirectBtn.addEventListener('click', generateImageDirect);
if (genVideoBtn) genVideoBtn.addEventListener('click', generateVideo);

if (settingsBtn) settingsBtn.addEventListener('click', openSettings);
if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
if (saveSettingsBtn) saveSettingsBtn.addEventListener('click', saveSettings);

// LoRA Video Modal
const loraVideoBtn = document.getElementById('lora-video-btn');
const loraModal = document.getElementById('lora-modal');
const closeLoraBtn = document.getElementById('close-lora-btn');
const generateLoraBtn = document.getElementById('generate-lora-btn');
const loraPresetSelect = document.getElementById('lora-preset-select');
const customUrlGroup = document.getElementById('custom-url-group');

// LoRA Presets - loaded dynamically from server
let LORA_PRESETS = {};

// Load LoRA presets from server and populate dropdown
async function loadLoraPresets() {
    try {
        const response = await fetch(`${API_BASE}/lora-presets`);
        if (response.ok) {
            const data = await response.json();
            LORA_PRESETS = data.presets || {};
            populateLoraDropdown();
        }
    } catch (error) {
        console.error('Failed to load LoRA presets:', error);
    }
}

function populateLoraDropdown() {
    if (!loraPresetSelect) return;

    // Clear existing options except "custom"
    loraPresetSelect.innerHTML = '';

    // Add preset options
    for (const name of Object.keys(LORA_PRESETS)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        loraPresetSelect.appendChild(option);
    }

    // Add custom option at the end
    const customOption = document.createElement('option');
    customOption.value = 'custom';
    customOption.textContent = 'Custom URL...';
    loraPresetSelect.appendChild(customOption);

    // Restore saved preset if any
    const savedPreset = localStorage.getItem('lora_preset');
    if (savedPreset && (LORA_PRESETS[savedPreset] || savedPreset === 'custom')) {
        loraPresetSelect.value = savedPreset;
    }

    // Also populate second LoRA dropdown
    const loraPresetSelect2 = document.getElementById('lora-preset-select-2');
    if (loraPresetSelect2) {
        loraPresetSelect2.innerHTML = '';

        // Add "None" option first
        const noneOption = document.createElement('option');
        noneOption.value = 'none';
        noneOption.textContent = 'None';
        loraPresetSelect2.appendChild(noneOption);

        // Add preset options
        for (const name of Object.keys(LORA_PRESETS)) {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            loraPresetSelect2.appendChild(option);
        }

        // Add custom option
        const customOption2 = document.createElement('option');
        customOption2.value = 'custom';
        customOption2.textContent = 'Custom URL...';
        loraPresetSelect2.appendChild(customOption2);
    }
}

// Load presets on page load
loadLoraPresets();

// Handle preset selection - show/hide custom URL field and pre-fill prompt/scale
if (loraPresetSelect) {
    loraPresetSelect.addEventListener('change', () => {
        const presetValue = loraPresetSelect.value;
        const isCustom = presetValue === 'custom';

        if (customUrlGroup) {
            customUrlGroup.style.display = isCustom ? 'block' : 'none';
        }

        // Pre-fill prompt and scale from preset (if not custom)
        if (!isCustom && LORA_PRESETS[presetValue]) {
            const preset = LORA_PRESETS[presetValue];
            if (preset.prompt && loraPromptInput) {
                loraPromptInput.value = preset.prompt;
                localStorage.setItem('lora_prompt', preset.prompt);
            }
            const scaleInput = document.getElementById('lora-scale');
            if (scaleInput) {
                scaleInput.value = preset.scale;
            }
        }

        // Save preset choice
        localStorage.setItem('lora_preset', presetValue);
    });
}

// Save prompt on change
const loraPromptInput = document.getElementById('lora-prompt');
if (loraPromptInput) {
    loraPromptInput.addEventListener('input', () => {
        localStorage.setItem('lora_prompt', loraPromptInput.value);
    });
}

// Save custom URL on change
const loraUrlInput = document.getElementById('lora-url');
if (loraUrlInput) {
    loraUrlInput.addEventListener('input', () => {
        localStorage.setItem('lora_custom_url', loraUrlInput.value);
    });
}

// Handle second LoRA dropdown
const loraPresetSelect2 = document.getElementById('lora-preset-select-2');
const customUrlGroup2 = document.getElementById('custom-url-group-2');
const loraScale2Group = document.getElementById('lora-scale-2-group');

if (loraPresetSelect2) {
    loraPresetSelect2.addEventListener('change', () => {
        const presetValue = loraPresetSelect2.value;
        const isNone = presetValue === 'none';
        const isCustom = presetValue === 'custom';

        // Show/hide scale and custom URL fields
        if (loraScale2Group) {
            loraScale2Group.style.display = isNone ? 'none' : 'block';
        }
        if (customUrlGroup2) {
            customUrlGroup2.style.display = isCustom ? 'block' : 'none';
        }

        // Pre-fill scale from preset
        if (!isNone && !isCustom && LORA_PRESETS[presetValue]) {
            const scaleInput2 = document.getElementById('lora-scale-2');
            if (scaleInput2) {
                scaleInput2.value = LORA_PRESETS[presetValue].scale;
            }
        }
    });
}

// Restore saved values on modal open
if (loraVideoBtn) {
    loraVideoBtn.addEventListener('click', () => {
        // Restore saved values
        const savedPrompt = localStorage.getItem('lora_prompt');
        const savedPreset = localStorage.getItem('lora_preset');
        const savedCustomUrl = localStorage.getItem('lora_custom_url');

        if (savedPrompt && loraPromptInput) loraPromptInput.value = savedPrompt;
        if (savedPreset && loraPresetSelect) {
            loraPresetSelect.value = savedPreset;
            if (customUrlGroup) {
                customUrlGroup.style.display = savedPreset === 'custom' ? 'block' : 'none';
            }
        }
        if (savedCustomUrl && loraUrlInput) loraUrlInput.value = savedCustomUrl;

        loraModal.classList.remove('hidden');
    });
}

if (closeLoraBtn) closeLoraBtn.addEventListener('click', () => loraModal.classList.add('hidden'));
if (generateLoraBtn) generateLoraBtn.addEventListener('click', generateLoraVideo);

// Sync LoRAs to local button
const syncLorasBtn = document.getElementById('sync-loras-btn');
if (syncLorasBtn) syncLorasBtn.addEventListener('click', syncLorasToLocal);

async function syncLorasToLocal() {
    // Get all preset URLs
    const loraUrls = Object.entries(LORA_PRESETS).map(([name, preset]) => ({
        name: name,
        url: preset.url
    }));

    addSystemMessage(`Syncing ${loraUrls.length} LoRAs to local folder...`);
    loraModal.classList.add('hidden');

    try {
        const response = await fetch(`${API_BASE}/sync/loras`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ loras: loraUrls })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Sync failed');
        }

        const data = await response.json();
        addSystemMessage(`✅ Synced ${data.downloaded} LoRAs, ${data.skipped} already existed.`);
    } catch (error) {
        console.error('LoRA sync failed:', error);
        addSystemMessage(`Failed to sync: ${error.message}`);
    }
}

async function generateLoraVideo() {
    const wanModel = document.getElementById('wan-model-select').value;
    const prompt = document.getElementById('lora-prompt').value.trim();
    const presetValue = loraPresetSelect ? loraPresetSelect.value : 'custom';
    const loraScale = parseFloat(document.getElementById('lora-scale').value) || 1.0;
    const numFrames = parseInt(document.getElementById('lora-frames').value) || 81;
    const fps = parseInt(document.getElementById('lora-fps').value) || 16;

    // Get LoRA 1 URL from preset or custom input
    let loraUrl;
    if (presetValue === 'custom') {
        loraUrl = document.getElementById('lora-url').value.trim();
    } else {
        loraUrl = LORA_PRESETS[presetValue]?.url || '';
    }

    // Get LoRA 2 URL and scale (optional)
    const preset2Select = document.getElementById('lora-preset-select-2');
    const preset2Value = preset2Select ? preset2Select.value : 'none';
    let loraUrl2 = null;
    let loraScale2 = null;

    if (preset2Value !== 'none') {
        if (preset2Value === 'custom') {
            loraUrl2 = document.getElementById('lora-url-2')?.value.trim() || null;
        } else {
            loraUrl2 = LORA_PRESETS[preset2Value]?.url || null;
        }
        loraScale2 = parseFloat(document.getElementById('lora-scale-2')?.value) || 1.0;
    }

    if (!prompt) {
        alert('Please enter a prompt.');
        return;
    }
    if (!loraUrl) {
        alert('Please enter or select a LoRA URL.');
        return;
    }

    loraModal.classList.add('hidden');
    const modelName = wanModel === 'wan-2.2-fast' ? 'WAN 2.2 Fast' : 'WAN 2.1';
    const presetName = presetValue === 'custom' ? 'Custom' : presetValue;
    const lora2Info = loraUrl2 ? ` + ${preset2Value}` : '';
    addSystemMessage(`Generating LoRA video with ${modelName} + ${presetName}${lora2Info} (${numFrames} frames @ ${fps}fps)...`);

    try {
        const response = await fetch(`${API_BASE}/generate/video/lora`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                lora_url: loraUrl,
                lora_scale: loraScale,
                lora_url_2: loraUrl2,
                lora_scale_2: loraScale2,
                wan_model: wanModel,
                num_frames: numFrames,
                fps: fps
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'LoRA video generation failed');
        }

        const data = await response.json();
        addVideo(data.video_url, data.prompt);
        addSystemMessage('LoRA video generated successfully!');
    } catch (error) {
        console.error('LoRA video gen failed:', error);
        addSystemMessage(`Failed: ${error.message}`);
    }
}

if (exportBtn) {
    exportBtn.addEventListener('click', async () => {
        addSystemMessage('Preparing export...');
        try {
            const response = await fetch(`${API_BASE}/export`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Export failed');
            }

            // Get the filename from Content-Disposition header
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'reverie_export.zip';
            if (contentDisposition) {
                const match = contentDisposition.match(/filename=(.+)/);
                if (match) filename = match[1];
            }

            // Download the blob
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            addSystemMessage('Export complete! Check your downloads.');
        } catch (error) {
            console.error('Export failed:', error);
            addSystemMessage(`Failed to export: ${error.message}`);
        }
    });
}

// Start
document.addEventListener('DOMContentLoaded', init);
