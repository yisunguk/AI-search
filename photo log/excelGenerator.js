/**
 * Excel Generator (SheetJS 버전)
 * - 사진 4장(2x2) 카드 레이아웃
 * - 가로방향(landscape) 페이지 설정
 * - SheetJS 무료판이라 실제 이미지는 못 넣고, 자리표시 텍스트만 넣음
 */

/** 페이지/카드 레이아웃 설정 */
const TEMPLATE_CONFIG = {
    cardHeightRows: 22,      // 카드 한 줄(위/아래) 높이
    cardWidthCols: 13,       // 왼쪽/오른쪽 카드 폭 (대략)
    left: {
        photoCell: 'C4',     // 왼쪽 위 사진 셀 기준
        siteCell: 'C16',     // 현장명 값 셀
        locationCell: 'C17', // 위치 값 셀
        contentCell: 'C18',  // 내용 값 셀
        dateCell: 'J17'      // 일시 값 셀
    },
    right: {
        photoCell: 'P4',     // 오른쪽 위 사진 셀 기준
        siteCell: 'P16',
        locationCell: 'P17',
        contentCell: 'P18',
        dateCell: 'W17'
    },
    maxPhotoWidth: 350
};

const CARDS_PER_PAGE = 4; // 페이지당 4장(2x2)

/** 셀 주소에 행 offset 적용 (예: C4 + 22행 -> C26) */
function shiftCellAddress(cell, rowOffset) {
    const match = cell.match(/^([A-Z]+)(\d+)$/);
    if (!match) return cell;
    const col = match[1];
    const row = parseInt(match[2], 10) + rowOffset;
    return `${col}${row}`;
}

/** 시트에서 최대 사용 행 갱신용 */
function updateMaxRow(maxRow, cellAddress) {
    const match = cellAddress.match(/^([A-Z]+)(\d+)$/);
    if (!match) return maxRow;
    const row = parseInt(match[2], 10);
    return Math.max(maxRow, row);
}

/**
 * 카드 1장(사진+텍스트)을 시트에 배치
 * - cardIndex: 0,1,2,3,4,... (페이지/위치 계산용)
 */
function addPhotoCard(ws, photo, cardIndex, projectName, areaName) {
    const cfg = TEMPLATE_CONFIG;
    const cardHeight = cfg.cardHeightRows;
    const cardsPerPage = CARDS_PER_PAGE;

    // 1) 이 카드가 몇 번째 페이지인지
    const pageIdx = Math.floor(cardIndex / cardsPerPage); // 0,1,2,...

    // 2) 페이지 안에서 몇 번째 카드인지 (0~3)
    const idxInPage = cardIndex % cardsPerPage;

    // 3) 페이지 안 위치 (위/아래 + 좌/우)
    let side;      // 'left' / 'right'
    let rowInPage; // 0 = 위, 1 = 아래

    if (idxInPage === 0) {        // 왼쪽 위
        side = 'left';
        rowInPage = 0;
    } else if (idxInPage === 1) { // 오른쪽 위
        side = 'right';
        rowInPage = 0;
    } else if (idxInPage === 2) { // 왼쪽 아래
        side = 'left';
        rowInPage = 1;
    } else {                      // 3: 오른쪽 아래
        side = 'right';
        rowInPage = 1;
    }

    // 4) 페이지 높이 (카드 2줄 + 여백 2줄 정도)
    const pageHeightRows = cardHeight * 2 + 2;

    // 5) 실제 행 offset 계산
    const baseOffset =
        pageIdx * pageHeightRows   // 페이지 아래로
        + rowInPage * cardHeight;  // 페이지 안에서 위/아래

    // 6) 셀 위치 계산
    const photoCell = shiftCellAddress(cfg[side].photoCell, baseOffset);
    const siteCell = shiftCellAddress(cfg[side].siteCell, baseOffset);
    const locationCell = shiftCellAddress(cfg[side].locationCell, baseOffset);
    const contentCell = shiftCellAddress(cfg[side].contentCell, baseOffset);
    const dateCell = shiftCellAddress(cfg[side].dateCell, baseOffset);

    // 굵은 테두리 스타일
    const thickBorder = {
        top: { style: 'medium' },
        bottom: { style: 'medium' },
        left: { style: 'medium' },
        right: { style: 'medium' }
    };

    // 7) 사진 자리 (실제 이미지는 X, 텍스트 placeholder)
    ws[photoCell] = {
        t: 's',
        v: `[사진: ${photo.name || ''}]`,
        s: {
            alignment: { horizontal: 'center', vertical: 'center', wrapText: true },
            border: thickBorder
        }
    };

    // 간단히 사진 영역 아래쪽까지 행 높이를 대충 맞추고 싶으면 rowDimensions 쓰면 되지만
    // SheetJS에서는 스타일만 두고 실제 인쇄 비율은 사용자가 조정.

    // 8) 필드 넣기용 헬퍼 (라벨+값)
    const addField = (valueCell, labelText, valueText) => {
        // 라벨은 valueCell의 왼쪽 셀로 가정
        const match = valueCell.match(/^([A-Z]+)(\d+)$/);
        if (!match) return;

        const col = match[1];
        const row = parseInt(match[2], 10);
        const labelCol = String.fromCharCode(col.charCodeAt(0) - 1); // 한 칸 왼쪽

        const labelCell = `${labelCol}${row}`;

        ws[labelCell] = {
            t: 's',
            v: labelText,
            s: {
                font: { bold: true },
                alignment: { horizontal: 'center', vertical: 'center' },
                fill: { fgColor: { rgb: "E0E0E0" } },
                border: thickBorder
            }
        };

        ws[valueCell] = {
            t: 's',
            v: valueText || '',
            s: {
                alignment: { horizontal: 'left', vertical: 'center' },
                border: thickBorder
            }
        };
    };

    const dateString = photo.date || '';
    const location = photo.location || areaName || '';
    const content = photo.description || '';
    const siteName = projectName || areaName || '';

    addField(siteCell, '현장명', siteName);
    addField(locationCell, '위치', location);
    addField(contentCell, '내용', content);
    addField(dateCell, '일시', dateString || '');
}

/** 작업장별 시트 생성 */
function createWorksheet(photos, projectName, areaName) {
    const ws = {};

    // 가로방향 인쇄 설정
    ws['!pageSetup'] = {
        orientation: "landscape",
        paperSize: 9,   // A4
        fitToWidth: 1,
        fitToHeight: 0
    };

    // 열 너비 (대충 사진 들어갈 정도로 넓게)
    ws['!cols'] = [
        { wch: 3 },  // A
        { wch: 3 },  // B
        { wch: 14 }, // C
        { wch: 14 }, // D
        { wch: 14 }, // E
        { wch: 14 }, // F
        { wch: 14 }, // G
        { wch: 3 },  // H
        { wch: 14 }, // I
        { wch: 14 }, // J
        { wch: 14 }, // K
        { wch: 3 },  // L
        { wch: 3 },  // M
        { wch: 14 }, // N / P 쪽 맞추기용
        { wch: 14 },
        { wch: 14 },
        { wch: 14 },
        { wch: 14 },
        { wch: 14 },
        { wch: 3 },
        { wch: 14 },
        { wch: 14 },
        { wch: 14 },
        { wch: 3 },
        { wch: 3 }
    ];

    let maxRow = 1;

    // 제목 정도만 상단에 넣고 싶으면 여기서 추가해도 됨
    ws['C1'] = {
        t: 's',
        v: projectName ? `${projectName} - 사진대지` : '사진대지',
        s: {
            font: { bold: true, sz: 16 },
            alignment: { horizontal: 'center', vertical: 'center' }
        }
    };
    maxRow = updateMaxRow(maxRow, 'C1');

    // 사진 카드들 배치
    photos.forEach((photo, idx) => {
        addPhotoCard(ws, photo, idx, projectName, areaName);

        // 대충 많이 내려간다고 보고, 페이지 수에 따라 최대 행 추정
        const pageIdx = Math.floor(idx / CARDS_PER_PAGE);
        const rowInPage = (idx % CARDS_PER_PAGE) < 2 ? 0 : 1;
        const approximateRow = 4 + pageIdx * (TEMPLATE_CONFIG.cardHeightRows * 2 + 2)
            + rowInPage * TEMPLATE_CONFIG.cardHeightRows
            + TEMPLATE_CONFIG.cardHeightRows;
        if (approximateRow > maxRow) maxRow = approximateRow;
    });

    // 시트 범위 설정
    ws['!ref'] = `A1:Z${maxRow || 50}`;

    return ws;
}

/** 전체 워크북 생성 (SheetJS) */
function generateExcel(workAreas, projectName) {
    const wb = XLSX.utils.book_new();

    Object.entries(workAreas).forEach(([areaName, photos]) => {
        if (!photos || photos.length === 0) return;

        const ws = createWorksheet(photos, projectName, areaName);

        // 시트 이름은 31자 제한
        let sheetName = areaName || '작업장';
        if (sheetName.length > 31) sheetName = sheetName.slice(0, 31);

        XLSX.utils.book_append_sheet(wb, ws, sheetName);
    });

    return wb;
}

/** Excel 파일 생성 + 다운로드 (app.js에서 이 함수 호출 중) */
async function downloadExcelFile(workAreas, projectName) {
    try {
        showLoading(true);
        showStatus('Excel 생성 중...', 'info');

        const wb = generateExcel(workAreas, projectName);

        const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
        const blob = new Blob(
            [wbout],
            { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }
        );

        const timestamp = formatDate(new Date()).replace(/-/g, '');
        const baseName = sanitizeFilename(`${projectName || '사진대지'}_${timestamp}`);
        const filename = `${baseName}.xlsx`;

        downloadFile(blob, filename);

        showLoading(false);
        showStatus('Excel 파일이 생성되었습니다!', 'success');
    } catch (error) {
        console.error('Error downloading Excel:', error);
        showLoading(false);
        showStatus('Excel 파일 생성 중 오류가 발생했습니다.', 'error');
    }
}
