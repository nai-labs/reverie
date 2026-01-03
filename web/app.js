const API_BASE = '/api';

// State
const urlParams = new URLSearchParams(window.location.search);
let user = urlParams.get('user') || "User";
let character = urlParams.get('character') || "Anika";
let resumeSessionParam = urlParams.get('resume') || null;  // Optional session to resume
let sessionPassword = null;

// Scene Queue State (persisted to localStorage)
let sceneQueue = [];  // Array of {url, type, timestamp}
const SCENE_QUEUE_STORAGE_KEY = 'reverie_scene_queue';

// Load scene queue from localStorage
function loadSceneQueueFromStorage() {
    try {
        const stored = localStorage.getItem(SCENE_QUEUE_STORAGE_KEY);
        if (stored) {
            sceneQueue = JSON.parse(stored);
            console.log(`[SceneQueue] Restored ${sceneQueue.length} items from localStorage`);
        }
    } catch (e) {
        console.error('[SceneQueue] Failed to load from localStorage:', e);
        sceneQueue = [];
    }
}

// Save scene queue to localStorage
function saveSceneQueueToStorage() {
    try {
        localStorage.setItem(SCENE_QUEUE_STORAGE_KEY, JSON.stringify(sceneQueue));
    } catch (e) {
        console.error('[SceneQueue] Failed to save to localStorage:', e);
    }
}

// Load immediately on script init
loadSceneQueueFromStorage();

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

// Scene Queue Elements
const sceneQueuePanel = document.getElementById('scene-queue-panel');
const sceneQueueContainer = document.getElementById('scene-queue-container');
const sceneCountBadge = document.getElementById('scene-count-badge');
const compileStoryBtn = document.getElementById('compile-story-btn');
const clearQueueBtn = document.getElementById('clear-queue-btn');

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
        const paramResume = urlParams.get('resume');

        if (paramUser && paramChar) {
            // We are the launcher/host, force init
            user = paramUser;
            character = paramChar;
            await initializeSession(user, character, paramResume);
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

    // Restore scene queue UI if there are saved items
    if (sceneQueue.length > 0) {
        renderSceneQueue();
        showSceneQueuePanel();
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

                    // Display attached media
                    if (msg.media && msg.media.length > 0) {
                        msg.media.forEach(media => {
                            if (media.type === 'image') {
                                addImage(media.url, 'Restored image');
                            } else if (media.type === 'audio') {
                                addAudio(media.url);
                            } else if (media.type === 'video') {
                                addVideo(media.url, 'Restored video');
                            }
                        });
                    }
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

async function initializeSession(user, character, resumeSessionId = null) {
    const body = { user, character };
    if (resumeSessionId) {
        body.resume_session = resumeSessionId;
    }

    const response = await fetch(`${API_BASE}/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const data = await response.json();
    console.log('Session initialized:', data);

    if (data.resumed) {
        addSystemMessage(`Resumed session with ${character}.`);
        await loadHistory();
    } else {
        addSystemMessage(`Connected to ${character}.`);
        if (data.initial_message) {
            addMessage(character, data.initial_message, 'bot');
        }
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
    const imageId = `image-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    // Escape single quotes in URL and prompt for onclick handlers
    const escapedUrl = url.replace(/'/g, "\\'");
    const escapedPrompt = (prompt || '').replace(/'/g, "\\'");
    msgDiv.innerHTML = `
        <div class="content">
            <img id="${imageId}" src="${url}" alt="${prompt || ''}" onclick="window.open('${escapedUrl}', '_blank')">
            <div class="image-actions">
                <button class="add-to-story-btn" onclick="addToSceneQueue('${escapedUrl}', 'image', '${imageId}', this, 'image')">
                    ➕ Story
                </button>
                <button class="edit-image-btn" onclick="openEditModal('${escapedUrl}')">
                    ✏️ Edit
                </button>
                <button class="faceswap-btn" onclick="applyFaceswap('${escapedUrl}', this)">
                    🔄 Face
                </button>
            </div>
        </div>
    `;
    messagesDiv.appendChild(msgDiv);
    scrollToBottom();

    // Update background
    backgroundLayer.style.backgroundImage = `url('${url}')`;
}

function addVideo(url, prompt, type = 'video') {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot';
    const videoId = `video-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    msgDiv.innerHTML = `
        <div class="content">
            <video id="${videoId}" controls autoplay loop>
                <source src="${url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
            <div class="video-actions">
                <button class="add-to-story-btn" onclick="addToSceneQueue('${url}', '${type}', '${videoId}', this, 'video')">
                    ➕ Add to Story
                </button>
                <button class="add-to-story-btn" onclick="extractLastFrame('${url}')">
                    📷 Use Last Frame
                </button>
            </div>
        </div>
    `;
    messagesDiv.appendChild(msgDiv);
    scrollToBottom();
}

function addAudio(url) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot';
    msgDiv.innerHTML = `
        <div class="content">
            <audio controls>
                <source src="${url}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
        </div>
    `;
    messagesDiv.appendChild(msgDiv);
    scrollToBottom();
}

function scrollToBottom() {
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// ============ SCENE QUEUE ============
function addToSceneQueue(url, type, elementId, btn, mediaType = 'video') {
    // Add to queue with mediaType for proper handling during compilation
    sceneQueue.push({
        url: url,
        type: type,
        mediaType: mediaType,  // 'image' or 'video'
        timestamp: Date.now()
    });

    // Persist to localStorage
    saveSceneQueueToStorage();

    // Update button state
    if (btn) {
        btn.textContent = '✓ Added';
        btn.classList.add('added');
    }

    // Show panel and update UI
    showSceneQueuePanel();
    renderSceneQueue();
}

function removeFromSceneQueue(index) {
    sceneQueue.splice(index, 1);
    saveSceneQueueToStorage();
    renderSceneQueue();

    // Hide panel if empty
    if (sceneQueue.length === 0) {
        hideSceneQueuePanel();
    }
}

function renderSceneQueue() {
    if (!sceneQueueContainer) return;

    // Update count badge
    if (sceneCountBadge) {
        sceneCountBadge.textContent = sceneQueue.length;
    }

    // Update compile button state
    if (compileStoryBtn) {
        compileStoryBtn.disabled = sceneQueue.length < 2;
    }

    // Render cards
    if (sceneQueue.length === 0) {
        sceneQueueContainer.innerHTML = '<div class="scene-queue-empty">Add images/videos to build your story</div>';
        return;
    }

    sceneQueueContainer.innerHTML = '';
    sceneQueue.forEach((scene, index) => {
        const card = document.createElement('div');
        card.className = 'scene-card';

        // Get type label
        let typeLabel = scene.type;
        if (scene.mediaType === 'image') typeLabel = '🖼️ Image';
        else if (scene.type === 'wan') typeLabel = 'WAN';
        else if (scene.type === 's2v') typeLabel = 'S2V';
        else if (scene.type === 'infinitetalk') typeLabel = 'Talk';

        // Use img or video based on mediaType
        const thumbnail = scene.mediaType === 'image'
            ? `<img class="scene-thumbnail" src="${scene.url}">`
            : `<video class="scene-thumbnail" src="${scene.url}" muted></video>`;

        card.innerHTML = `
            <span class="scene-number">${index + 1}</span>
            ${thumbnail}
            <button class="scene-remove" onclick="removeFromSceneQueue(${index})">✕</button>
            <div class="scene-type">${typeLabel}</div>
        `;

        sceneQueueContainer.appendChild(card);
    });
}

function clearSceneQueue() {
    sceneQueue = [];
    saveSceneQueueToStorage();
    renderSceneQueue();
    hideSceneQueuePanel();

    // Reset all "Add to Story" buttons in chat
    document.querySelectorAll('.add-to-story-btn.added').forEach(btn => {
        btn.textContent = '➕ Add to Story';
        btn.classList.remove('added');
    });
}

function showSceneQueuePanel() {
    if (sceneQueuePanel) {
        sceneQueuePanel.classList.remove('hidden');
    }
}

function hideSceneQueuePanel() {
    if (sceneQueuePanel) {
        sceneQueuePanel.classList.add('hidden');
    }
}

function toggleSceneQueuePanel() {
    if (sceneQueuePanel) {
        sceneQueuePanel.classList.toggle('collapsed');
    }
}

async function compileStory() {
    if (sceneQueue.length < 2) {
        addSystemMessage('Need at least 2 clips to compile a story.');
        return;
    }

    addSystemMessage(`Compiling ${sceneQueue.length} clips into story video...`);

    // Disable button during compilation
    if (compileStoryBtn) {
        compileStoryBtn.disabled = true;
        compileStoryBtn.textContent = '⏳ Compiling...';
    }

    try {
        // Send full scene data with mediaType for proper handling
        const scenes = sceneQueue.map(scene => ({
            url: scene.url,
            mediaType: scene.mediaType || 'video'
        }));

        const response = await fetch(`${API_BASE}/compile-story`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scenes: scenes })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Compilation failed');
        }

        const data = await response.json();
        addSystemMessage('Story compiled successfully!');
        addVideo(data.video_url, 'Compiled Story', 'story');

        // Clear queue after successful compilation
        clearSceneQueue();

    } catch (error) {
        console.error('Story compilation failed:', error);
        addSystemMessage(`Failed to compile story: ${error.message}`);
    } finally {
        // Re-enable button
        if (compileStoryBtn) {
            compileStoryBtn.disabled = sceneQueue.length < 2;
            compileStoryBtn.textContent = '🎥 Compile Story';
        }
    }
}

// Extract last frame from video and set as current image
async function extractLastFrame(videoUrl) {
    addSystemMessage('Extracting last frame and applying face swap...');

    try {
        const response = await fetch(`${API_BASE}/extract-frame`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_url: videoUrl })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Frame extraction failed');
        }

        const data = await response.json();
        addSystemMessage('Frame extracted with face swap applied!');
        addImage(data.image_url, 'Face-swapped frame');

    } catch (error) {
        console.error('Frame extraction failed:', error);
        addSystemMessage(`Failed to extract frame: ${error.message}`);
    }
}

// Scene queue event listeners
if (compileStoryBtn) compileStoryBtn.addEventListener('click', compileStory);
if (clearQueueBtn) clearQueueBtn.addEventListener('click', clearSceneQueue);
// ============ END SCENE QUEUE ============

// ============ SCRIPT TTS ============
const scriptTTSModal = document.getElementById('script-tts-modal');
const scriptTTSInput = document.getElementById('tts-script-input');
const generateScriptTTSBtn = document.getElementById('generate-script-tts-btn');
const closeScriptTTSBtn = document.getElementById('close-script-tts-btn');
const scriptTTSBtn = document.getElementById('script-tts-btn');

function openScriptTTSModal() {
    if (scriptTTSModal) {
        scriptTTSModal.classList.remove('hidden');
        if (scriptTTSInput) scriptTTSInput.focus();
    }
}

function closeScriptTTSModal() {
    if (scriptTTSModal) {
        scriptTTSModal.classList.add('hidden');
        if (scriptTTSInput) scriptTTSInput.value = '';
    }
}

async function generateScriptTTS() {
    const text = scriptTTSInput?.value.trim();
    if (!text) {
        alert('Please enter a script.');
        return;
    }

    closeScriptTTSModal();
    addSystemMessage('Generating script audio...');

    try {
        const response = await fetch(`${API_BASE}/generate/script-tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'TTS generation failed');
        }

        const data = await response.json();
        addSystemMessage('Script audio generated!');
        addAudio(data.tts_url);

    } catch (error) {
        console.error('Script TTS failed:', error);
        addSystemMessage(`Failed to generate script audio: ${error.message}`);
    }
}

// Script TTS event listeners
if (scriptTTSBtn) scriptTTSBtn.addEventListener('click', openScriptTTSModal);
if (closeScriptTTSBtn) closeScriptTTSBtn.addEventListener('click', closeScriptTTSModal);
if (generateScriptTTSBtn) generateScriptTTSBtn.addEventListener('click', generateScriptTTS);
// ============ END SCRIPT TTS ============

// ============ LIPSYNC ============
const lipsyncBtn = document.getElementById('lipsync-btn');
const lipsyncModelSelect = document.getElementById('lipsync-model-select');

async function generateLipsync() {
    const model = lipsyncModelSelect?.value || 'veed';
    const modelName = lipsyncModelSelect?.options[lipsyncModelSelect.selectedIndex]?.text || 'Veed';

    addSystemMessage(`Generating lipsync with ${modelName}...`);

    try {
        const response = await fetch(`${API_BASE}/generate/lipsync?model=${model}`, { method: 'POST' });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Lipsync failed');
        }

        const data = await response.json();
        addSystemMessage(`Lipsync complete with ${modelName}!`);
        addVideo(data.video_url, `Lipsynced video (${modelName})`, 'lipsync');

    } catch (error) {
        console.error('Lipsync failed:', error);
        addSystemMessage(`Lipsync failed: ${error.message}`);
    }
}

// Lipsync event listener
if (lipsyncBtn) lipsyncBtn.addEventListener('click', generateLipsync);
// ============ END LIPSYNC ============

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
        // Pass the model type for scene queue classification
        addVideo(data.video_url, data.prompt, model);
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

// ============ SESSION BROWSER ============
const sessionsBtn = document.getElementById('sessions-btn');
const sessionsModal = document.getElementById('sessions-modal');
const closeSessionsBtn = document.getElementById('close-sessions-btn');
const newSessionBtn = document.getElementById('new-session-btn');
const sessionsList = document.getElementById('sessions-list');
const sessionSearch = document.getElementById('session-search');
const sessionCharacterFilter = document.getElementById('session-character-filter');

let allSessions = [];

async function loadSessions() {
    try {
        const response = await fetch(`${API_BASE}/sessions`);
        if (response.ok) {
            const data = await response.json();
            allSessions = data.sessions || [];

            // Populate character filter
            const characters = [...new Set(allSessions.map(s => s.character))];
            if (sessionCharacterFilter) {
                sessionCharacterFilter.innerHTML = '<option value="">All Characters</option>';
                characters.forEach(char => {
                    const opt = document.createElement('option');
                    opt.value = char;
                    opt.textContent = char;
                    sessionCharacterFilter.appendChild(opt);
                });
            }

            renderSessions(allSessions);
        }
    } catch (error) {
        console.error('Failed to load sessions:', error);
        if (sessionsList) {
            sessionsList.innerHTML = '<div class="no-sessions">Failed to load sessions</div>';
        }
    }
}

function renderSessions(sessions) {
    if (!sessionsList) return;

    if (sessions.length === 0) {
        sessionsList.innerHTML = '<div class="no-sessions">No sessions found</div>';
        return;
    }

    sessionsList.innerHTML = '';

    sessions.forEach(session => {
        const card = document.createElement('div');
        card.className = 'session-card';

        // Format date
        let dateStr = 'Unknown date';
        if (session.created_at) {
            const date = new Date(session.created_at);
            dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }

        card.innerHTML = `
            <div class="session-header">
                <span class="session-character">${session.character || 'Unknown'}</span>
                <span class="session-date">${dateStr}</span>
            </div>
            <div class="session-preview">${session.last_message_preview || '(No preview)'}</div>
            <div class="session-id">${session.folder_name || session.session_id}</div>
        `;

        card.addEventListener('click', () => resumeSession(session.folder_name || session.session_id));
        sessionsList.appendChild(card);
    });
}

function filterSessions() {
    const searchTerm = sessionSearch?.value.toLowerCase() || '';
    const charFilter = sessionCharacterFilter?.value || '';

    let filtered = allSessions;

    if (charFilter) {
        filtered = filtered.filter(s => s.character === charFilter);
    }

    if (searchTerm) {
        filtered = filtered.filter(s =>
            (s.session_id || '').toLowerCase().includes(searchTerm) ||
            (s.character || '').toLowerCase().includes(searchTerm) ||
            (s.last_message_preview || '').toLowerCase().includes(searchTerm)
        );
    }

    renderSessions(filtered);
}

function openSessionBrowser() {
    if (sessionsModal) {
        sessionsModal.classList.remove('hidden');
        loadSessions();
    }
}

function closeSessionBrowser() {
    if (sessionsModal) {
        sessionsModal.classList.add('hidden');
    }
}

async function resumeSession(sessionId) {
    closeSessionBrowser();
    messagesDiv.innerHTML = '';
    addSystemMessage(`Resuming session ${sessionId}...`);

    try {
        await initializeSession(user, character, sessionId);
    } catch (error) {
        console.error('Failed to resume session:', error);
        addSystemMessage('Failed to resume session.');
    }
}

async function startNewSession() {
    closeSessionBrowser();
    messagesDiv.innerHTML = '';
    addSystemMessage('Starting new session...');

    try {
        await initializeSession(user, character, null);
    } catch (error) {
        console.error('Failed to start new session:', error);
        addSystemMessage('Failed to start new session.');
    }
}

// Session browser event listeners
if (sessionsBtn) sessionsBtn.addEventListener('click', openSessionBrowser);
if (closeSessionsBtn) closeSessionsBtn.addEventListener('click', closeSessionBrowser);
if (newSessionBtn) newSessionBtn.addEventListener('click', startNewSession);
if (sessionSearch) sessionSearch.addEventListener('input', filterSessions);
if (sessionCharacterFilter) sessionCharacterFilter.addEventListener('change', filterSessions);
// ============ END SESSION BROWSER ============

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
let selectedLoraCategory = 'all';
let selectedLora = null;
let loraFavorites = JSON.parse(localStorage.getItem('lora_favorites') || '[]');

// Load LoRA presets from server and render grid
async function loadLoraPresets() {
    try {
        const response = await fetch(`${API_BASE}/lora-presets`);
        if (response.ok) {
            const data = await response.json();
            LORA_PRESETS = data.presets || {};
            renderLoraGrid();
            renderFavorites();
            populateLoraDropdown2();
        }
    } catch (error) {
        console.error('Failed to load LoRA presets:', error);
    }
}

// Render the main LoRA grid based on selected category
function renderLoraGrid() {
    const grid = document.getElementById('lora-grid');
    if (!grid) return;

    grid.innerHTML = '';

    for (const [name, preset] of Object.entries(LORA_PRESETS)) {
        const category = preset.category || 'uncategorized';
        if (selectedLoraCategory !== 'all' && category !== selectedLoraCategory) continue;

        const item = document.createElement('div');
        item.className = 'lora-item' + (selectedLora === name ? ' selected' : '');

        const isFav = loraFavorites.includes(name);
        item.innerHTML = `
            <span class="star ${isFav ? 'favorited' : ''}" data-name="${name}">⭐</span>
            <span class="name">${name}</span>
        `;

        // Click on name to select
        item.querySelector('.name').addEventListener('click', () => selectLora(name));

        // Click on star to toggle favorite
        item.querySelector('.star').addEventListener('click', (e) => {
            e.stopPropagation();
            toggleFavorite(name);
        });

        grid.appendChild(item);
    }

    // Add Custom URL option
    const customItem = document.createElement('div');
    customItem.className = 'lora-item' + (selectedLora === 'custom' ? ' selected' : '');
    customItem.innerHTML = '<span class="name">📝 Custom URL...</span>';
    customItem.addEventListener('click', () => selectLora('custom'));
    grid.appendChild(customItem);
}

// Render favorites row
function renderFavorites() {
    const favContainer = document.getElementById('lora-favorites');
    if (!favContainer) return;

    favContainer.innerHTML = '';

    if (loraFavorites.length === 0) {
        favContainer.innerHTML = '<span style="color: #666; font-size: 0.7rem;">Click ⭐ to add favorites</span>';
        return;
    }

    for (const name of loraFavorites) {
        if (!LORA_PRESETS[name]) continue;

        const item = document.createElement('div');
        item.className = 'lora-fav-item';
        item.textContent = name;
        item.addEventListener('click', () => selectLora(name));
        favContainer.appendChild(item);
    }
}

// Select a LoRA
function selectLora(name) {
    selectedLora = name;

    // Update hidden input for form submission
    const presetSelect = document.getElementById('lora-preset-select');
    if (presetSelect) presetSelect.value = name;

    // Update display
    const nameDisplay = document.getElementById('selected-lora-name');
    if (nameDisplay) nameDisplay.textContent = name === 'custom' ? '(Custom)' : `(${name})`;

    // Show/hide custom URL field
    const customGroup = document.getElementById('custom-url-group');
    if (customGroup) customGroup.style.display = name === 'custom' ? 'block' : 'none';

    // Pre-fill prompt and scale
    if (name !== 'custom' && LORA_PRESETS[name]) {
        const promptField = document.getElementById('lora-prompt');
        const scaleField = document.getElementById('lora-scale');
        if (promptField) promptField.value = LORA_PRESETS[name].prompt || '';
        if (scaleField) scaleField.value = LORA_PRESETS[name].scale || 1.0;
    }

    renderLoraGrid(); // Re-render to update selection state
}

// Toggle favorite status
function toggleFavorite(name) {
    const idx = loraFavorites.indexOf(name);
    if (idx === -1) {
        loraFavorites.push(name);
    } else {
        loraFavorites.splice(idx, 1);
    }
    localStorage.setItem('lora_favorites', JSON.stringify(loraFavorites));
    renderLoraGrid();
    renderFavorites();
}

// Populate LoRA 2 dropdown (simplified)
function populateLoraDropdown2() {
    const loraPresetSelect2 = document.getElementById('lora-preset-select-2');
    if (!loraPresetSelect2) return;

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
    const customOption = document.createElement('option');
    customOption.value = 'custom';
    customOption.textContent = 'Custom URL...';
    loraPresetSelect2.appendChild(customOption);
}

// Category tab click handlers
document.querySelectorAll('.lora-cat-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.lora-cat-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedLoraCategory = btn.dataset.cat;
        renderLoraGrid();
    });
});

// Keep old function name for compatibility
function populateLoraDropdown() {
    renderLoraGrid();
    renderFavorites();
    populateLoraDropdown2();
}

// Load presets on page load
loadLoraPresets();

// ============ DEBUG MODE ============
let IMAGE_PROMPT_COMPONENTS = {};
let debugPreviewImagePath = null;  // Store path of generated preview image

// Load image prompt components from server
async function loadImagePromptComponents() {
    try {
        const response = await fetch(`${API_BASE}/image-prompt-components`);
        if (response.ok) {
            const data = await response.json();
            IMAGE_PROMPT_COMPONENTS = data.components || {};
            populatePromptDropdowns();
        }
    } catch (error) {
        console.error('Failed to load image prompt components:', error);
    }
}

function populatePromptDropdowns() {
    const dropdowns = {
        'prompt-character': IMAGE_PROMPT_COMPONENTS.character || [],
        'prompt-pose': IMAGE_PROMPT_COMPONENTS.pose || [],
        'prompt-setting': IMAGE_PROMPT_COMPONENTS.setting || [],
        'prompt-style': IMAGE_PROMPT_COMPONENTS.style || []
    };

    for (const [id, options] of Object.entries(dropdowns)) {
        const select = document.getElementById(id);
        if (!select) continue;

        select.innerHTML = '<option value="">-- Select --</option>';
        for (const option of options) {
            const opt = document.createElement('option');
            opt.value = option;
            opt.textContent = option.length > 50 ? option.substring(0, 50) + '...' : option;
            select.appendChild(opt);
        }
    }
}

// Build prompt from dropdown selections
function buildImagePrompt() {
    const character = document.getElementById('prompt-character')?.value || '';
    const pose = document.getElementById('prompt-pose')?.value || '';
    const setting = document.getElementById('prompt-setting')?.value || '';
    const style = document.getElementById('prompt-style')?.value || '';

    const parts = [character, pose].filter(Boolean).join(', ');
    const withSetting = setting ? `${parts}, in ${setting}` : parts;
    const withStyle = style ? `${withSetting}, ${style}` : withSetting;

    return withStyle;
}

// Update prompt textarea when dropdowns change
function setupPromptBuilderListeners() {
    const dropdownIds = ['prompt-character', 'prompt-pose', 'prompt-setting', 'prompt-style'];
    const promptTextarea = document.getElementById('debug-image-prompt');

    for (const id of dropdownIds) {
        const select = document.getElementById(id);
        if (select) {
            select.addEventListener('change', () => {
                if (promptTextarea) {
                    promptTextarea.value = buildImagePrompt();
                }
            });
        }
    }
}

// Extract |...| from last assistant message
function extractPromptFromChat() {
    const messages = document.querySelectorAll('.message.assistant');
    if (messages.length === 0) return '';

    const lastMessage = messages[messages.length - 1];
    const text = lastMessage.textContent || '';

    // Find text between | delimiters
    const match = text.match(/\|([^|]+)\|/);
    return match ? match[1].trim() : '';
}

// Debug mode toggle
const debugModeToggle = document.getElementById('debug-mode-toggle');
const debugModeSection = document.getElementById('debug-mode-section');

if (debugModeToggle) {
    debugModeToggle.addEventListener('change', () => {
        if (debugModeSection) {
            debugModeSection.style.display = debugModeToggle.checked ? 'block' : 'none';
        }
        if (debugModeToggle.checked) {
            loadImagePromptComponents();
        }
    });
}

// "From Chat" button - extract prompt from last assistant message
const useChatPromptBtn = document.getElementById('use-chat-prompt-btn');
if (useChatPromptBtn) {
    useChatPromptBtn.addEventListener('click', () => {
        const extracted = extractPromptFromChat();
        const promptTextarea = document.getElementById('debug-image-prompt');
        if (promptTextarea && extracted) {
            promptTextarea.value = extracted;
        } else if (!extracted) {
            alert('No |...| prompt found in chat messages');
        }
    });
}

// Generate Preview button
const generatePreviewBtn = document.getElementById('generate-preview-btn');
if (generatePreviewBtn) {
    generatePreviewBtn.addEventListener('click', async () => {
        const promptTextarea = document.getElementById('debug-image-prompt');
        const prompt = promptTextarea?.value.trim();

        if (!prompt) {
            alert('Please enter or build an image prompt');
            return;
        }

        generatePreviewBtn.disabled = true;
        generatePreviewBtn.textContent = '⏳ Generating...';

        try {
            const response = await fetch(`${API_BASE}/generate/image`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ custom_prompt: prompt })
            });

            if (!response.ok) {
                throw new Error('Image generation failed');
            }

            const data = await response.json();
            debugPreviewImagePath = data.image_path;

            // Show preview
            const previewContainer = document.getElementById('debug-preview-container');
            const previewImage = document.getElementById('debug-preview-image');
            if (previewContainer && previewImage) {
                previewImage.src = debugPreviewImagePath + '?t=' + Date.now();
                previewContainer.style.display = 'block';
            }
        } catch (error) {
            console.error('Preview generation failed:', error);
            alert('Failed to generate preview: ' + error.message);
        } finally {
            generatePreviewBtn.disabled = false;
            generatePreviewBtn.textContent = '📷 Generate Preview';
        }
    });
}

setupPromptBuilderListeners();
// ============ END DEBUG MODE ============

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

    // Get LoRA 1 URL from preset or custom input (null if not selected)
    let loraUrl = null;
    if (presetValue === 'custom') {
        const customUrl = document.getElementById('lora-url').value.trim();
        loraUrl = customUrl || null;
    } else if (presetValue && LORA_PRESETS[presetValue]?.url) {
        loraUrl = LORA_PRESETS[presetValue].url;
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

    // Check if debug mode has a preview image to use
    const debugMode = document.getElementById('debug-mode-toggle')?.checked;
    const usePreviewImage = debugMode && debugPreviewImagePath;

    loraModal.classList.add('hidden');
    const modelName = wanModel === 'wan-2.2-fast' ? 'WAN 2.2 Fast' : 'WAN 2.1';
    const loraInfo = loraUrl ? ` + ${presetValue === 'custom' ? 'Custom LoRA' : presetValue}` : '';
    const lora2Info = loraUrl2 ? ` + ${preset2Value}` : '';
    const debugInfo = usePreviewImage ? ' [using preview image]' : '';
    addSystemMessage(`Generating WAN video with ${modelName}${loraInfo}${lora2Info} (${numFrames} frames @ ${fps}fps)${debugInfo}...`);

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
                fps: fps,
                use_preview_image: usePreviewImage
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'LoRA video generation failed');
        }

        const data = await response.json();
        addVideo(data.video_url, data.prompt, 'wan');
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

// ============ IMAGE EDIT & FACESWAP ============
let currentEditImageUrl = null;

const imageEditModal = document.getElementById('image-edit-modal');
const editPreviewImage = document.getElementById('edit-preview-image');
const editPromptInput = document.getElementById('edit-prompt-input');
const submitEditBtn = document.getElementById('submit-edit-btn');
const closeEditBtn = document.getElementById('close-edit-btn');

function openEditModal(imageUrl) {
    currentEditImageUrl = imageUrl;
    if (editPreviewImage) {
        editPreviewImage.src = imageUrl;
    }
    if (editPromptInput) {
        editPromptInput.value = '';
    }
    if (imageEditModal) {
        imageEditModal.classList.remove('hidden');
    }
}

async function submitImageEdit() {
    const prompt = editPromptInput?.value.trim();
    if (!prompt) {
        alert('Please enter an edit instruction.');
        return;
    }

    if (!currentEditImageUrl) {
        alert('No image selected for editing.');
        return;
    }

    // Close modal and show loading
    if (imageEditModal) imageEditModal.classList.add('hidden');
    addSystemMessage(`Editing image: "${prompt.substring(0, 50)}..."...`);

    try {
        const response = await fetch(`${API_BASE}/edit/image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_url: currentEditImageUrl,
                prompt: prompt
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Image edit failed');
        }

        const data = await response.json();
        addImage(data.image_url, `Edited: ${prompt}`);
        addSystemMessage('Image edited successfully!');
    } catch (error) {
        console.error('Image edit failed:', error);
        addSystemMessage(`Failed to edit image: ${error.message}`);
    }
}

async function applyFaceswap(imageUrl, btn) {
    // Disable button and show loading state
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳...';
    }

    addSystemMessage('Applying face swap...');

    try {
        const response = await fetch(`${API_BASE}/faceswap`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_url: imageUrl
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Face swap failed');
        }

        const data = await response.json();
        addImage(data.image_url, 'Face swapped');
        addSystemMessage('Face swap applied successfully!');
    } catch (error) {
        console.error('Face swap failed:', error);
        addSystemMessage(`Failed to apply face swap: ${error.message}`);
    } finally {
        // Restore button
        if (btn) {
            btn.disabled = false;
            btn.textContent = '🔄 Face';
        }
    }
}

// Image edit modal event listeners
if (submitEditBtn) submitEditBtn.addEventListener('click', submitImageEdit);
if (closeEditBtn) closeEditBtn.addEventListener('click', () => {
    if (imageEditModal) imageEditModal.classList.add('hidden');
});
if (editPromptInput) {
    editPromptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitImageEdit();
        }
    });
}
// ============ END IMAGE EDIT & FACESWAP ============

// Start
document.addEventListener('DOMContentLoaded', init);
