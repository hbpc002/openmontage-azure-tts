import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export interface SentenceCaptionItem {
  text: string;
  startMs: number;
  endMs: number;
}

interface Props {
  sentences: SentenceCaptionItem[];
  fontSize?: number;
  color?: string;
  backgroundColor?: string;
  fontFamily?: string;
}

const SentenceRenderer: React.FC<{
  text: string;
  startMs: number;
  endMs: number;
  fontSize: number;
  color: string;
  backgroundColor: string;
  fontFamily: string;
}> = ({ text, startMs, endMs, fontSize, color, backgroundColor, fontFamily }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = startMs + (frame / fps) * 1000;
  const progress = (currentMs - startMs) / (endMs - startMs);

  const entrance = spring({ frame, fps, config: { damping: 16, stiffness: 100 } });
  const exit = interpolate(progress, [0.7, 1], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 100 }}>
      <div
        style={{
          opacity: Math.min(entrance, exit),
          transform: `translateY(${interpolate(entrance, [0, 1], [24, 0])}px)`,
          backgroundColor,
          borderRadius: 14,
          padding: "16px 32px",
          maxWidth: "84%",
          textAlign: "center",
        }}
      >
        <span style={{ fontSize, fontWeight: 700, fontFamily, lineHeight: 1.5, color, whiteSpace: "pre-wrap" }}>
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export const SentenceCaption: React.FC<Props> = ({
  sentences,
  fontSize = 40,
  color = "#F8FAFC",
  backgroundColor = "rgba(0, 0, 0, 0.55)",
  fontFamily = "Noto Serif SC, SimSun, serif",
}) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill>
      {sentences.map((s, i) => {
        const fromFrame = Math.round((s.startMs / 1000) * fps);
        const nextStart = sentences[i + 1]?.startMs ?? s.endMs + 500;
        const duration = Math.max(1, Math.round(((nextStart - s.startMs) / 1000) * fps));

        return (
          <Sequence key={i} from={fromFrame} durationInFrames={duration}>
            <SentenceRenderer
              text={s.text}
              startMs={s.startMs}
              endMs={s.endMs}
              fontSize={fontSize}
              color={color}
              backgroundColor={backgroundColor}
              fontFamily={fontFamily}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
