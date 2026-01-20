const functions = require("firebase-functions");
const { GoogleGenerativeAI } = require("@google/generative-ai");
const cors = require('cors')({ origin: true });

// 환경변수에서 키 가져오기 (.env 사용)
const apiKey = process.env.GEMINI_API_KEY;
const genAI = new GoogleGenerativeAI(apiKey);

exports.parseWorkplan = functions.https.onRequest(async (req, res) => {
    // CORS 처리
    cors(req, res, async () => {
        try {
            const { text, sectionNames, columnDefinitions, systemPrompt, mode } = req.body;

            console.log("Request received:", {
                textLength: text ? text.length : 0,
                sectionNames,
                columnDefinitions,
                hasSystemPrompt: !!systemPrompt,
                mode
            });

            if (!apiKey) {
                console.error("API Key is missing");
                res.status(500).json({ error: 'Server configuration error: API Key missing' });
                return;
            }

            if (!text) {
                res.status(400).json({ error: 'Text is required' });
                return;
            }

            // 모델 초기화 (Flash 2.0 Experimental)
            const model = genAI.getGenerativeModel({
                model: "gemini-2.0-flash-exp",
                generationConfig: {
                    responseMimeType: "application/json"
                }
            });

            const sections = sectionNames || [
                "토공", "포장공", "배수공", "구조물공", "터널공", "환경관리 및 안전관리", "부대공"
            ];

            // 동적 필드 정의 생성
            let outputFieldsPrompt = '';

            // 모든 모드에서 구조화된 객체 배열 요청 (app.js가 두 형식 모두 지원함)
            outputFieldsPrompt = `
            - "section": 공사구분 (목록: ${Array.isArray(sections) ? sections.join(', ') : sections}). 텍스트의 "◆ 섹션명"을 우선 따름)
            - "location": 작업 위치 (텍스트 앞부분)
            - "content": 작업 내용 (위치 뒤, 괄호 앞부분)
            - "personnel": 인원 정보 배열 (객체 형태: [{name: "목수", count: "2명"}, ...])
            - "equipment": 장비 정보 배열 (객체 형태: [{name: "0.6w", count: "1대"}, ...])
            - "company": 업체명 (문서 상단의 업체명 또는 텍스트 내 명시된 업체)
            - "totalPersonnel": 총 투입인원 (예: "◆ 투입인원 : 37명" 에서 "37명" 추출)
            - "totalEquipment": 총 투입장비 (예: "◆ 투입장비 : 9대" 에서 "9대" 추출)
            `;

            if (Array.isArray(columnDefinitions) && columnDefinitions.length > 0) {
                const customFields = columnDefinitions.filter(d =>
                    !['section', 'location', 'content', 'personnel', 'equipment', 'company', 'constructionType', 'totalPersonnel', 'totalEquipment'].includes(d.key) &&
                    !['공사구분', '위치', '작업내용', '인원', '장비', '업체명', '총인원', '총장비'].includes(d.name)
                );

                if (customFields.length > 0) {
                    outputFieldsPrompt += customFields.map(f => `- "${f.name}": ${f.name} 정보 (텍스트에서 추출)`).join('\n            ');
                }
            }

            // Build prompt with optional système prompt
            let fullPrompt = '';
            if (systemPrompt && systemPrompt.trim()) {
                fullPrompt = `[사용자 지시사항]\n${systemPrompt.trim()}\n\n`;
            }

            fullPrompt += `
            너는 건설현장 작업계획서를 구조화된 데이터로 변환하는 AI 어시스턴트야.
            아래 제공된 [작업계획 텍스트]를 분석해서 JSON 배열로 반환해줘.

            [입력 텍스트 분석 규칙]
            1. 텍스트는 "◆ 섹션명" 으로 구분되어 있어. (예: ◆ 토공, ◆ 배수공)
            2. 각 줄은 "- 위치 작업내용 (인원, 장비)" 형태일 수 있어.
            3. 문서 상단이나 "##" 뒤에 나오는 업체명(예: 장차건설)을 찾아서 모든 항목의 "company" 필드에 넣어줘.
            4. "◆ 투입장비", "◆ 투입인원" 같은 요약 섹션이 있다면, 해당 정보를 추출해서 **모든 항목**의 "totalEquipment", "totalPersonnel" 필드에 포함시켜줘.
            5. 요약 섹션 자체는 별도의 작업 항목(row)으로 만들지 마.

            [출력 필드]
            ${outputFieldsPrompt}
            
            [작업계획 텍스트]
            ${text}
            `;

            const result = await model.generateContent(fullPrompt);
            const response = await result.response;
            const textResponse = response.text();

            // JSON 파싱
            let items = JSON.parse(textResponse);
            if (!Array.isArray(items) && items.items) {
                items = items.items;
            } else if (!Array.isArray(items)) {
                items = [items];
            }

            res.json(items);

        } catch (err) {
            console.error("Error processing request:", err);
            res.status(500).json({ error: String(err) });
        }
    });
});
