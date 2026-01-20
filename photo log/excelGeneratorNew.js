/**
 * Excel Generator using ExcelJS - Landscape 2x2 Grid
 * 4 cards per page (2x2 grid) on landscape A4
 */

/**
 * Generate Excel file with 2x2 grid layout
 * @param {Object} workAreasData - Work areas data object
 * @param {string} projectName - Project name
 * @returns {Promise<Blob>} Excel file blob
 */
async function generateExcelWithImages(workAreasData, projectName = '') {
    try {
        const ExcelJS = window.ExcelJS;
        const workbook = new ExcelJS.Workbook();

        // Process each work area
        for (const [areaName, photos] of Object.entries(workAreasData)) {
            if (photos.length === 0) continue;

            // Sort photos by date
            const sortedPhotos = sortPhotosByDate(photos);

            // Create worksheet
            const worksheet = workbook.addWorksheet(sanitizeSheetName(areaName));

            // LANDSCAPE orientation
            worksheet.pageSetup = { orientation: 'landscape', paperSize: 9, fitToPage: true };

            // Set column widths for 2 columns of cards
            worksheet.getColumn(1).width = 3;   // Left margin
            worksheet.getColumn(2).width = 45;  // Left card column
            worksheet.getColumn(3).width = 3;   // Center gap
            worksheet.getColumn(4).width = 45;  // Right card column
            worksheet.getColumn(5).width = 3;   // Right margin

            let currentRow = 1;

            // Add photos in 2x2 grid (4 per page)
            for (let i = 0; i < sortedPhotos.length; i += 4) {
                // Top row (2 cards)
                const topLeft = sortedPhotos[i];
                const topRight = sortedPhotos[i + 1];

                if (topLeft) {
                    await addGridPhotoCard(worksheet, topLeft, currentRow, 2, projectName, areaName);
                }
                if (topRight) {
                    await addGridPhotoCard(worksheet, topRight, currentRow, 4, projectName, areaName);
                }

                currentRow += 38; // Card height

                // Bottom row (2 cards)
                const bottomLeft = sortedPhotos[i + 2];
                const bottomRight = sortedPhotos[i + 3];

                if (bottomLeft) {
                    await addGridPhotoCard(worksheet, bottomLeft, currentRow, 2, projectName, areaName);
                }
                if (bottomRight) {
                    await addGridPhotoCard(worksheet, bottomRight, currentRow, 4, projectName, areaName);
                }

                currentRow += 38 + 2; // Next page with gap
            }
        }

        // Generate Excel file
        const buffer = await workbook.xlsx.writeBuffer();
        return new Blob([buffer], {
            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        });
    } catch (error) {
        console.error('Error generating Excel with images:', error);
        throw error;
    }
}

/**
 * Add a photo card in 2x2 grid
 * @param {Object} worksheet - ExcelJS worksheet
 * @param {Object} photo - Photo data
 * @param {number} startRow - Starting row (1-indexed)
 * @param {number} startCol - Starting column (2 or 4)
 * @param {string} projectName - Project name
 * @param {string} areaName - Area name
 */
async function addGridPhotoCard(worksheet, photo, startRow, startCol, projectName, areaName) {
    const cardHeight = 37;

    // Set row heights
    for (let i = 0; i < cardHeight; i++) {
        worksheet.getRow(startRow + i).height = 18;
    }

    // 1. HEADER: "사 진 대 지" with THICK border
    const headerCell = worksheet.getCell(startRow, startCol);
    headerCell.value = '사 진 대 지';
    headerCell.font = { size: 14, bold: true };
    headerCell.alignment = { horizontal: 'center', vertical: 'middle' };
    headerCell.border = {
        top: { style: 'medium' },
        left: { style: 'medium' },
        right: { style: 'medium' },
        bottom: { style: 'thin' }
    };
    worksheet.getRow(startRow).height = 22;

    // 2. IMAGE AREA (rows 2-24)
    try {
        const imageId = worksheet.workbook.addImage({
            base64: photo.dataUrl,
            extension: 'jpeg'
        });

        worksheet.addImage(imageId, {
            tl: { col: startCol - 1, row: startRow + 1 },
            br: { col: startCol, row: startRow + 23 }
        });
    } catch (error) {
        console.error('Error adding image:', error);
        const imgCell = worksheet.getCell(startRow + 12, startCol);
        imgCell.value = `[사진: ${photo.name}]`;
        imgCell.alignment = { horizontal: 'center', vertical: 'middle' };
    }

    // 3. INFO BOX (rows 24-29)
    const infoStartRow = startRow + 23;

    const infoData = [
        { label: '공사명', value: projectName || areaName },
        { label: '공 종', value: '철근콘크리트 공사' },
        { label: '위 치', value: areaName },
        { label: '내 용', value: photo.name },
        { label: '일 자', value: formatDate(photo.date) }
    ];

    for (let i = 0; i < infoData.length; i++) {
        const row = infoStartRow + i;
        const cell = worksheet.getCell(row, startCol);

        cell.value = `${infoData[i].label}  ${infoData[i].value}`;
        cell.font = { size: 9 };
        cell.alignment = { horizontal: 'left', vertical: 'middle' };
        cell.border = {
            top: { style: 'thin' },
            left: { style: 'medium' },
            right: { style: 'medium' },
            bottom: { style: 'thin' }
        };
        worksheet.getRow(row).height = 16;
    }

    // 4. FOOTER (rows 30-36) with THICK bottom border
    const footerStartRow = startRow + 28;

    // Footer line 1: 공 종
    const footer1 = worksheet.getCell(footerStartRow, startCol);
    footer1.value = `공 종  철근콘크리트 공사`;
    footer1.font = { size: 9 };
    footer1.alignment = { horizontal: 'left', vertical: 'middle' };
    footer1.border = {
        left: { style: 'medium' },
        right: { style: 'medium' }
    };

    // Footer line 2: 내 용
    const footer2 = worksheet.getCell(footerStartRow + 1, startCol);
    footer2.value = `내 용  ${areaName}`;
    footer2.font = { size: 9 };
    footer2.alignment = { horizontal: 'left', vertical: 'middle' };
    footer2.border = {
        left: { style: 'medium' },
        right: { style: 'medium' }
    };

    // Footer line 3: 일 시 (with thick bottom border)
    const footer3 = worksheet.getCell(footerStartRow + 2, startCol);
    footer3.value = `일 시  ${formatDate(photo.date)}`;
    footer3.font = { size: 9 };
    footer3.alignment = { horizontal: 'right', vertical: 'middle' };
    footer3.border = {
        left: { style: 'medium' },
        right: { style: 'medium' },
        bottom: { style: 'medium' }
    };
}

/**
 * Download Excel file
 * @param {Object} workAreasData - Work areas data object
 * @param {string} projectName - Project name
 */
async function downloadExcelFile(workAreasData, projectName = '') {
    try {
        showLoading(true);

        // Generate Excel file with images
        const blob = await generateExcelWithImages(workAreasData, projectName);

        // Generate filename
        const timestamp = formatDate(new Date()).replace(/-/g, '');
        const baseName = sanitizeFilename(`${projectName || '사진대지'}_${timestamp}`);
        const filename = `${baseName}.xlsx`;

        // Download file
        downloadFile(blob, filename);

        showLoading(false);
        showStatus('Excel 파일이 생성되었습니다!', 'success');
    } catch (error) {
        console.error('Error downloading Excel:', error);
        showLoading(false);
        showStatus('Excel 파일 생성 중 오류가 발생했습니다.', 'error');
    }
}
