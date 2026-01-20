/**
 * Storage Manager
 * Handle saving and loading work data using localStorage
 */

const STORAGE_KEY = 'photo_layout_work_data';
const TEMPLATE_STORAGE_KEY = 'photo_layout_work_templates';
const STORAGE_VERSION = '1.0';

/**
 * Save work data to localStorage
 * @param {Object} workData - Work data to save
 * @returns {boolean} Success status
 */
/**
 * Save work data to localStorage
 * @param {Object} workData - Work data to save
 * @param {string} saveName - Name for the save slot
 * @returns {boolean} Success status
 */
function saveWorkData(workData, saveName) {
    try {
        const saves = getSavedWorksMap();
        const id = generateId();

        const dataToSave = {
            id: id,
            name: saveName || workData.projectName || '(이름 없음)',
            version: STORAGE_VERSION,
            timestamp: new Date().toISOString(),
            projectName: workData.projectName,
            workAreas: workData.workAreas.map(wa => ({
                id: wa.id,
                name: wa.name,
                workDescription: wa.workDescription,
                photos: wa.photos.map(photo => ({
                    id: photo.id,
                    name: photo.name,
                    dataUrl: photo.dataUrl,
                    thumbnail: photo.thumbnail,
                    date: photo.date.toISOString(),
                    size: photo.size
                }))
            }))
        };

        // Calculate size
        const jsonString = JSON.stringify(dataToSave);
        const sizeInMB = new Blob([jsonString]).size / 1024 / 1024;

        if (sizeInMB > 8) {
            throw new Error('저장 데이터가 너무 큽니다. 사진 수를 줄여주세요.');
        }

        // Add to saves map
        saves[id] = dataToSave;

        // Save back to localStorage
        localStorage.setItem(STORAGE_KEY, JSON.stringify(saves));

        console.log(`Work data saved successfully (${sizeInMB.toFixed(2)} MB)`);
        return true;
    } catch (error) {
        console.error('Error saving work data:', error);
        if (error.name === 'QuotaExceededError') {
            throw new Error('저장 공간이 부족합니다. 브라우저의 저장 공간을 확인해주세요.');
        }
        throw error;
    }
}

/**
 * Get all saved works map
 * @returns {Object} Map of saved works
 */
function getSavedWorksMap() {
    try {
        const jsonString = localStorage.getItem(STORAGE_KEY);
        if (!jsonString) return {};

        // Handle migration from old single-save format
        const data = JSON.parse(jsonString);
        if (data.version && !data.id) {
            // Old format, wrap in new structure
            const id = generateId();
            const saves = {};
            saves[id] = { ...data, id: id, name: data.projectName || '(이전 작업)' };
            return saves;
        }

        return data;
    } catch (error) {
        console.error('Error getting saved works:', error);
        return {};
    }
}

/**
 * Get list of saved works metadata
 * @returns {Array} List of saved works info
 */
function getSavedWorksList() {
    const saves = getSavedWorksMap();
    return Object.values(saves).map(save => ({
        id: save.id,
        name: save.name,
        projectName: save.projectName,
        timestamp: new Date(save.timestamp),
        photoCount: save.workAreas.reduce((sum, wa) => sum + wa.photos.length, 0),
        size: (new Blob([JSON.stringify(save)]).size / 1024 / 1024).toFixed(2)
    })).sort((a, b) => b.timestamp - a.timestamp);
}

/**
 * Load specific work data
 * @param {string} id - Save ID
 * @returns {Object|null} Loaded work data
 */
function loadWorkData(id) {
    try {
        const saves = getSavedWorksMap();
        const data = saves[id];

        if (!data) return null;

        // Convert date strings back to Date objects
        data.workAreas.forEach(wa => {
            wa.photos.forEach(photo => {
                photo.date = new Date(photo.date);
            });
        });

        return data;
    } catch (error) {
        console.error('Error loading work data:', error);
        throw new Error('저장된 데이터를 불러오는 중 오류가 발생했습니다.');
    }
}

/**
 * Delete saved work
 * @param {string} id - Save ID
 */
function deleteWorkData(id) {
    try {
        const saves = getSavedWorksMap();
        if (saves[id]) {
            delete saves[id];
            localStorage.setItem(STORAGE_KEY, JSON.stringify(saves));
            return true;
        }
        return false;
    } catch (error) {
        console.error('Error deleting work data:', error);
        throw error;
    }
}

/**
 * Export work data as JSON file
 * @param {Object} workData - Work data to export
 * @param {string} filename - Filename for export
 */
function exportWorkDataAsFile(workData, filename) {
    try {
        const dataToSave = {
            version: STORAGE_VERSION,
            timestamp: new Date().toISOString(),
            projectName: workData.projectName,
            workAreas: workData.workAreas.map(wa => ({
                id: wa.id,
                name: wa.name,
                workDescription: wa.workDescription,
                photos: wa.photos.map(photo => ({
                    id: photo.id,
                    name: photo.name,
                    dataUrl: photo.dataUrl,
                    thumbnail: photo.thumbnail,
                    date: photo.date.toISOString(),
                    size: photo.size
                }))
            }))
        };

        const jsonString = JSON.stringify(dataToSave, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });

        downloadFile(blob, filename);

        return true;
    } catch (error) {
        console.error('Error exporting work data:', error);
        throw error;
    }
}

/**
 * Import work data from JSON file
 * @param {File} file - JSON file to import
 * @returns {Promise<Object>} Imported work data
 */
function importWorkDataFromFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = function (e) {
            try {
                const data = JSON.parse(e.target.result);

                // Convert date strings back to Date objects
                data.workAreas.forEach(wa => {
                    wa.photos.forEach(photo => {
                        photo.date = new Date(photo.date);
                    });
                });

                resolve(data);
            } catch (error) {
                reject(new Error('잘못된 파일 형식입니다.'));
            }
        };

        reader.onerror = function () {
            reject(new Error('파일을 읽는 중 오류가 발생했습니다.'));
        };

        reader.readAsText(file);
    });
}

/**
 * ============================================
 * WORK AREA TEMPLATE MANAGEMENT
 * ============================================
 */

/**
 * Save work area template
 * @param {string} templateName - Name of the template
 * @returns {Object} Saved template object
 */
function saveWorkAreaTemplate(templateName) {
    try {
        const templates = getWorkAreaTemplatesMap();
        const id = generateId();

        const template = {
            id: id,
            name: templateName.trim(),
            timestamp: new Date().toISOString()
        };

        templates[id] = template;
        localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(templates));

        console.log('Template saved:', template);
        return template;
    } catch (error) {
        console.error('Error saving template:', error);
        throw new Error('템플릿 저장 중 오류가 발생했습니다.');
    }
}

/**
 * Get all work area templates as map
 * @returns {Object} Map of templates
 */
function getWorkAreaTemplatesMap() {
    try {
        const jsonString = localStorage.getItem(TEMPLATE_STORAGE_KEY);
        if (!jsonString) return {};
        return JSON.parse(jsonString);
    } catch (error) {
        console.error('Error getting templates:', error);
        return {};
    }
}

/**
 * Get all work area templates as array
 * @returns {Array} Array of template objects
 */
function getWorkAreaTemplates() {
    const templates = getWorkAreaTemplatesMap();
    return Object.values(templates).sort((a, b) =>
        a.name.localeCompare(b.name, 'ko')
    );
}

/**
 * Update work area template
 * @param {string} id - Template ID
 * @param {string} newName - New template name
 * @returns {boolean} Success status
 */
function updateWorkAreaTemplate(id, newName) {
    try {
        const templates = getWorkAreaTemplatesMap();
        if (!templates[id]) {
            throw new Error('템플릿을 찾을 수 없습니다.');
        }

        templates[id].name = newName.trim();
        templates[id].timestamp = new Date().toISOString();

        localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(templates));
        console.log('Template updated:', templates[id]);
        return true;
    } catch (error) {
        console.error('Error updating template:', error);
        throw error;
    }
}

/**
 * Delete work area template
 * @param {string} id - Template ID
 * @returns {boolean} Success status
 */
function deleteWorkAreaTemplate(id) {
    try {
        const templates = getWorkAreaTemplatesMap();
        if (!templates[id]) {
            return false;
        }

        delete templates[id];
        localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(templates));
        console.log('Template deleted:', id);
        return true;
    } catch (error) {
        console.error('Error deleting template:', error);
        throw new Error('템플릿 삭제 중 오류가 발생했습니다.');
    }
}

