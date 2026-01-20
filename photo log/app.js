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

    // Delete works button
    const deleteWorksBtn = document.getElementById('deleteWorksBtn');
    if (deleteWorksBtn) {
        deleteWorksBtn.addEventListener('click', handleDeleteWorks);
    }

    // Manage templates button
    const manageTemplatesBtn = document.getElementById('manageTemplatesBtn');
    if (manageTemplatesBtn) {
        manageTemplatesBtn.addEventListener('click', handleManageTemplates);
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
        workDescription: '',
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
                <div class="template-selector-container">
                    <select class="template-selector input" style="margin-bottom: 8px;">
                        <option value="">📋 템플릿 선택 (또는 직접 입력)</option>
                    </select>
                </div>
                <input 
                    type="text" 
                    class="input work-area-name-input" 
                    placeholder="예) 1601동 25층 바닥철근 검측"
                    value="${workArea.name}"
                >
            </div>
            <div class="work-area-actions">
                <!-- Delete button removed as requested -->
            </div>
        </div>
        
        <div class="form-group">
            <label class="label">작업내용</label>
            <textarea 
                class="input work-description-input" 
                placeholder="예) 바닥철근 배근 완료, 슬리브 설치 완료"
                rows="3"
            >${workArea.workDescription}</textarea>
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

    // Template selector
    const templateSelector = card.querySelector('.template-selector');
    if (templateSelector) {
        // Populate template options
        const templates = getWorkAreaTemplates();
        templates.forEach(template => {
            const option = document.createElement('option');
            option.value = template.name;
            option.textContent = template.name;
            templateSelector.appendChild(option);
        });

        // Handle template selection
        templateSelector.addEventListener('change', (e) => {
            if (e.target.value && nameInput) {
                nameInput.value = e.target.value;
                workArea.name = e.target.value;
                updateGenerateButton();
            }
        });
    }

    // Work description input
    const descInput = card.querySelector('.work-description-input');
    if (descInput) {
        descInput.addEventListener('input', debounce((e) => {
            workArea.workDescription = e.target.value.trim();
        }, 300));
    }

    // Remove work area button - Removed
    /*
    const removeBtn = card.querySelector('.remove-work-area-btn');
    if (removeBtn) {
        removeBtn.addEventListener('click', () => {
            removeWorkArea(workArea.id);
        });
    }
    */

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
        const workAreasData = {};
        validWorkAreas.forEach(wa => {
            workAreasData[wa.name] = wa.photos;
        });

        // Generate and download Excel (ExcelJS with 1x2 vertical layout + work description)
        await downloadExcelFileExcelJS(workAreasData, appState.projectName, appState.workAreas);

    } catch (error) {
        console.error('Error generating Excel:', error);
        showStatus('Excel 생성 중 오류가 발생했습니다.', 'error');
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

        // Show save name modal
        const modal = document.getElementById('saveNameModal');
        const input = document.getElementById('saveNameInput');
        const confirmBtn = document.getElementById('confirmSaveBtn');

        if (!modal || !input || !confirmBtn) return;

        // Set default name
        const defaultName = `${appState.projectName || '나의 작업'} (${formatDateKorean(new Date())})`;
        input.value = defaultName;

        // Show modal
        modal.classList.remove('hidden');
        input.focus();
        input.select();

        // Handle confirm button
        const handleConfirm = () => {
            const saveName = input.value.trim();
            if (!saveName) {
                showStatus('저장 이름을 입력해주세요.', 'error');
                return;
            }

            try {
                // Save work data
                saveWorkData(appState, saveName);

                // Close modal
                modal.classList.add('hidden');

                showStatus('작업이 저장되었습니다!', 'success');
            } catch (error) {
                console.error('Error saving work:', error);
                showStatus(error.message || '작업 저장 중 오류가 발생했습니다.', 'error');
            }

            // Clean up
            confirmBtn.removeEventListener('click', handleConfirm);
            input.removeEventListener('keypress', handleKeyPress);
        };

        // Handle Enter key
        const handleKeyPress = (e) => {
            if (e.key === 'Enter') {
                handleConfirm();
            }
        };

        // Add event listeners
        confirmBtn.addEventListener('click', handleConfirm);
        input.addEventListener('keypress', handleKeyPress);

        // Close on click outside
        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
                confirmBtn.removeEventListener('click', handleConfirm);
                input.removeEventListener('keypress', handleKeyPress);
            }
        };

    } catch (error) {
        console.error('Error in handleSaveWork:', error);
        showStatus('작업 저장 중 오류가 발생했습니다.', 'error');
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
        item.ondblclick = () => loadSavedWork(save.id);

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
 * Handle delete works button click
 */
function handleDeleteWorks() {
    const modal = document.getElementById('deleteWorksModal');
    if (!modal) return;

    // Render list with checkboxes
    renderDeleteWorksList();

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

    // Handle confirm delete button
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    if (confirmBtn) {
        confirmBtn.onclick = () => confirmBatchDelete();
    }
}

/**
 * Render delete works list with checkboxes
 */
function renderDeleteWorksList() {
    const listContainer = document.getElementById('deleteWorksList');
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
        item.style.cursor = 'pointer';
        item.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; flex: 1;">
                <input type="checkbox" class="delete-checkbox" data-id="${save.id}" style="width: 18px; height: 18px; cursor: pointer;">
                <div class="saved-work-info" style="flex: 1;">
                    <div class="saved-work-name">${save.name}</div>
                    <div class="saved-work-details">
                        ${save.projectName || '(이름 없음)'} | 
                        사진 ${save.photoCount}개 | 
                        ${formatDateTime(save.timestamp)}
                    </div>
                </div>
            </div>
        `;

        // Click item to toggle checkbox
        item.onclick = (e) => {
            if (e.target.type !== 'checkbox') {
                const checkbox = item.querySelector('.delete-checkbox');
                checkbox.checked = !checkbox.checked;
            }
        };

        listContainer.appendChild(item);
    });
}

/**
 * Confirm and execute batch delete
 */
function confirmBatchDelete() {
    const checkboxes = document.querySelectorAll('.delete-checkbox:checked');

    if (checkboxes.length === 0) {
        showStatus('삭제할 항목을 선택해주세요.', 'error');
        return;
    }

    if (!confirm(`선택한 ${checkboxes.length}개의 작업을 삭제하시겠습니까?`)) {
        return;
    }

    try {
        const idsToDelete = Array.from(checkboxes).map(cb => cb.dataset.id);

        idsToDelete.forEach(id => {
            deleteWorkData(id);
        });

        // Close modal
        document.getElementById('deleteWorksModal').classList.add('hidden');

        showStatus(`${idsToDelete.length}개의 작업이 삭제되었습니다.`, 'success');
    } catch (error) {
        console.error('Error deleting works:', error);
        showStatus('작업 삭제 중 오류가 발생했습니다.', 'error');
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
 * ============================================
 * TEMPLATE MANAGEMENT FUNCTIONS
 * ============================================
 */

/**
 * Handle manage templates button click
 */
function handleManageTemplates() {
    const modal = document.getElementById('templateManagementModal');
    if (!modal) return;

    // Render templates list
    renderTemplatesList();

    // Show modal
    modal.classList.remove('hidden');

    // Setup event listeners
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

    // Add template button
    const addTemplateBtn = document.getElementById('addTemplateBtn');
    const newTemplateInput = document.getElementById('newTemplateInput');

    if (addTemplateBtn && newTemplateInput) {
        const handleAdd = () => {
            const templateName = newTemplateInput.value.trim();
            if (!templateName) {
                showStatus('템플릿 이름을 입력해주세요.', 'error');
                return;
            }

            try {
                saveWorkAreaTemplate(templateName);
                newTemplateInput.value = '';
                renderTemplatesList();
                showStatus('템플릿이 추가되었습니다.', 'success');
                refreshAllTemplateSelectors();
            } catch (error) {
                console.error('Error adding template:', error);
                showStatus('템플릿 추가 중 오류가 발생했습니다.', 'error');
            }
        };

        addTemplateBtn.onclick = handleAdd;
        newTemplateInput.onkeypress = (e) => {
            if (e.key === 'Enter') {
                handleAdd();
            }
        };
    }
}

/**
 * Refresh all template selectors in existing work area cards
 */
function refreshAllTemplateSelectors() {
    const selectors = document.querySelectorAll('.template-selector');
    const templates = getWorkAreaTemplates();

    selectors.forEach(selector => {
        const currentValue = selector.value;

        // Clear existing options except the first one (placeholder)
        while (selector.options.length > 1) {
            selector.remove(1);
        }

        // Add updated options
        templates.forEach(template => {
            const option = document.createElement('option');
            option.value = template.name;
            option.textContent = template.name;
            selector.appendChild(option);
        });

        // Restore selection if possible, otherwise reset to empty
        // Check if the current value still exists in the new options
        const options = Array.from(selector.options).map(o => o.value);
        if (currentValue && options.includes(currentValue)) {
            selector.value = currentValue;
        } else {
            selector.value = "";
        }
    });
}

/**
 * Render templates list in modal
 */
function renderTemplatesList() {
    const listContainer = document.getElementById('templatesList');
    if (!listContainer) return;

    const templates = getWorkAreaTemplates();

    // Reset selection state when rendering list
    templateSelectionState.clear();
    updateBulkActionButtons();

    const selectAllCheckbox = document.getElementById('selectAllTemplates');
    if (selectAllCheckbox) selectAllCheckbox.checked = false;

    if (templates.length === 0) {
        listContainer.innerHTML = `
            <div class="empty-saves">
                <p>등록된 템플릿이 없습니다.</p>
            </div>
        `;
        return;
    }

    listContainer.innerHTML = '';

    templates.forEach(template => {
        const item = document.createElement('div');
        item.className = 'template-item';
        item.innerHTML = `
            <div class="template-checkbox-wrapper">
                <input type="checkbox" class="template-checkbox" data-id="${template.id}">
            </div>
            <div class="template-info">
                <div class="template-name">${template.name}</div>
            </div>
            <div class="template-actions">
                <button class="btn-edit" data-id="${template.id}">✏️ 수정</button>
                <button class="btn-delete-template" data-id="${template.id}">🗑️ 삭제</button>
            </div>
        `;

        // Checkbox
        const checkbox = item.querySelector('.template-checkbox');
        checkbox.onchange = (e) => handleTemplateCheckboxChange(template.id, e.target.checked);

        // Click item to toggle checkbox (excluding actions)
        item.onclick = (e) => {
            if (e.target !== checkbox && !e.target.closest('.template-actions')) {
                checkbox.checked = !checkbox.checked;
                handleTemplateCheckboxChange(template.id, checkbox.checked);
            }
        };

        // Edit button
        const editBtn = item.querySelector('.btn-edit');
        editBtn.onclick = (e) => {
            e.stopPropagation();
            handleEditTemplate(template.id, template.name);
        };

        // Delete button
        const deleteBtn = item.querySelector('.btn-delete-template');
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            handleDeleteTemplate(template.id);
        };

        listContainer.appendChild(item);
    });
}

// Track selected templates for bulk action
const templateSelectionState = new Set();

/**
 * Handle template checkbox change
 */
function handleTemplateCheckboxChange(id, checked) {
    if (checked) {
        templateSelectionState.add(id);
    } else {
        templateSelectionState.delete(id);
    }
    updateBulkActionButtons();
}

/**
 * Update bulk action buttons state
 */
function updateBulkActionButtons() {
    const bulkActions = document.querySelector('.bulk-actions');
    const selectedCount = document.getElementById('selectedCount');
    const count = templateSelectionState.size;

    if (bulkActions && selectedCount) {
        selectedCount.textContent = `${count}개 선택됨`;
        if (count > 0) {
            bulkActions.style.display = 'flex';
        } else {
            bulkActions.style.display = 'none';
        }
    }

    // Update select all checkbox state
    const selectAllCheckbox = document.getElementById('selectAllTemplates');
    const templates = getWorkAreaTemplates();
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = templates.length > 0 && count === templates.length;
    }
}

/**
 * Handle select all templates
 */
function handleSelectAllTemplates(checked) {
    const checkboxes = document.querySelectorAll('.template-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checked;
        const id = cb.dataset.id;
        if (checked) {
            templateSelectionState.add(id);
        } else {
            templateSelectionState.delete(id);
        }
    });
    updateBulkActionButtons();
}

/**
 * Handle bulk create work areas
 */
function handleBulkCreateWorkAreas() {
    if (templateSelectionState.size === 0) return;

    const templates = getWorkAreaTemplatesMap();
    const selectedIds = Array.from(templateSelectionState);

    // Sort selected templates by name to maintain order
    const selectedTemplates = selectedIds
        .map(id => templates[id])
        .filter(t => t)
        .sort((a, b) => a.name.localeCompare(b.name, 'ko'));

    // Check if the first work area is empty (initial state)
    // If so, remove it so we start from 1
    if (appState.workAreas.length === 1) {
        const firstWorkArea = appState.workAreas[0];
        // Check if name is empty and no photos
        if ((!firstWorkArea.name || firstWorkArea.name.trim() === '') &&
            (!firstWorkArea.photos || firstWorkArea.photos.length === 0)) {

            // Remove from appState
            appState.workAreas = [];

            // Clear container
            const container = document.getElementById('workAreasContainer');
            if (container) container.innerHTML = '';
        }
    }

    // Create work areas
    selectedTemplates.forEach(template => {
        const workAreaId = generateId();
        const workAreaNumber = appState.workAreas.length + 1;

        const workArea = {
            id: workAreaId,
            name: template.name,
            workDescription: '',
            photos: []
        };

        appState.workAreas.push(workArea);
        renderWorkArea(workArea, workAreaNumber);
    });

    updateGenerateButton();

    // Close modal and show message
    const modal = document.getElementById('templateManagementModal');
    if (modal) modal.classList.add('hidden');

    showStatus(`${selectedTemplates.length}개의 작업장이 추가되었습니다.`, 'success');
}

/**
 * Handle edit template
 * @param {string} id - Template ID
 * @param {string} currentName - Current template name
 */
function handleEditTemplate(id, currentName) {
    const newName = prompt('템플릿 이름을 수정하세요:', currentName);
    if (!newName || newName.trim() === '') {
        return;
    }

    try {
        updateWorkAreaTemplate(id, newName.trim());
        renderTemplatesList();
        refreshAllTemplateSelectors();
        showStatus('템플릿이 수정되었습니다.', 'success');
    } catch (error) {
        console.error('Error updating template:', error);
        showStatus('템플릿 수정 중 오류가 발생했습니다.', 'error');
    }
}

/**
 * Handle delete template
 * @param {string} id - Template ID
 */
function handleDeleteTemplate(id) {
    if (!confirm('이 템플릿을 삭제하시겠습니까?')) {
        return;
    }

    try {
        deleteWorkAreaTemplate(id);
        renderTemplatesList();
        refreshAllTemplateSelectors();
        showStatus('템플릿이 삭제되었습니다.', 'success');
    } catch (error) {
        console.error('Error deleting template:', error);
        showStatus('템플릿 삭제 중 오류가 발생했습니다.', 'error');
    }
}


/**
 * Initialize app when DOM is ready
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
