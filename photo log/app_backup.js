/**
 * Main Application Logic
 * Manages application state and user interactions
 */

// Application state
const appState = {
    workAreas: [],
    projectName: ''
};

/**
 * Initialize application
 */
function initApp() {
    console.log('Initializing Photo Layout Application...');

    // Set up event listeners
    setupEventListeners();

    // Add initial work area
    addWorkArea();

    console.log('Application initialized successfully');
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Add work area button
    const addWorkAreaBtn = document.getElementById('addWorkAreaBtn');
    if (addWorkAreaBtn) {
        addWorkAreaBtn.addEventListener('click', addWorkArea);
    }

    // Generate Excel button
    const generateExcelBtn = document.getElementById('generateExcelBtn');
    if (generateExcelBtn) {
        generateExcelBtn.addEventListener('click', handleGenerateExcel);
    }

    // Generate CSV button
    const generateCsvBtn = document.getElementById('generateCsvBtn');
    if (generateCsvBtn) {
        generateCsvBtn.addEventListener('click', handleGenerateCSV);
    }

    // Save work button
    const saveWorkBtn = document.getElementById('saveWorkBtn');
    if (saveWorkBtn) {
        saveWorkBtn.addEventListener('click', handleSaveWork);
    }

    // Load work button
    const loadWorkBtn = document.getElementById('loadWorkBtn');
    if (loadWorkBtn) {
        loadWorkBtn.addEventListener('click', handleLoadWork);
    }

    // Reset button
    const resetBtn = document.getElementById('resetBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', handleReset);
    }

    // Project name input
    const projectNameInput = document.getElementById('projectName');
    if (projectNameInput) {
        projectNameInput.addEventListener('input', debounce((e) => {
            appState.projectName = e.target.value.trim();
            updateGenerateButton();
        }, 300));
    }
}

/**
 * Add new work area
 */
function addWorkArea() {
    const workAreaId = generateId();
    const workAreaNumber = appState.workAreas.length + 1;

    const workArea = {
        id: workAreaId,
        name: ``,
        photos: []
    };

    appState.workAreas.push(workArea);

    renderWorkArea(workArea, workAreaNumber);
    updateGenerateButton();
}

/**
 * Render work area card
 * @param {Object} workArea - Work area object
 * @param {number} number - Work area number
 */
function renderWorkArea(workArea, number) {
    const container = document.getElementById('workAreasContainer');
    if (!container) return;

    const card = document.createElement('div');
    card.className = 'work-area-card fade-in';
    card.dataset.workAreaId = workArea.id;

    card.innerHTML = `
        <div class="work-area-header">
            <div class="work-area-title form-group">
                <label class="label">작업장 ${number}</label>
                <input 
                    type="text" 
                    class="input work-area-name-input" 
                    placeholder="예) 1601동 25층 바닥철근 검측"
                    value="${workArea.name}"
                >
            </div>
            <div class="work-area-actions">
                <button class="btn btn-danger btn-small remove-work-area-btn" title="작업장 제거">
                    <span class="btn-icon">🗑️</span>
                </button>
            </div>
        </div>
        
        <div class="upload-zone">
            <div class="upload-icon">📤</div>
            <p class="upload-text">사진을 드래그하거나 클릭하여 업로드</p>
            <p class="upload-hint">JPG, PNG, BMP 파일 지원 (최대 10MB)</p>
            <input type="file" class="file-input" accept="image/jpeg,image/jpg,image/png,image/bmp" multiple>
        </div>
        
        <div class="photos-grid"></div>
    `;

    container.appendChild(card);

    // Setup event listeners for this work area
    setupWorkAreaListeners(card, workArea);
}

/**
 * Setup event listeners for work area
 * @param {HTMLElement} card - Work area card element
 * @param {Object} workArea - Work area object
 */
function setupWorkAreaListeners(card, workArea) {
    // Work area name input
    const nameInput = card.querySelector('.work-area-name-input');
    if (nameInput) {
        nameInput.addEventListener('input', debounce((e) => {
            workArea.name = e.target.value.trim();
            updateGenerateButton();
        }, 300));
    }

    // Remove work area button
    const removeBtn = card.querySelector('.remove-work-area-btn');
    if (removeBtn) {
        removeBtn.addEventListener('click', () => {
            removeWorkArea(workArea.id);
        });
    }

    // Initialize file handlers
    initializeFileHandlers(card, (photos) => {
        handlePhotosAdded(workArea, photos);
        updatePhotosDisplay(card, workArea);
    });
}

/**
 * Handle photos added to work area
 * @param {Object} workArea - Work area object
 * @param {Object[]} photos - Array of photo data
 */
function handlePhotosAdded(workArea, photos) {
    workArea.photos.push(...photos);
    updateGenerateButton();
}

/**
 * Update photos display for work area
 * @param {HTMLElement} card - Work area card element
 * @param {Object} workArea - Work area object
 */
function updatePhotosDisplay(card, workArea) {
    const photosGrid = card.querySelector('.photos-grid');
    if (!photosGrid) return;

    updatePhotoGrid(photosGrid, workArea.photos, (photoId) => {
        removePhoto(workArea, photoId);
    });
}

/**
 * Remove photo from work area
 * @param {Object} workArea - Work area object
 * @param {string} photoId - Photo ID
 */
function removePhoto(workArea, photoId) {
    const index = workArea.photos.findIndex(p => p.id === photoId);
    if (index !== -1) {
        workArea.photos.splice(index, 1);
        updateGenerateButton();
    }
}

/**
 * Remove work area
 * @param {string} workAreaId - Work area ID
 */
function removeWorkArea(workAreaId) {
    // Don't allow removing the last work area
    if (appState.workAreas.length <= 1) {
        showStatus('최소 1개의 작업장이 필요합니다.', 'error');
        return;
    }

    const index = appState.workAreas.findIndex(wa => wa.id === workAreaId);
    if (index !== -1) {
        appState.workAreas.splice(index, 1);

        // Remove from DOM
        const card = document.querySelector(`[data-work-area-id="${workAreaId}"]`);
        if (card) {
            card.remove();
        }

        // Renumber remaining work areas
        renumberWorkAreas();
        updateGenerateButton();
    }
}

/**
 * Renumber work area labels
 */
function renumberWorkAreas() {
    const cards = document.querySelectorAll('.work-area-card');
    cards.forEach((card, index) => {
        const label = card.querySelector('.label');
        if (label) {
            label.textContent = `작업장 ${index + 1}`;
        }
    });
}

/**
 * Update generate button state
 */
function updateGenerateButton() {
    const generateBtn = document.getElementById('generateExcelBtn');
    if (!generateBtn) return;

    // Check if there are any work areas with photos
    const hasPhotos = appState.workAreas.some(wa =>
        wa.name.trim() !== '' && wa.photos.length > 0
    );

    generateBtn.disabled = !hasPhotos;

    const generateCsvBtn = document.getElementById('generateCsvBtn');
    if (generateCsvBtn) {
        generateCsvBtn.disabled = !hasPhotos;
    }
}

/**
 * Handle generate Excel button click
 */
async function handleGenerateExcel() {
    try {
        // Validate data
        const validWorkAreas = appState.workAreas.filter(wa =>
            wa.name.trim() !== '' && wa.photos.length > 0
        );

        if (validWorkAreas.length === 0) {
            showStatus('작업장명과 사진을 모두 입력해주세요.', 'error');
            return;
        }

        // Prepare data
    }

/**
 * Handle generate CSV button click
 */
async function handleGenerateCSV() {
        try {
            // Validate data
            const validWorkAreas = appState.workAreas.filter(wa =>
                wa.name.trim() !== '' && wa.photos.length > 0
            );

            if (validWorkAreas.length === 0) {
                showStatus('작업장명과 사진을 모두 입력해주세요.', 'error');
                return;
            }

            // Prepare data
            const workAreasData = {};
            validWorkAreas.forEach(wa => {
                workAreasData[wa.name] = wa.photos;
            });

            // Generate and download CSV
            await downloadCSVFile(workAreasData, appState.projectName);

        } catch (error) {
            console.error('Error generating CSV:', error);
            showStatus('CSV 생성 중 오류가 발생했습니다.', 'error');
        }
    }

    /**
     * Handle save work button click
     */
    function handleSaveWork() {
        try {
            // Check if there's any data to save
            if (appState.workAreas.length === 0 ||
                appState.workAreas.every(wa => wa.photos.length === 0)) {
                showStatus('저장할 데이터가 없습니다.', 'error');
                return;
            }

            // Prompt for save name
            const defaultName = `${appState.projectName || '나의 작업'} (${formatDateKorean(new Date())})`;
            const saveName = prompt('저장할 이름을 입력해주세요:', defaultName);

            if (saveName === null) return; // Cancelled

            // Save work data
            saveWorkData(appState, saveName);

            showStatus('작업이 저장되었습니다!', 'success');
        } catch (error) {
            console.error('Error saving work:', error);
            showStatus(error.message || '작업 저장 중 오류가 발생했습니다.', 'error');
        }
    }

    /**
     * Handle load work button click
     */
    function handleLoadWork() {
        const modal = document.getElementById('loadWorkModal');
        if (!modal) return;

        // Render list
        renderSavedWorksList();

        // Show modal
        modal.classList.remove('hidden');

        // Setup modal close handlers
        const closeBtn = modal.querySelector('.close-modal-btn');
        if (closeBtn) {
            closeBtn.onclick = () => modal.classList.add('hidden');
        }

        // Close on click outside
        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        };
    }

    /**
     * Render saved works list in modal
     */
    function renderSavedWorksList() {
        const listContainer = document.getElementById('savedWorksList');
        if (!listContainer) return;

        const saves = getSavedWorksList();

        if (saves.length === 0) {
            listContainer.innerHTML = `
            <div class="empty-saves">
                <p>저장된 작업이 없습니다.</p>
            </div>
        `;
            return;
        }

        listContainer.innerHTML = '';

        saves.forEach(save => {
            const item = document.createElement('div');
            item.className = 'saved-work-item';
            item.innerHTML = `
            <div class="saved-work-info">
                <div class="saved-work-name">${save.name}</div>
                <div class="saved-work-details">
                    ${save.projectName || '(이름 없음)'} | 
                    사진 ${save.photoCount}개 | 
                    ${formatDateTime(save.timestamp)}
                </div>
            </div>
            <div class="saved-work-actions">
                <button class="btn-load" data-id="${save.id}">불러오기</button>
                <button class="btn-delete" data-id="${save.id}">삭제</button>
            </div>
        `;

            // Add event listeners
            const loadBtn = item.querySelector('.btn-load');
            loadBtn.onclick = () => loadSavedWork(save.id);

            const deleteBtn = item.querySelector('.btn-delete');
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                deleteSavedWork(save.id);
            };

            listContainer.appendChild(item);
        });
    }

    /**
     * Load specific saved work
     * @param {string} id - Save ID
     */
    function loadSavedWork(id) {
        try {
            if (!confirm('현재 작업 내용이 사라집니다. 저장된 작업을 불러오시겠습니까?')) {
                return;
            }

            const loadedData = loadWorkData(id);

            if (!loadedData) {
                showStatus('작업을 불러올 수 없습니다.', 'error');
                return;
            }

            // Clear current state
            appState.workAreas = [];
            appState.projectName = loadedData.projectName || '';

            // Update project name input
            const projectNameInput = document.getElementById('projectName');
            if (projectNameInput) {
                projectNameInput.value = appState.projectName;
            }

            // Clear work areas container
            const container = document.getElementById('workAreasContainer');
            if (container) {
                container.innerHTML = '';
            }

            // Restore work areas
            loadedData.workAreas.forEach((wa, index) => {
                appState.workAreas.push(wa);
                renderWorkArea(wa, index + 1);

                // Update photos display
                const card = document.querySelector(`[data-work-area-id="${wa.id}"]`);
                if (card) {
                    const photosGrid = card.querySelector('.photos-grid');
                    if (photosGrid) {
                        updatePhotoGrid(photosGrid, wa.photos, (photoId) => {
                            removePhoto(wa, photoId);
                        });
                    }
                }
            });

            updateGenerateButton();

            // Close modal
            document.getElementById('loadWorkModal').classList.add('hidden');

            showStatus('작업을 불러왔습니다!', 'success');

        } catch (error) {
            console.error('Error loading work:', error);
            showStatus('작업 불러오기 중 오류가 발생했습니다.', 'error');
        }
    }

    /**
     * Delete saved work
     * @param {string} id - Save ID
     */
    function deleteSavedWork(id) {
        if (!confirm('정말 이 저장본을 삭제하시겠습니까?')) {
            return;
        }

        try {
            deleteWorkData(id);
            renderSavedWorksList(); // Refresh list
            showStatus('삭제되었습니다.', 'success');
        } catch (error) {
            console.error('Error deleting work:', error);
            showStatus('삭제 중 오류가 발생했습니다.', 'error');
        }
    }

    /**
     * Handle reset button click
     */
    function handleReset() {
        if (!confirm('모든 데이터가 초기화됩니다. 계속하시겠습니까?')) {
            return;
        }

        // Clear state
        appState.workAreas = [];
        appState.projectName = '';

        // Clear UI
        const container = document.getElementById('workAreasContainer');
        if (container) {
            container.innerHTML = '';
        }

        const projectNameInput = document.getElementById('projectName');
        if (projectNameInput) {
            projectNameInput.value = '';
        }

        // Add initial work area
        addWorkArea();

        showStatus('초기화되었습니다.', 'success');
    }

    /**
     * Initialize app when DOM is ready
     */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initApp);
    } else {
        initApp();
    }
