/**
 * File Handler
 * Handle file uploads, drag & drop, and preview generation
 */

/**
 * Initialize file upload handlers for a work area
 * @param {HTMLElement} workAreaCard - Work area card element
 * @param {Function} onFilesAdded - Callback when files are added
 */
function initializeFileHandlers(workAreaCard, onFilesAdded) {
    const uploadZone = workAreaCard.querySelector('.upload-zone');
    const fileInput = workAreaCard.querySelector('.file-input');

    if (!uploadZone || !fileInput) {
        console.error('Upload zone or file input not found');
        return;
    }

    // Click to upload
    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });

    // File input change
    fileInput.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files);
        await handleFiles(files, workAreaCard, onFilesAdded);
        fileInput.value = ''; // Reset input
    });

    // Drag and drop
    uploadZone.addEventListener('dragover', handleDragOver);
    uploadZone.addEventListener('dragleave', handleDragLeave);
    uploadZone.addEventListener('drop', async (e) => {
        handleDragLeave(e);
        const files = Array.from(e.dataTransfer.files);
        await handleFiles(files, workAreaCard, onFilesAdded);
    });

    // Prevent default drag behaviors on the entire document
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        document.addEventListener(eventName, preventDefaults, false);
    });
}

/**
 * Prevent default drag behaviors
 * @param {Event} e - Event object
 */
function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

/**
 * Handle drag over event
 * @param {DragEvent} e - Drag event
 */
function handleDragOver(e) {
    preventDefaults(e);
    e.currentTarget.classList.add('drag-over');
}

/**
 * Handle drag leave event
 * @param {DragEvent} e - Drag event
 */
function handleDragLeave(e) {
    preventDefaults(e);
    e.currentTarget.classList.remove('drag-over');
}

/**
 * Handle uploaded files
 * @param {File[]} files - Array of files
 * @param {HTMLElement} workAreaCard - Work area card element
 * @param {Function} onFilesAdded - Callback when files are added
 */
async function handleFiles(files, workAreaCard, onFilesAdded) {
    const validFiles = files.filter(file => {
        if (!isValidImageFile(file)) {
            console.warn(`Invalid file: ${file.name}`);
            return false;
        }
        return true;
    });

    if (validFiles.length === 0) {
        showStatus('유효한 이미지 파일이 없습니다.', 'error');
        return;
    }

    if (validFiles.length !== files.length) {
        const invalidCount = files.length - validFiles.length;
        showStatus(`${invalidCount}개의 파일이 유효하지 않아 제외되었습니다.`, 'error');
    }

    // Process files
    const processedFiles = [];

    for (const file of validFiles) {
        try {
            const photoData = await processImageFile(file);
            processedFiles.push(photoData);
        } catch (error) {
            console.error(`Error processing file ${file.name}:`, error);
        }
    }

    if (processedFiles.length > 0) {
        onFilesAdded(processedFiles);
        showStatus(`${processedFiles.length}개의 사진이 추가되었습니다.`, 'success');
    }
}

/**
 * Process image file
 * @param {File} file - Image file
 * @returns {Promise<Object>} Processed photo data
 */
async function processImageFile(file) {
    // Read file as data URL
    const dataUrl = await readFileAsDataURL(file);

    // Get EXIF date
    const photoDate = await getPhotoDate(file);

    // Generate thumbnail
    const thumbnail = await resizeImage(dataUrl, 300, 300);

    return {
        id: generateId(),
        name: file.name,
        file: file,
        dataUrl: dataUrl,
        thumbnail: thumbnail,
        date: photoDate,
        size: file.size
    };
}

/**
 * Create photo card element
 * @param {Object} photoData - Photo data object
 * @param {Function} onRemove - Callback when photo is removed
 * @returns {HTMLElement} Photo card element
 */
function createPhotoCard(photoData, onRemove) {
    const card = document.createElement('div');
    card.className = 'photo-card fade-in';
    card.dataset.photoId = photoData.id;

    const img = document.createElement('img');
    img.src = photoData.thumbnail;
    img.alt = photoData.name;
    img.loading = 'lazy';

    const info = document.createElement('div');
    info.className = 'photo-info';
    info.textContent = formatDate(photoData.date);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'photo-remove';
    removeBtn.innerHTML = '×';
    removeBtn.title = '사진 제거';
    removeBtn.onclick = (e) => {
        e.stopPropagation();
        card.remove();
        onRemove(photoData.id);
    };

    card.appendChild(img);
    card.appendChild(info);
    card.appendChild(removeBtn);

    return card;
}

/**
 * Update photo grid display
 * @param {HTMLElement} container - Container element
 * @param {Object[]} photos - Array of photo data
 * @param {Function} onRemove - Callback when photo is removed
 */
function updatePhotoGrid(container, photos, onRemove) {
    // Clear existing photos
    container.innerHTML = '';

    if (photos.length === 0) {
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        emptyState.innerHTML = `
            <div class="empty-state-icon">📷</div>
            <p class="empty-state-text">아직 사진이 없습니다</p>
        `;
        container.appendChild(emptyState);
        return;
    }

    // Add photo cards
    photos.forEach(photo => {
        const photoCard = createPhotoCard(photo, onRemove);
        container.appendChild(photoCard);
    });
}

/**
 * Sort photos by date
 * @param {Object[]} photos - Array of photo data
 * @returns {Object[]} Sorted photos
 */
function sortPhotosByDate(photos) {
    return [...photos].sort((a, b) => {
        return a.date.getTime() - b.date.getTime();
    });
}

/**
 * Get file size in human readable format
 * @param {number} bytes - File size in bytes
 * @returns {string} Human readable size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}
