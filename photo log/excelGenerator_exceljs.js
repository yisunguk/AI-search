/**
 * Excel Generator (ExcelJS + 이미지 버전)
 * - 실제 JPG/PNG 이미지를 엑셀에 삽입
 * - 1x2 (2장) 세로 카드 레이아웃 (보고서 형태)
 * - 세로방향(portrait)
 */

const EXCELJS_LAYOUT = {
    cardHeight: 22,    // 카드 한 개 높이 (이미지 17행 + 정보 4행 + 여백 1행)
    cardWidth: 1,      // 가로 1개
    topMargin: 2,      // 상단 여백 (제목 1행 + 간격 1행)
    gapBetweenCards: 0 // 사진대지 간 간격 (0행 - 바로 붙음)
};

/** ExcelJS에서 1x2 카드 위치 계산 */
function getExcelJsCardPosition(cardIndex) {
    const { cardHeight, topMargin, gapBetweenCards } = EXCELJS_LAYOUT;

    const pageIdx = Math.floor(cardIndex / 2);   // 페이지 번호 (0, 1, 2...)
    const idxInPage = cardIndex % 2;            // 페이지 내 index (0: 상단, 1: 하단)

    // 페이지당 2개의 카드
    const pageRowOffset = pageIdx * (cardHeight * 2 + 2); // 페이지 간 여백 2행

    const startRow = topMargin + pageRowOffset + (idxInPage * (cardHeight + gapBetweenCards));
    const startCol = 2; // B열부터 시작 (A열은 여백)

    return { startRow, startCol };
}

/** 사진 한 장을 카드로 추가 (ExcelJS) */
async function addExcelJsPhotoCard(workbook, worksheet, photo, cardIndex, projectName, areaName, areaDescription) {
    const pos = getExcelJsCardPosition(cardIndex);
    const { startRow, startCol } = pos;

    // 레이아웃 설정
    const IMAGE_WIDTH_COLS = 14; // 이미지 가로 점유 컬럼 수 (B~O)
    const IMAGE_HEIGHT_ROWS = 17; // 이미지 세로 점유 로우 수 (줄임)

    // 1) 이미지 추가
    if (photo.file instanceof File) {
        const buf = await photo.file.arrayBuffer();
        const ext = (photo.file.type || '').includes('png') ? 'png' : 'jpeg';

        const imageId = workbook.addImage({
            buffer: buf,
            extension: ext
        });

        worksheet.addImage(imageId, {
            tl: { col: startCol - 1, row: startRow - 1 },
            br: { col: startCol - 1 + IMAGE_WIDTH_COLS, row: startRow - 1 + IMAGE_HEIGHT_ROWS }
        });
    }

    // 2) 테두리 스타일
    const borderStyle = {
        top: { style: 'thin' },
        left: { style: 'thin' },
        bottom: { style: 'thin' },
        right: { style: 'thin' }
    };

    // 3) 텍스트 박스 영역 (이미지 바로 아래)
    const infoRowStart = startRow + IMAGE_HEIGHT_ROWS;

    // 공통 셀 설정 함수
    function setMergedCell(r, c, w, val, isLabel) {
        worksheet.mergeCells(r, c, r, c + w - 1);
        const cell = worksheet.getCell(r, c);
        cell.value = val;
        cell.border = borderStyle;
        cell.alignment = {
            vertical: 'middle',
            horizontal: isLabel ? 'center' : 'left',
            wrapText: true
        };
        cell.font = {
            size: 11,
            bold: isLabel
        };
        if (isLabel) {
            cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE0E0E0' } };
        }
    }

    const labelCols = 3; // 라벨이 차지할 컬럼 수
    const valCols = IMAGE_WIDTH_COLS - labelCols; // 값이 차지할 컬럼 수

    const dateString = photo.date || '';
    const location = photo.location || areaName || '';
    const content = areaDescription || photo.description || ''; // 작업내용 우선, 없으면 사진 설명
    const siteName = projectName || areaName || '';

    // 줄 1: 현장명
    setMergedCell(infoRowStart, startCol, labelCols, '현장명', true);
    setMergedCell(infoRowStart, startCol + labelCols, valCols, siteName, false);

    // 줄 2: 위치
    setMergedCell(infoRowStart + 1, startCol, labelCols, '위치', true);
    setMergedCell(infoRowStart + 1, startCol + labelCols, valCols, location, false);

    // 줄 3: 내용 (작업내용)
    setMergedCell(infoRowStart + 2, startCol, labelCols, '내용', true);
    setMergedCell(infoRowStart + 2, startCol + labelCols, valCols, content, false);

    // 줄 4: 일시
    setMergedCell(infoRowStart + 3, startCol, labelCols, '일시', true);
    setMergedCell(infoRowStart + 3, startCol + labelCols, valCols, dateString, false);
}

/** 작업장별 시트 생성 (ExcelJS) */
async function buildExcelJsSheet(workbook, areaName, photos, projectName, areaDescription) {
    const sheetName = (areaName || '작업장').slice(0, 31);
    const ws = workbook.addWorksheet(sheetName, {
        pageSetup: {
            orientation: 'portrait', // 세로 방향
            paperSize: 9, // A4
            fitToPage: true,
            fitToWidth: 1,
            fitToHeight: 0, // 자동 높이
            margins: {
                left: 0.5, right: 0.5,
                top: 0.5, bottom: 0.5,
                header: 0.3, footer: 0.3
            }
        }
    });

    // 열 너비 조정
    ws.getColumn(1).width = 2;

    for (let c = 2; c <= 15; c++) {
        ws.getColumn(c).width = 5.5;
    }

    // 제목 (맨 위)
    const title = projectName ? `${projectName} - 사진대지` : '사진대지';
    ws.mergeCells(1, 2, 1, 15);
    const titleCell = ws.getCell(1, 2);
    titleCell.value = title;
    titleCell.font = { bold: true, size: 20 };
    titleCell.alignment = { horizontal: 'center', vertical: 'middle' };
    titleCell.border = { bottom: { style: 'double' } };

    // 카드들 배치
    for (let i = 0; i < photos.length; i++) {
        await addExcelJsPhotoCard(workbook, ws, photos[i], i, projectName, areaName, areaDescription);
    }
}

/** ExcelJS로 실제 이미지 포함 엑셀 생성 + 다운로드 */
async function downloadExcelFileExcelJS(workAreas, projectName, workAreasData) {
    try {
        showLoading(true);
        showStatus('이미지 포함 Excel 생성 중...', 'info');

        const workbook = new ExcelJS.Workbook();

        for (const [areaName, photos] of Object.entries(workAreas)) {
            if (!photos || photos.length === 0) continue;
            // workAreasData에서 해당 작업장의 description 찾기
            const areaData = workAreasData?.find(wa => wa.name === areaName);
            const areaDescription = areaData?.workDescription || '';
            await buildExcelJsSheet(workbook, areaName, photos, projectName, areaDescription);
        }

        const buf = await workbook.xlsx.writeBuffer();
        const blob = new Blob(
            [buf],
            { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }
        );

        const timestamp = formatDate(new Date()).replace(/-/g, '');
        const baseName = sanitizeFilename(`${projectName || '사진대지(이미지)'}_${timestamp}`);
        const filename = `${baseName}.xlsx`;

        downloadFile(blob, filename);

        showLoading(false);
        showStatus('이미지 포함 Excel 파일이 생성되었습니다!', 'success');
    } catch (error) {
        console.error('ExcelJS 이미지 생성 오류:', error);
        showLoading(false);
        showStatus('ExcelJS로 Excel 생성 중 오류가 발생했습니다.', 'error');
    }
}
