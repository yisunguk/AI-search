/**
 * Utility Functions
 * Helper functions used throughout the application
 */

/**
 * Format date to ISO string (YYYY-MM-DD)
 * @param {Date} date - Date object
 * @returns {string} Formatted date string
 */
function formatDate(date) {
    if (!(date instanceof Date) || isNaN(date)) {
        date = new Date();
    }

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');

    return `${year}-${month}-${day}`;
}

/**
 * Format date to Korean string (YYYY년 MM월 DD일)
 * @param {Date} date - Date object
 * @returns {string} Formatted date string
 */
function formatDateKorean(date) {
    if (!(date instanceof Date) || isNaN(date)) {
        date = new Date();
    }

    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();

    return `${year}년 ${month}월 ${day}일`;
}

/**
 * Format date and time to Korean string
 * @param {Date} date - Date object
 * @returns {string} Formatted datetime string
 */
function formatDateTime(date) {
    if (!(date instanceof Date) || isNaN(date)) {
        date = new Date();
    }

    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');

    return `${year}년 ${month}월 ${day}일 ${hours}:${minutes}`;
}

/**
 * Resize image to fit within max dimensions
 * @param {string} dataUrl - Image data URL
 * @param {number} maxWidth - Maximum width
 * @param {number} maxHeight - Maximum height
 * @returns {Promise<string>} Resized image data URL
 */
function resizeImage(dataUrl, maxWidth = 800, maxHeight = 600) {
    return new Promise((resolve, reject) => {
        const img = new Image();

        img.onload = function () {
            let width = img.width;
            let height = img.height;

            // Calculate new dimensions
            if (width > maxWidth || height > maxHeight) {
                const aspectRatio = width / height;

                if (width > height) {
                    width = maxWidth;
                    height = width / aspectRatio;
                } else {
                    height = maxHeight;
                    width = height * aspectRatio;
                }
            }

            // Create canvas and draw resized image
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;

            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);

            resolve(canvas.toDataURL('image/jpeg', 0.9));
        };

        img.onerror = function () {
            reject(new Error('Failed to load image'));
        };

        img.src = dataUrl;
    });
}

/**
 * Generate unique ID
 * @returns {string} Unique ID
 */
function generateId() {
    return `id_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Sanitize filename
 * @param {string} filename - Original filename
 * @returns {string} Sanitized filename
 */
function sanitizeFilename(filename) {
    return filename
        .replace(/[^a-zA-Z0-9가-힣._-]/g, '_')
        .replace(/_{2,}/g, '_');
}

/**
 * Show status message
 * @param {string} message - Message to display
 * @param {string} type - Message type ('success' or 'error')
 * @param {number} duration - Duration to show message (ms)
 */
function showStatus(message, type = 'success', duration = 5000) {
    const statusEl = document.getElementById('statusMessage');

    if (statusEl) {
        statusEl.textContent = message;
        statusEl.className = `status-message ${type}`;

        setTimeout(() => {
            statusEl.className = 'status-message';
        }, duration);
    }
}

/**
 * Show loading overlay
 * @param {boolean} show - Whether to show or hide
 */
function showLoading(show = true) {
    const overlay = document.getElementById('loadingOverlay');

    if (overlay) {
        if (show) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }
}

/**
 * Validate image file
 * @param {File} file - File to validate
 * @returns {boolean} Whether file is valid
 */
function isValidImageFile(file) {
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (!validTypes.includes(file.type)) {
        return false;
    }

    if (file.size > maxSize) {
        return false;
    }

    return true;
}

/**
 * Read file as data URL
 * @param {File} file - File to read
 * @returns {Promise<string>} File data URL
 */
function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = function (e) {
            resolve(e.target.result);
        };

        reader.onerror = function () {
            reject(new Error('Failed to read file'));
        };

        reader.readAsDataURL(file);
    });
}

/**
 * Download file
 * @param {Blob} blob - File blob
 * @param {string} filename - Filename
 */
function downloadFile(blob, filename) {
    // Debugging: Check actual filename
    console.log('Download filename:', filename);

    // 1) Support for IE/Edge (msSaveOrOpenBlob)
    if (window.navigator && window.navigator.msSaveOrOpenBlob) {
        window.navigator.msSaveOrOpenBlob(blob, filename);
        return;
    }

    // 2) Standard Browsers
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename || 'download.xlsx';

    document.body.appendChild(a);

    // Use MouseEvent for better compatibility
    const clickEvent = new MouseEvent('click', {
        view: window,
        bubbles: true,
        cancelable: true
    });
    a.dispatchEvent(clickEvent);

    setTimeout(() => {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }, 100);
}

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
function debounce(func, wait = 300) {
    let timeout;

    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };

        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
