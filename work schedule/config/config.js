const path = require('path');
require('dotenv').config();

const BASE_DIR = path.resolve(__dirname, '..');
const DATA_DIR = path.join(BASE_DIR, 'data');
const TEMPLATE_DIR = path.join(DATA_DIR, 'templates');
const TEMPLATE_DB_PATH = path.join(DATA_DIR, 'templates.json');

module.exports = {
    paths: {
        base: BASE_DIR,
        data: DATA_DIR,
        templates: TEMPLATE_DIR,
        templateDb: TEMPLATE_DB_PATH
    },
    // 기본 열 매핑 (엑셀 열 문자)
    defaultColumnMap: {
        location: 'B',      // 위치
        workContent: 'C',   // 작업내용
        personnel: 'H',     // 인원
        equipment: 'I'      // 장비
    },
    // 기본 공사구분 목록 (파싱 힌트용)
    defaultSections: [
        "토공",
        "포장공",
        "배수공",
        "구조물공",
        "터널공",
        "환경관리 및 안전관리",
        "부대공"
    ],
    gemini: {
        apiKey: process.env.GEMINI_API_KEY,
        model: "gemini-2.0-flash-exp"
    },
    server: {
        port: process.env.PORT || 3000
    }
};
