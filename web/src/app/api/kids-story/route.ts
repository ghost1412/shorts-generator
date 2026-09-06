import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { hero, heroName, companion, quest, setting } = await request.json();

    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      return NextResponse.json({ error: 'GEMINI_API_KEY is not configured in web/.env.local' }, { status: 500 });
    }

    const systemPrompt = `You are a professional children's storybook writer. Create a charming, sweet, and educational 3-page children's story based on the character and quest provided. Keep it engaging, simple, and under 100 words in total. Output a raw JSON object ONLY. No conversational text. Do not wrap in markdown codeblocks.

The JSON schema must be EXACTLY:
{
  "title": "Story Title",
  "pages": [
    {
      "text": "Story text for page 1 (1-2 simple sentences).",
      "image_prompt": "Description of the scene for page 1 for an image generator, e.g. 'A cute baby bear named Luna wearing a tiny wizard hat in a glowing sparkly forest, 3d render Pixar style, claymation, colorful'."
    },
    {
      "text": "Story text for page 2 (1-2 simple sentences).",
      "image_prompt": "Description of the scene for page 2 for an image generator."
    },
    {
      "text": "Story text for page 3 (1-2 simple sentences).",
      "image_prompt": "Description of the scene for page 3 for an image generator."
    }
  ]
}`;

    const userPrompt = `Hero: ${hero} (named ${heroName || 'Buddy'})
Companion: ${companion}
Quest: ${quest}
Setting: ${setting}`;

    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=${apiKey}`;
    
    const payload = {
      contents: [
        {
          role: 'user',
          parts: [
            { text: `System instructions:\n${systemPrompt}\n\nPrompt:\n${userPrompt}` }
          ]
        }
      ],
      generationConfig: {
        temperature: 0.8,
        responseMimeType: 'application/json'
      }
    };

    let rawText = '';
    let success = false;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Gemini status ${response.status}: ${errText}`);
      }

      const data = await response.json();
      rawText = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
      if (rawText) success = true;
    } catch (geminiError: any) {
      console.warn('[Kids Story] Gemini failed, attempting local Ollama fallback...', geminiError.message || geminiError);
      
      const localUrl = process.env.LOCAL_LLM_URL || 'http://localhost:11434/api/chat';
      const localModel = process.env.LOCAL_LLM_MODEL || 'qwen3:8b';
      
      const localPayload = {
        model: localModel,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ],
        stream: false
      };

      try {
        const localResponse = await fetch(localUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(localPayload)
        });

        if (!localResponse.ok) {
          throw new Error(`Ollama status ${localResponse.status}`);
        }

        const localData = await localResponse.json();
        rawText = localData.message?.content || '';
        if (rawText) success = true;
      } catch (ollamaError: any) {
        console.error('[Kids Story] Both Gemini and Ollama failed:', ollamaError.message || ollamaError);
        return NextResponse.json({ error: 'Both AI providers failed. Is Ollama running?' }, { status: 500 });
      }
    }

    if (!success || !rawText) {
      return NextResponse.json({ error: 'Failed to generate story content' }, { status: 500 });
    }

    // Clean JSON wrapper if any
    let cleanedText = rawText.trim();
    if (cleanedText.startsWith('```json')) {
      cleanedText = cleanedText.substring(7);
    }
    if (cleanedText.endsWith('```')) {
      cleanedText = cleanedText.substring(0, cleanedText.length - 3);
    }
    cleanedText = cleanedText.trim();

    const storyJson = JSON.parse(cleanedText);
    return NextResponse.json({ success: true, story: storyJson });

  } catch (error: any) {
    console.error('Kids Story API Error:', error);
    return NextResponse.json({ error: error.message || 'Internal Server Error' }, { status: 500 });
  }
}
