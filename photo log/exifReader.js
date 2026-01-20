/**
 * EXIF Data Reader
 * Extract EXIF metadata from images
 */

/**
 * Extract EXIF date from image
 * @param {File} file - Image file
 * @returns {Promise<Date>} Photo date
 */
function getPhotoDate(file) {
    return new Promise((resolve) => {
        const img = new Image();

        img.onload = function () {
            try {
                EXIF.getData(img, function () {
                    const dateTimeOriginal = EXIF.getTag(this, 'DateTimeOriginal');
                    const dateTime = EXIF.getTag(this, 'DateTime');

                    const exifDate = dateTimeOriginal || dateTime;

                    if (exifDate) {
                        // EXIF date format: "YYYY:MM:DD HH:MM:SS"
                        const date = parseExifDate(exifDate);

                        if (date && !isNaN(date)) {
                            resolve(date);
                            return;
                        }
                    }

                    // Fallback to file modification date
                    resolve(new Date(file.lastModified));
                });
            } catch (error) {
                console.error('Error reading EXIF data:', error);
                resolve(new Date(file.lastModified));
            }
        };

        img.onerror = function () {
            console.error('Error loading image for EXIF reading');
            resolve(new Date(file.lastModified));
        };

        // Load image from file
        const reader = new FileReader();
        reader.onload = function (e) {
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

/**
 * Parse EXIF date string to Date object
 * @param {string} exifDate - EXIF date string (format: "YYYY:MM:DD HH:MM:SS")
 * @returns {Date|null} Parsed date or null
 */
function parseExifDate(exifDate) {
    try {
        // EXIF format: "YYYY:MM:DD HH:MM:SS"
        const parts = exifDate.split(' ');

        if (parts.length !== 2) {
            return null;
        }

        const dateParts = parts[0].split(':');
        const timeParts = parts[1].split(':');

        if (dateParts.length !== 3 || timeParts.length !== 3) {
            return null;
        }

        const year = parseInt(dateParts[0], 10);
        const month = parseInt(dateParts[1], 10) - 1; // Month is 0-indexed
        const day = parseInt(dateParts[2], 10);
        const hours = parseInt(timeParts[0], 10);
        const minutes = parseInt(timeParts[1], 10);
        const seconds = parseInt(timeParts[2], 10);

        const date = new Date(year, month, day, hours, minutes, seconds);

        return isNaN(date) ? null : date;
    } catch (error) {
        console.error('Error parsing EXIF date:', error);
        return null;
    }
}

/**
 * Get all EXIF data from image
 * @param {File} file - Image file
 * @returns {Promise<Object>} EXIF data object
 */
function getAllExifData(file) {
    return new Promise((resolve) => {
        const img = new Image();

        img.onload = function () {
            try {
                EXIF.getData(img, function () {
                    const allData = EXIF.getAllTags(this);
                    resolve(allData);
                });
            } catch (error) {
                console.error('Error reading EXIF data:', error);
                resolve({});
            }
        };

        img.onerror = function () {
            console.error('Error loading image for EXIF reading');
            resolve({});
        };

        const reader = new FileReader();
        reader.onload = function (e) {
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

/**
 * Get camera make and model from EXIF
 * @param {File} file - Image file
 * @returns {Promise<Object>} Camera info object
 */
function getCameraInfo(file) {
    return new Promise((resolve) => {
        const img = new Image();

        img.onload = function () {
            try {
                EXIF.getData(img, function () {
                    const make = EXIF.getTag(this, 'Make');
                    const model = EXIF.getTag(this, 'Model');

                    resolve({
                        make: make || '',
                        model: model || ''
                    });
                });
            } catch (error) {
                console.error('Error reading camera info:', error);
                resolve({ make: '', model: '' });
            }
        };

        img.onerror = function () {
            console.error('Error loading image for camera info');
            resolve({ make: '', model: '' });
        };

        const reader = new FileReader();
        reader.onload = function (e) {
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

/**
 * Get GPS coordinates from EXIF
 * @param {File} file - Image file
 * @returns {Promise<Object|null>} GPS coordinates or null
 */
function getGPSData(file) {
    return new Promise((resolve) => {
        const img = new Image();

        img.onload = function () {
            try {
                EXIF.getData(img, function () {
                    const lat = EXIF.getTag(this, 'GPSLatitude');
                    const latRef = EXIF.getTag(this, 'GPSLatitudeRef');
                    const lon = EXIF.getTag(this, 'GPSLongitude');
                    const lonRef = EXIF.getTag(this, 'GPSLongitudeRef');

                    if (lat && lon) {
                        const latitude = convertDMSToDD(lat, latRef);
                        const longitude = convertDMSToDD(lon, lonRef);

                        resolve({ latitude, longitude });
                    } else {
                        resolve(null);
                    }
                });
            } catch (error) {
                console.error('Error reading GPS data:', error);
                resolve(null);
            }
        };

        img.onerror = function () {
            console.error('Error loading image for GPS data');
            resolve(null);
        };

        const reader = new FileReader();
        reader.onload = function (e) {
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

/**
 * Convert DMS (Degrees, Minutes, Seconds) to DD (Decimal Degrees)
 * @param {Array} dms - DMS array [degrees, minutes, seconds]
 * @param {string} ref - Reference (N, S, E, W)
 * @returns {number} Decimal degrees
 */
function convertDMSToDD(dms, ref) {
    const degrees = dms[0];
    const minutes = dms[1];
    const seconds = dms[2];

    let dd = degrees + (minutes / 60) + (seconds / 3600);

    if (ref === 'S' || ref === 'W') {
        dd = -dd;
    }

    return dd;
}
