const { GoogleGenerativeAI } = require("@google/generative-ai");
const config = require('../config/config');

const genAI = new GoogleGenerativeAI(config.gemini.apiKey);
const model = genAI.getGenerativeModel({
    model: config.gemini.model,
    generationConfig: {
        responseMimeType: "application/json"
    }
});

async function parseWorkplan(text, sectionNames) {
    const sections = sectionNames || config.defaultSections;

    const prompt = `
    너는 건설현장 작업계획서를 구조화된 데이터로 변환하는 AI 어시스턴트야.
    아래 제공된 [작업계획 텍스트]를 분석해서 JSON 배열로 반환해줘.

    [규칙]
    1. 각 작업 항목은 다음 필드를 가져야 해:
       - "section": 공사구분 (가능하면 다음 목록 중 하나 선택: ${sections.join(', ')}. 목록에 없으면 텍스트 내용을 보고 적절히 판단하거나 새로운 구분 사용)
       - "location": 작업 위치
       - "content": 작업 내용 (간결하게)
       - "personnel": 인원 정보 (객체 배열로 반환. 예: [{"name": "목수", "count": "2명"}, {"name": "신호수", "count": "1명"}])
       - "equipment": 장비 정보 (객체 배열로 반환. 예: [{"name": "백호 0.6w", "count": "1대"}, {"name": "덤프 15t", "count": "2대"}])
    
    2. 응답은 오직 JSON 배열만 포함해야 해. 다른 설명은 추가하지 마.
    
    [작업계획 텍스트]
    ${text}
    `;

    try {
        const result = await model.generateContent(prompt);
        const response = await result.response;
        const textResponse = response.text();

        // JSON 파싱
        let items = JSON.parse(textResponse);

        // 만약 최상위가 객체이고 items 키가 있다면 그 안의 배열 사용
        if (!Array.isArray(items) && items.items) {
            items = items.items;
        } else if (!Array.isArray(items)) {
            // 배열이 아니라면 배열로 감싸기
            items = [items];
        }

        return items;
    } catch (error) {
        console.error("Gemini API Error:", error);
        throw new Error("Failed to parse workplan with AI");
    }
}

module.exports = {
    parseWorkplan
};
