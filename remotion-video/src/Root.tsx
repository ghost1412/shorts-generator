import "./index.css";
import { Composition } from "remotion";
import { ShortFlow, shortFlowSchema } from "./ShortFlow";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ShortFlow"
        component={ShortFlow}
        fps={30}
        width={1080}
        height={1920}
        schema={shortFlowSchema}
        calculateMetadata={({ props }) => {
          let durationInFrames = 900;
          if (props.words && props.words.length > 0) {
            const maxWordEnd = Math.max(...props.words.map(w => w.end));
            durationInFrames = Math.ceil((maxWordEnd + 1.0) * 30);
          }
          if (props.backgrounds && props.backgrounds.length > 0) {
            const maxBgEnd = Math.max(...props.backgrounds.map(bg => bg.end));
            const bgDurationFrames = Math.ceil(maxBgEnd * 30);
            if (bgDurationFrames > durationInFrames) {
              durationInFrames = bgDurationFrames;
            }
          }
          return {
            durationInFrames: Math.max(30, durationInFrames),
          };
        }}
        defaultProps={{
          audioUrl: "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
          bgMusicUrl: undefined,
          bgMusicVolume: 0.15,
          mode: "FACTS" as const,
          category: "general",
          titleText: "Preview Short",
          subtitleYPos: 1600,
          words: [
            { word: "This", start: 0.1, end: 0.5 },
            { word: "is", start: 0.5, end: 0.9 },
            { word: "a", start: 0.9, end: 1.2 },
            { word: "preview", start: 1.2, end: 2.0 },
            { word: "subtitle", start: 2.0, end: 3.0 },
          ],
          backgrounds: [],
        }}
      />
    </>
  );
};
