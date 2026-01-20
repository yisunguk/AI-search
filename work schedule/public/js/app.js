// IndexedDB Helper
const DB_NAME = 'WorkScheduleDB';
const DB_VERSION = 1;
const STORE_NAME = 'templates';
let currentMode = 'workplan';


const dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = event => reject('IndexedDB error: ' + event.target.error);

    request.onupgradeneeded = event => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
            db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        }
    };

    request.onsuccess = event => resolve(event.target.result);
});

async function saveTemplateToDB(template) {
    const db = await dbPromise;
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.put(template);
        request.onsuccess = () => resolve(template);
        request.onerror = () => reject(request.error);
    });
}

async function getTemplatesFromDB() {
    const db = await dbPromise;
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function getTemplateFromDB(id) {
    const db = await dbPromise;
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.get(id);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // 탭 전환 로직
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;

            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(targetTab).classList.add('active');

            if (targetTab === 'workplan') {
                loadTemplateOptions();
            } else if (targetTab === 'templates') {
                loadTemplateList();
            }
        });
    });

    // Mode switching logic - Menu Items
    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetMode = item.dataset.mode;
            if (currentMode === targetMode) return;

            currentMode = targetMode;
            menuItems.forEach(m => m.classList.remove('active'));
            item.classList.add('active');

            // Update tab button text and card title based on mode
            updateTabAndTitleText();

            // Update UI based on mode
            updateUIForMode();
            loadTemplateList();
            loadTemplateOptions();
        });
    });

    function updateTabAndTitleText() {
        const workTabBtn = document.getElementById('workTabBtn');
        const workCardTitle = document.getElementById('workCardTitle');

        if (currentMode === 'workplan') {
            workTabBtn.textContent = '작업계획 작성';
            workCardTitle.textContent = '작업계획 작성';
        } else {
            workTabBtn.textContent = '투입비 작성';
            workCardTitle.textContent = '투입비 작성';
        }
    }

    function toggleFormFields() {
        const dataRowOffsetGroup = document.getElementById('dataRowOffsetGroup');

        if (currentMode === 'workplan') {
            // 작업계획 모드: 오프셋 필드 숨김
            dataRowOffsetGroup.style.display = 'none';
        } else {
            // 투입비 모드: 오프셋 필드 표시
            dataRowOffsetGroup.style.display = 'block';
        }
    }

    function updateUIForMode() {
        toggleFormFields();

        if (currentMode === 'workplan') {
            renderColumnMappings([
                { key: 'constructionType', name: '공사구분', column: 'A' },
                { key: 'location', name: '위치', column: 'B' },
                { key: 'content', name: '작업내용', column: 'C' },
                { key: 'personnel', name: '인원', column: 'H' },
                { key: 'equipment', name: '장비', column: 'I' },
                { key: 'company', name: '업체명', column: 'J' },
                { key: 'totalPersonnel', name: '총인원', column: '' },
                { key: 'totalEquipment', name: '총장비', column: '' }
            ]);
        } else {
            renderColumnMappings([
                { key: 'constructionType', name: '공사구분', column: 'A' },
                { key: 'location', name: '위치', column: 'B' },
                { key: 'content', name: '작업내용', column: 'C' },
                { key: 'personnelName', name: '인원(직종)', column: 'H' },
                { key: 'personnelCount', name: '인원(수)', column: 'I' },
                { key: 'equipmentName', name: '장비(기종)', column: 'J' },
                { key: 'equipmentCount', name: '장비(대수)', column: 'K' },
                { key: 'company', name: '업체명', column: 'L' },
                { key: 'totalPersonnel', name: '총인원', column: '' },
                { key: 'totalEquipment', name: '총장비', column: '' }
            ]);
        }
    }

    // 초기 데이터 로드
    loadTemplateList();
    loadTemplateOptions();
    updateUIForMode(); // Initialize columns based on default mode

    document.getElementById('btnAddColumn').addEventListener('click', () => {
        addColumn();
    });

    // 파일 선택 시 파일명 표시
    const fileInput = document.getElementById('file');
    const filePlaceholder = document.querySelector('.file-upload-placeholder span');

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            filePlaceholder.textContent = e.target.files[0].name;
            // 양식 이름이 비어있으면 파일명으로 자동 채우기
            const templateNameInput = document.getElementById('templateName');
            if (!templateNameInput.value) {
                templateNameInput.value = e.target.files[0].name.replace('.xlsx', '');
            }
        } else {
            filePlaceholder.textContent = '클릭하여 파일 선택 또는 드래그 앤 드롭';
        }
    });

    // 양식 등록 폼 제출
    const templateForm = document.getElementById('templateForm');
    templateForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        showLoading('양식을 분석하고 저장 중입니다...');

        try {
            const fileInput = document.getElementById('file');
            const file = fileInput.files[0];
            if (!file) throw new Error('파일을 선택해주세요.');

            const templateName = document.getElementById('templateName').value || file.name;
            const sheetName = document.getElementById('sheetName').value;
            const sectionNamesStr = document.getElementById('sectionNames').value;
            const sectionNames = sectionNamesStr.split(',').map(s => s.trim()).filter(s => s);

            // Dynamic Column Mapping gathering
            const columnMappingList = document.getElementById('columnMappingList');
            const rows = columnMappingList.querySelectorAll('.column-mapping-item');
            const columnDefinitions = Array.from(rows).map(row => ({
                key: row.dataset.key,
                name: row.querySelector('.col-name').value,
                column: row.querySelector('.col-column').value
            })).filter(def => def.name && def.column); // Filter out empty entries

            // Get system prompt
            const systemPrompt = document.getElementById('systemPrompt').value || '';

            // Get data row offset for direct payment mode (투입비 모드에서만 사용)
            const dataRowOffsetValue = document.getElementById('dataRowOffset').value;
            const dataRowOffset = dataRowOffsetValue ? parseInt(dataRowOffsetValue, 10) : 11;

            // Client-side Excel Analysis
            const arrayBuffer = await file.arrayBuffer();
            const workbook = new ExcelJS.Workbook();
            await workbook.xlsx.load(arrayBuffer);

            let worksheet;
            if (sheetName) {
                worksheet = workbook.getWorksheet(sheetName);
            } else {
                worksheet = workbook.worksheets[0];
            }

            if (!worksheet) {
                throw new Error("시트를 찾을 수 없습니다.");
            }

            // 공사구분 섹션 찾기 (두 모드 모두 사용)
            const sectionsMeta = {};
            const sectionsToCheck = sectionNames.length > 0 ? sectionNames : ["토공", "포장공", "배수공", "구조물공", "터널공", "환경관리 및 안전관리", "부대공"];

            for (const sec of sectionsToCheck) {
                const row = findSectionRow(worksheet, sec);
                if (row) {
                    sectionsMeta[sec] = { headerRow: row };
                }
            }

            const templateId = currentEditingId || Date.now().toString();
            const newTemplate = {
                id: templateId,
                name: templateName,
                mode: currentMode,
                fileData: arrayBuffer, // Save file content to DB
                sheetName: worksheet.name,
                sections: sectionsMeta,
                dataRowOffset: dataRowOffset, // For direct payment mode (섹션 헤더에서 오프셋)
                columnDefinitions: columnDefinitions, // Save dynamic definitions
                systemPrompt: systemPrompt, // Save system prompt
                createdAt: currentEditingId ? (await getTemplateFromDB(currentEditingId)).createdAt : new Date().toISOString(),
                updatedAt: new Date().toISOString()
            };

            await saveTemplateToDB(newTemplate);

            alert(`양식이 성공적으로 ${currentEditingId ? '수정' : '등록'}되었습니다: ${newTemplate.name}`);

            // Reset form and editing state
            templateForm.reset();
            currentEditingId = null;
            const submitBtn = document.querySelector('#templateForm button[type="submit"]');
            submitBtn.textContent = '양식 등록하기';
            submitBtn.classList.remove('warning');

            // Reset column mappings to default
            // Reset column mappings to default
            updateUIForMode();

            loadTemplateList();
        } catch (error) {
            console.error(error);
            alert('오류가 발생했습니다: ' + error.message);
        } finally {
            hideLoading();
        }
    });

    // AI 파싱 버튼
    const btnParse = document.getElementById('btnParse');
    btnParse.addEventListener('click', async () => {
        const text = document.getElementById('workText').value;
        const templateId = document.getElementById('selectTemplate').value;

        if (!text.trim()) {
            alert('작업계획 텍스트를 입력해주세요.');
            return;
        }

        showLoading('AI가 작업계획을 분석 중입니다...');

        try {
            // 템플릿 정보 가져오기 (공사구분 힌트용)
            let sectionNames = null;
            let columnDefinitions = [];
            let systemPrompt = null;

            if (templateId) {
                const template = await getTemplateFromDB(templateId);
                if (template) {
                    if (template.sections) {
                        sectionNames = Object.keys(template.sections);
                    }
                    if (template.columnDefinitions) {
                        columnDefinitions = template.columnDefinitions;
                    }
                    if (template.systemPrompt) {
                        systemPrompt = template.systemPrompt;
                    }
                }
            }

            // Firebase Functions 호출 (Rewrites 설정으로 /api/parse -> parseWorkplan)
            const response = await fetch('/api/parse', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text, sectionNames, columnDefinitions, systemPrompt, mode: currentMode })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `파싱 실패 (${response.status})`);
            }

            const items = await response.json();
            displayParseResult(items);
        } catch (error) {
            console.error(error);
            alert('파싱 중 오류가 발생했습니다: ' + error.message);
        } finally {
            hideLoading();
        }
    });

    // 엑셀 생성 버튼 (Client-side)
    const btnGenerate = document.getElementById('btnGenerate');
    btnGenerate.addEventListener('click', async () => {
        const templateId = document.getElementById('selectTemplate').value;
        if (!templateId) {
            alert('양식을 선택해주세요.');
            return;
        }

        const items = window.currentParsedItems;
        if (!items) {
            alert('먼저 파싱을 실행해주세요.');
            return;
        }

        showLoading('엑셀 파일을 생성 중입니다...');

        try {
            const template = await getTemplateFromDB(templateId);
            if (!template) throw new Error('템플릿을 찾을 수 없습니다.');

            const workbook = new ExcelJS.Workbook();
            await workbook.xlsx.load(template.fileData);

            const worksheet = workbook.getWorksheet(template.sheetName);
            if (!worksheet) throw new Error('시트를 찾을 수 없습니다.');

            const columnDefinitions = template.columnDefinitions || [];
            // Backward compatibility for old templates with columnMap
            if (columnDefinitions.length === 0 && template.columnMap) {
                // Convert old map to new definitions if needed, or just handle in fillRows
                // For simplicity, we'll handle it in fillRows or convert here.
                // Let's convert here for unified logic
                if (template.columnMap.location) columnDefinitions.push({ key: 'location', name: '위치', column: template.columnMap.location });
                if (template.columnMap.workContent) columnDefinitions.push({ key: 'content', name: '작업내용', column: template.columnMap.workContent });
                if (template.columnMap.personnel) columnDefinitions.push({ key: 'personnel', name: '인원', column: template.columnMap.personnel });
                if (template.columnMap.equipment) columnDefinitions.push({ key: 'equipment', name: '장비', column: template.columnMap.equipment });
                if (template.columnMap.constructionType) columnDefinitions.push({ key: 'constructionType', name: '공사구분', column: template.columnMap.constructionType });
                if (template.columnMap.company) columnDefinitions.push({ key: 'company', name: '업체명', column: template.columnMap.company });
            }

            const sectionsMeta = template.sections;
            const templateMode = template.mode || 'workplan';

            // Split columns into Detail and Summary
            const summaryKeys = ['company', 'totalPersonnel', 'totalEquipment'];
            const summaryColumns = columnDefinitions.filter(d => summaryKeys.includes(d.key) || ['업체명', '총인원', '총장비'].includes(d.name));
            const detailColumns = columnDefinitions.filter(d => !summaryKeys.includes(d.key) && !['업체명', '총인원', '총장비'].includes(d.name));

            if (templateMode === 'direct_payment') {
                // ============================================
                // 투입비 모드: 섹션 기반 + 오프셋 데이터 입력
                // ============================================
                const dataRowOffset = template.dataRowOffset || 11;

                console.log('=== 투입비 모드 디버그 ===');
                console.log('템플릿 모드:', templateMode);
                console.log('데이터 오프셋:', dataRowOffset);
                console.log('섹션 메타:', sectionsMeta);
                console.log('상세 컬럼:', detailColumns);
                console.log('파싱된 아이템:', items);

                // Group items by section
                const itemsBySection = {};
                items.forEach(item => {
                    const sec = item.section || "기타";
                    if (!itemsBySection[sec]) {
                        itemsBySection[sec] = [];
                    }
                    itemsBySection[sec].push(item);
                });

                console.log('섹션별 아이템:', itemsBySection);

                const sortedSections = Object.entries(sectionsMeta)
                    .sort(([, a], [, b]) => a.headerRow - b.headerRow);

                // Fill Detail Columns (Section by Section with offset)
                if (sortedSections.length > 0) {
                    for (let i = 0; i < sortedSections.length; i++) {
                        const [sectionName, meta] = sortedSections[i];
                        const headerRow = meta.headerRow;

                        // 투입비: 헤더 + 오프셋에서 데이터 시작
                        const startRow = headerRow + dataRowOffset;

                        console.log(`섹션 "${sectionName}": 헤더 행=${headerRow}, 데이터 시작 행=${startRow}`);

                        let nextHeaderRow = worksheet.rowCount + 1;
                        if (i < sortedSections.length - 1) {
                            nextHeaderRow = sortedSections[i + 1][1].headerRow;
                        }
                        const endRow = nextHeaderRow - 1;

                        // Clear range for DETAIL columns only
                        const columnsToClear = detailColumns.map(d => d.column);
                        clearRange(worksheet, startRow, endRow, columnsToClear);

                        // Fill data
                        const sectionItems = itemsBySection[sectionName] || [];
                        console.log(`섹션 "${sectionName}" 아이템 수:`, sectionItems.length);
                        if (sectionItems.length > 0) {
                            fillRows(worksheet, startRow, sectionItems, detailColumns);
                        }
                    }
                } else {
                    // ============================================================
                    // 섹션이 없는 경우 (Dynamic Writing): 
                    // 프로그램이 직접 섹션 헤더를 쓰고 데이터를 채움
                    // ============================================================
                    console.log('섹션이 발견되지 않음. 동적으로 섹션 헤더와 데이터를 작성합니다.');

                    let currentRow = 1 + dataRowOffset; // 시작 행 (예: 12행)

                    // 공사구분 컬럼 찾기 (섹션 헤더를 쓸 열)
                    const constructionTypeColDef = columnDefinitions.find(d => d.key === 'constructionType' || d.name === '공사구분');
                    const sectionHeaderCol = constructionTypeColDef ? constructionTypeColDef.column : 'C'; // 기본값 C열

                    // 기존 데이터 초기화 (충분히 넓은 범위)
                    const columnsToClear = detailColumns.map(d => d.column);
                    // 섹션 헤더가 들어갈 열도 초기화 대상에 포함
                    if (!columnsToClear.includes(sectionHeaderCol)) {
                        columnsToClear.push(sectionHeaderCol);
                    }
                    clearRange(worksheet, currentRow, currentRow + 200, columnsToClear);

                    // 섹션 순서대로 작성 (기본 순서 또는 파싱된 순서)
                    const defaultOrder = ["토공", "배수공", "구조물공", "포장공", "부대공", "터널공", "환경관리 및 안전관리"];
                    const parsedSections = Object.keys(itemsBySection);

                    // 기본 순서에 있는 것 먼저, 그 외에는 뒤에 추가
                    const orderedSections = [
                        ...defaultOrder.filter(s => parsedSections.includes(s)),
                        ...parsedSections.filter(s => !defaultOrder.includes(s))
                    ];

                    for (const sectionName of orderedSections) {
                        const sectionItems = itemsBySection[sectionName] || [];
                        if (sectionItems.length === 0) continue;

                        // 1. 섹션 헤더 작성 (예: ◆ 토공)
                        const headerCell = worksheet.getCell(`${sectionHeaderCol}${currentRow}`);
                        headerCell.value = `◆ ${sectionName}`;
                        headerCell.font = { bold: true }; // 볼드체 적용

                        currentRow++; // 다음 행으로 이동

                        // 2. 데이터 채우기
                        fillRows(worksheet, currentRow, sectionItems, detailColumns);

                        // 3. 다음 섹션을 위해 행 인덱스 증가
                        currentRow += sectionItems.length;

                        // 섹션 간 빈 줄 추가 (선택 사항, 여기서는 1줄 띄움)
                        currentRow++;
                    }
                }

                // Fill summary columns if defined
                if (summaryColumns.length > 0) {
                    // 섹션이 있으면 첫 섹션 기준, 없으면 기본 1행 기준
                    const baseRow = sortedSections.length > 0 ? sortedSections[0][1].headerRow : 1;
                    const summaryStartRow = baseRow + dataRowOffset;

                    const summaryColsToClear = summaryColumns.map(d => d.column);
                    clearRange(worksheet, summaryStartRow, summaryStartRow + 50, summaryColsToClear);
                    fillSummaryTable(worksheet, summaryStartRow, items, summaryColumns);
                }

            } else {
                // ============================================
                // 작업계획 모드: 섹션 기반 데이터 입력 + 미등록 섹션 자동 추가
                // ============================================

                // Group items by section
                const itemsBySection = {};
                items.forEach(item => {
                    const sec = item.section || "기타";
                    if (!itemsBySection[sec]) {
                        itemsBySection[sec] = [];
                    }
                    itemsBySection[sec].push(item);
                });

                const sortedSections = Object.entries(sectionsMeta)
                    .sort(([, a], [, b]) => a.headerRow - b.headerRow);

                // 처리된 섹션 추적
                const processedSections = new Set();
                let lastUsedRow = 0;

                // 1. Fill Detail Columns (Section by Section) - 등록된 섹션
                for (let i = 0; i < sortedSections.length; i++) {
                    const [sectionName, meta] = sortedSections[i];
                    const headerRow = meta.headerRow;
                    processedSections.add(sectionName);

                    let nextHeaderRow = worksheet.rowCount + 1;
                    if (i < sortedSections.length - 1) {
                        nextHeaderRow = sortedSections[i + 1][1].headerRow;
                    }

                    const startRow = headerRow;
                    const endRow = nextHeaderRow - 1;

                    // Clear range for DETAIL columns only
                    const columnsToClear = detailColumns.map(d => d.column);
                    clearRange(worksheet, startRow, endRow, columnsToClear);

                    // Fill data
                    const sectionItems = itemsBySection[sectionName] || [];
                    if (sectionItems.length > 0) {
                        fillRows(worksheet, startRow, sectionItems, detailColumns);
                        lastUsedRow = Math.max(lastUsedRow, startRow + sectionItems.length);
                    } else {
                        lastUsedRow = Math.max(lastUsedRow, endRow);
                    }
                }

                // 2. 미등록 섹션 처리 (양식에 없는 공사구분 자동 추가)
                const unregisteredSections = Object.keys(itemsBySection)
                    .filter(sec => !processedSections.has(sec));

                if (unregisteredSections.length > 0) {
                    console.log('미등록 섹션 발견:', unregisteredSections);

                    // 공사구분 컬럼 찾기 (A열이 기본)
                    const constructionTypeColDef = detailColumns.find(d =>
                        d.key === 'constructionType' || d.name === '공사구분');
                    const sectionHeaderCol = constructionTypeColDef ? constructionTypeColDef.column : 'A';

                    // 마지막 섹션 이후 또는 워크시트 끝에서 시작
                    let currentRow = sortedSections.length > 0
                        ? lastUsedRow + 2  // 기존 섹션이 있으면 그 이후
                        : 5; // 섹션이 없으면 5행부터 시작

                    for (const sectionName of unregisteredSections) {
                        const sectionItems = itemsBySection[sectionName];
                        if (sectionItems.length === 0) continue;

                        console.log(`미등록 섹션 "${sectionName}" 추가: ${sectionItems.length}개 항목, 시작 행: ${currentRow}`);

                        // 섹션 헤더 작성 (예: ◆ 배관공)
                        const headerCell = worksheet.getCell(`${sectionHeaderCol}${currentRow}`);
                        headerCell.value = `◆ ${sectionName}`;
                        headerCell.font = { bold: true };

                        currentRow++; // 데이터 시작 행으로 이동

                        // 데이터 채우기
                        fillRows(worksheet, currentRow, sectionItems, detailColumns);

                        currentRow += sectionItems.length + 1; // 다음 섹션을 위해 이동 (빈 줄 포함)
                    }
                }

                // 3. Fill Summary Table (Global, Grouped by Company)
                const summaryStartRow = sortedSections.length > 0 ? sortedSections[0][1].headerRow : 5;

                // Clear range for SUMMARY columns
                const summaryColsToClear = summaryColumns.map(d => d.column);
                clearRange(worksheet, summaryStartRow, summaryStartRow + 50, summaryColsToClear);

                fillSummaryTable(worksheet, summaryStartRow, items, summaryColumns);
            }

            // Download
            const buffer = await workbook.xlsx.writeBuffer();
            const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '작업계획_완성.xlsx';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

        } catch (error) {
            console.error(error);
            alert('엑셀 생성 중 오류가 발생했습니다: ' + error.message);
        } finally {
            hideLoading();
        }
    });

    // Helper Functions

    function findSectionRow(worksheet, sectionName) {
        let foundRow = null;
        worksheet.eachRow((row, rowNumber) => {
            if (foundRow) return;
            row.eachCell((cell) => {
                if (foundRow) return;
                if (cell.value && String(cell.value).includes(sectionName)) {
                    foundRow = rowNumber;
                }
            });
        });
        return foundRow;
    }

    function clearRange(worksheet, startRow, endRow, columns) {
        for (let r = startRow; r <= endRow; r++) {
            columns.forEach(col => {
                const cell = worksheet.getCell(`${col}${r}`);
                cell.value = null;
            });
        }
    }

    function fillRows(worksheet, startRow, items, columnDefinitions) {
        items.forEach((item, index) => {
            const currentRow = startRow + index;

            columnDefinitions.forEach(def => {
                let value = '';

                // Standard mapping
                if (def.key === 'constructionType' || def.name === '공사구분') value = item.section;
                else if (def.key === 'location' || def.name === '위치') value = item.location;
                else if (def.key === 'content' || def.name === '작업내용') value = item.content;
                else if (def.key === 'equipment' || def.name === '장비') {
                    if (Array.isArray(item.equipment)) {
                        // Check if elements are objects (new mode) or strings (old mode)
                        if (item.equipment.length > 0 && typeof item.equipment[0] === 'object') {
                            value = item.equipment.map(e => `${e.name} ${e.count}`).join(', ');
                        } else {
                            value = item.equipment.join(', ');
                        }
                    } else {
                        value = item.equipment;
                    }
                }
                else if (def.key === 'personnel' || def.name === '인원') {
                    if (Array.isArray(item.personnel)) {
                        if (item.personnel.length > 0 && typeof item.personnel[0] === 'object') {
                            value = item.personnel.map(p => `${p.name} ${p.count}`).join(', ');
                        } else {
                            value = item.personnel.join(', ');
                        }
                    } else {
                        value = item.personnel;
                    }
                }
                // New fields for Direct Payment Mode
                else if (def.key === 'equipmentName' || def.name === '장비(기종)') {
                    if (Array.isArray(item.equipment) && item.equipment.length > 0 && typeof item.equipment[0] === 'object') {
                        value = item.equipment.map(e => e.name).join(', '); // Use newline for multiple items in one cell
                    }
                }
                else if (def.key === 'equipmentCount' || def.name === '장비(대수)') {
                    if (Array.isArray(item.equipment) && item.equipment.length > 0 && typeof item.equipment[0] === 'object') {
                        value = item.equipment.map(e => e.count).join(', ');
                    }
                }
                else if (def.key === 'personnelName' || def.name === '인원(직종)') {
                    if (Array.isArray(item.personnel) && item.personnel.length > 0 && typeof item.personnel[0] === 'object') {
                        value = item.personnel.map(p => p.name).join(', ');
                    }
                }
                else if (def.key === 'personnelCount' || def.name === '인원(수)') {
                    if (Array.isArray(item.personnel) && item.personnel.length > 0 && typeof item.personnel[0] === 'object') {
                        value = item.personnel.map(p => p.count).join(', ');
                    }
                }
                else {
                    // Custom fields: try to find by name in the item object
                    value = item[def.name] || item[def.key] || '';
                }

                if (value) {
                    worksheet.getCell(`${def.column}${currentRow}`).value = value;
                }
            });
        });
    }

    function fillSummaryTable(worksheet, startRow, items, summaryColumns) {
        // Group items by company
        const companyGroups = {};
        items.forEach(item => {
            const companyName = item.company || 'Unknown';
            if (!companyGroups[companyName]) {
                companyGroups[companyName] = item; // Keep the first item found for this company as representative
            }
        });

        const uniqueCompanies = Object.values(companyGroups);

        uniqueCompanies.forEach((item, index) => {
            const currentRow = startRow + index;

            summaryColumns.forEach(def => {
                let value = '';
                if (def.key === 'company' || def.name === '업체명') value = item.company;
                else if (def.key === 'totalPersonnel' || def.name === '총인원') value = item.totalPersonnel;
                else if (def.key === 'totalEquipment' || def.name === '총장비') value = item.totalEquipment;

                if (value) {
                    worksheet.getCell(`${def.column}${currentRow}`).value = value;
                }
            });
        });
    }

    // Dynamic Column Management Functions
    function renderColumnMappings(definitions) {
        const list = document.getElementById('columnMappingList');
        list.innerHTML = '';
        definitions.forEach(def => {
            addColumn(def);
        });
    }

    function addColumn(def = null) {
        const list = document.getElementById('columnMappingList');
        const id = Date.now().toString() + Math.random().toString(36).substr(2, 9);
        const key = def ? def.key : `field_${id}`;
        const name = def ? def.name : '';
        const column = def ? def.column : '';

        const div = document.createElement('div');
        div.className = 'column-mapping-item';
        div.dataset.key = key;
        div.innerHTML = `
        <input type="text" class="col-name" placeholder="예: 날씨" value="${name}" required>
        <input type="text" class="col-column" placeholder="예: F" value="${column}" required>
        <button type="button" class="btn danger small" onclick="removeColumn(this)">
            🗑️
        </button>
    `;
        list.appendChild(div);
    }

    function removeColumn(btn) {
        btn.closest('.column-mapping-item').remove();
    }
    // Make removeColumn globally accessible
    window.removeColumn = removeColumn;

    // Delete Template Function
    async function deleteTemplate(id) {
        if (!confirm('이 양식을 삭제하시겠습니까?')) return;

        try {
            const db = await dbPromise;
            const transaction = db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            await new Promise((resolve, reject) => {
                const request = store.delete(id);
                request.onsuccess = () => resolve();
                request.onerror = () => reject(request.error);
            });

            alert('양식이 삭제되었습니다.');
            loadTemplateList();
            loadTemplateOptions();
        } catch (error) {
            console.error('Failed to delete template:', error);
            alert('삭제 중 오류가 발생했습니다.');
        }
    }
    window.deleteTemplate = deleteTemplate;

    // Edit Template Function
    let currentEditingId = null;

    async function editTemplate(id) {
        try {
            const template = await getTemplateFromDB(id);
            if (!template) {
                alert('양식을 찾을 수 없습니다.');
                return;
            }

            // Switch to templates tab
            document.querySelector('[data-tab="templates"]').click();

            // Populate form
            document.getElementById('templateName').value = template.name;
            document.getElementById('sheetName').value = template.sheetName || '';

            // Populate section names
            const sectionNames = Object.keys(template.sections || {}).join(', ');
            document.getElementById('sectionNames').value = sectionNames;

            // Populate column definitions
            const columnDefs = template.columnDefinitions || [];
            if (columnDefs.length > 0) {
                renderColumnMappings(columnDefs);
            }

            // Populate system prompt
            document.getElementById('systemPrompt').value = template.systemPrompt || '';

            // Set editing mode
            currentEditingId = id;
            const submitBtn = document.querySelector('#templateForm button[type="submit"]');
            submitBtn.textContent = '양식 수정하기';
            submitBtn.classList.add('warning');

            // Scroll to form
            document.getElementById('templateForm').scrollIntoView({ behavior: 'smooth' });

            alert('수정할 내용을 변경하고 "양식 수정하기" 버튼을 눌러주세요.\n\n* 엑셀 파일은 다시 선택해야 합니다.');
        } catch (error) {
            console.error('Failed to load template for editing:', error);
            alert('양식 로드 중 오류가 발생했습니다.');
        }
    }
    window.editTemplate = editTemplate;

    async function loadTemplateList() {
        try {
            const allTemplates = await getTemplatesFromDB();
            const templates = allTemplates.filter(t => (t.mode || 'workplan') === currentMode);
            const listEl = document.getElementById('templateList');

            if (templates.length === 0) {
                listEl.innerHTML = '<div class="empty-state">등록된 양식이 없습니다.</div>';
                return;
            }

            listEl.innerHTML = templates.map(t => `
            <div class="template-item">
                <div class="template-info">
                    <h3>${t.name}</h3>
                    <p>시트: ${t.sheetName} | 등록일: ${new Date(t.createdAt).toLocaleDateString()}</p>
                </div>
                <div class="template-actions">
                    <button class="btn secondary small" onclick="editTemplate('${t.id}')">
                        ✏️ 수정
                    </button>
                    <button class="btn danger small" onclick="deleteTemplate('${t.id}')">
                        🗑️ 삭제
                    </button>
                </div>
            </div>
        `).join('');
        } catch (error) {
            console.error('Failed to load templates:', error);
        }
    }

    async function loadTemplateOptions() {
        try {
            const allTemplates = await getTemplatesFromDB();
            const templates = allTemplates.filter(t => (t.mode || 'workplan') === currentMode);
            const selectEl = document.getElementById('selectTemplate');
            const currentVal = selectEl.value;

            selectEl.innerHTML = '<option value="">양식을 선택하세요</option>' +
                templates.map(t => `<option value="${t.id}">${t.name}</option>`).join('');

            if (currentVal) selectEl.value = currentVal;
        } catch (error) {
            console.error('Failed to load template options:', error);
        }
    }

    function displayParseResult(items) {
        window.currentParsedItems = items;
        const resultSection = document.getElementById('resultSection');
        const resultViewer = document.getElementById('parseResult');
        resultSection.classList.remove('hidden');
        resultViewer.textContent = JSON.stringify(items, null, 2);
        resultSection.scrollIntoView({ behavior: 'smooth' });
    }

    function showLoading(message) {
        const overlay = document.getElementById('loadingOverlay');
        const text = document.getElementById('loadingText');
        text.textContent = message;
        overlay.classList.remove('hidden');
    }


    function hideLoading() {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }

    // Backup and Restore Functions
    async function backupTemplates() {
        try {
            const templates = await getTemplatesFromDB();

            if (templates.length === 0) {
                alert('백업할 양식이 없습니다.');
                return;
            }

            // Convert ArrayBuffer to Base64 for JSON serialization
            const templatesForExport = templates.map(t => ({
                ...t,
                fileData: arrayBufferToBase64(t.fileData)
            }));

            const dataStr = JSON.stringify(templatesForExport, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            const date = new Date().toISOString().split('T')[0];
            a.download = `templates_backup_${date}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            alert(`${templates.length}개의 양식이 백업되었습니다.`);
        } catch (error) {
            console.error('Backup failed:', error);
            alert('백업 중 오류가 발생했습니다: ' + error.message);
        }
    }

    async function restoreTemplates(file) {
        try {
            const text = await file.text();
            const importedTemplates = JSON.parse(text);

            if (!Array.isArray(importedTemplates)) {
                throw new Error('잘못된 백업 파일 형식입니다.');
            }

            // Ask user: overwrite or merge
            const existingTemplates = await getTemplatesFromDB();
            let shouldOverwrite = false;

            if (existingTemplates.length > 0) {
                shouldOverwrite = confirm(
                    `기존 양식 ${existingTemplates.length}개가 있습니다.\n\n` +
                    `"확인": 기존 데이터를 삭제하고 백업 파일로 덮어씁니다\n` +
                    `"취소": 기존 데이터를 유지하고 병합합니다`
                );
            }

            // Convert Base64 back to ArrayBuffer
            const templatesForImport = importedTemplates.map(t => ({
                ...t,
                fileData: base64ToArrayBuffer(t.fileData)
            }));

            const db = await dbPromise;
            const transaction = db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);

            if (shouldOverwrite) {
                // Delete all existing
                await new Promise((resolve, reject) => {
                    const clearRequest = store.clear();
                    clearRequest.onsuccess = () => resolve();
                    clearRequest.onerror = () => reject(clearRequest.error);
                });
            }

            // Add imported templates
            for (const template of templatesForImport) {
                await new Promise((resolve, reject) => {
                    const putRequest = store.put(template);
                    putRequest.onsuccess = () => resolve();
                    putRequest.onerror = () => reject(putRequest.error);
                });
            }

            alert(`${templatesForImport.length}개의 양식이 복원되었습니다.`);
            loadTemplateList();
            loadTemplateOptions();
        } catch (error) {
            console.error('Restore failed:', error);
            alert('복원 중 오류가 발생했습니다: ' + error.message);
        }
    }

    // Helper functions for ArrayBuffer <-> Base64 conversion
    function arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    function base64ToArrayBuffer(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    // Initialize backup/restore event listeners
    // Initialize backup/restore event listeners
    // document.addEventListener('DOMContentLoaded', () => {
    {
        const btnBackup = document.getElementById('btnBackup');
        const btnRestore = document.getElementById('btnRestore');
        const restoreFileInput = document.getElementById('restoreFile');

        if (btnBackup) {
            console.log('Backup button initialized');
            btnBackup.addEventListener('click', backupTemplates);
        } else {
            console.error('Backup button not found');
        }

        if (btnRestore && restoreFileInput) {
            console.log('Restore button initialized');
            btnRestore.addEventListener('click', () => {
                restoreFileInput.click();
            });

            restoreFileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    restoreTemplates(file);
                    // Reset input
                    e.target.value = '';
                }
            });
        } else {
            console.error('Restore button or file input not found');
        }
    }
});
