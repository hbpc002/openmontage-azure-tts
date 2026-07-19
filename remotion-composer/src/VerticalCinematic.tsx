import React from "react";
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { SentenceCaption, SentenceCaptionItem } from "./components/SentenceCaption";
import {
  CinematicRendererProps,
  CinematicVideoScene,
  CinematicTitleScene,
} from "./cinematic/types";

function resolveAsset(src: string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) return src;
  const clean = src.replace(/^file:\/\/\/?/, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[/\\]/.test(clean)) {
    const posix = clean.replace(/\\/g, "/");
    if (posix.startsWith("/")) return `file://${posix}`;
    return `file:///${posix}`;
  }
  return staticFile(clean);
}

const FPS = 30;

const SceneVideo: React.FC<{ scene: CinematicVideoScene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fadeInFrames = scene.fadeInFrames ?? 10;
  const fadeOutFrames = scene.fadeOutFrames ?? 10;
  const fadeOutStart = Math.max(fadeInFrames, durationInFrames - fadeOutFrames);
  const opacity = Math.min(
    fadeInFrames === 0 ? 1 : interpolate(frame, [0, fadeInFrames], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    fadeOutFrames === 0 ? 1 : interpolate(frame, [fadeOutStart, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  );
  const scale = interpolate(frame, [0, durationInFrames], [1.03, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const filter = scene.filter ?? "contrast(1.04) saturate(0.85) brightness(0.78)";

  return (
    <AbsoluteFill style={{ opacity }}>
      <OffthreadVideo
        muted
        src={resolveAsset(scene.src)}
        style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})`, filter }}
      />
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(10,8,6,0.25) 0%, rgba(2,2,4,0.55) 100%)" }} />
    </AbsoluteFill>
  );
};

const TextOverlay: React.FC<{ text: string; index: number; totalTexts: number }> = ({ text, index, totalTexts }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const progress = interpolate(frame, [0, Math.min(20, durationInFrames / 2)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const exit = interpolate(frame, [durationInFrames - 15, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const lines = text.split("\n");
  const yOffset = totalTexts === 1 ? 0 : (index - (totalTexts - 1) / 2) * 100;

  return (
    <div
      style={{
        position: "absolute",
        left: "8%",
        right: "8%",
        top: "50%",
        transform: `translateY(calc(-50% + ${yOffset}px))`,
        textAlign: "center",
        fontFamily: "Noto Serif SC, SimSun, serif",
        fontWeight: 400,
        fontSize: 42,
        lineHeight: 1.6,
        color: "rgba(245,235,220,0.92)",
        textShadow: "0 2px 20px rgba(0,0,0,0.6)",
        opacity: Math.min(progress, exit),
        letterSpacing: "0.08em",
      }}
    >
      {lines.map((line, i) => (
        <div key={i} style={{ marginBottom: 8 }}>{line}</div>
      ))}
    </div>
  );
};

const Soundtrack: React.FC<{
  src: string; volume: number;
  trimBeforeSeconds?: number; trimAfterSeconds?: number;
  fadeInSeconds: number; fadeOutSeconds: number;
}> = ({ src, volume, trimBeforeSeconds, trimAfterSeconds, fadeInSeconds, fadeOutSeconds }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const fi = Math.max(1, Math.round(fadeInSeconds * fps));
  const fo = Math.max(1, Math.round(fadeOutSeconds * fps));
  const fadeIn = interpolate(frame, [0, fi], [0, volume], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [durationInFrames - fo, durationInFrames], [volume, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <Audio src={resolveAsset(src)} trimBefore={trimBeforeSeconds !== undefined ? Math.round(trimBeforeSeconds * fps) : undefined} trimAfter={trimAfterSeconds !== undefined ? Math.round(trimAfterSeconds * fps) : undefined} volume={() => Math.min(fadeIn, fadeOut)} />;
};

export const calculateVerticalCinematicMetadata: CalculateMetadataFunction<CinematicRendererProps> = async ({ props }) => {
  const totalSeconds = props.scenes.length === 0 ? 30 : Math.max(...props.scenes.map(s => s.startSeconds + s.durationSeconds));
  return { durationInFrames: Math.max(1, Math.ceil(totalSeconds * FPS)), fps: FPS, width: 1080, height: 1920 };
};

export const VerticalCinematic: React.FC<CinematicRendererProps> = ({ scenes, soundtrack, music, captions }) => {
  const titleScenes = scenes.filter((s): s is CinematicTitleScene & { kind: "title" } => s.kind === "title");
  const videoScenes = scenes.filter((s): s is CinematicVideoScene => s.kind === "video");

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0806" }}>
      {soundtrack ? <Soundtrack src={soundtrack.src} volume={soundtrack.volume ?? 1} fadeInSeconds={soundtrack.fadeInSeconds ?? 0.3} fadeOutSeconds={soundtrack.fadeOutSeconds ?? 0.5}
        trimBeforeSeconds={soundtrack.trimBeforeSeconds} trimAfterSeconds={soundtrack.trimAfterSeconds} /> : null}
      {music ? <Soundtrack src={music.src} volume={music.volume ?? 0.15} fadeInSeconds={music.fadeInSeconds ?? 2} fadeOutSeconds={music.fadeOutSeconds ?? 3}
        trimBeforeSeconds={music.trimBeforeSeconds} trimAfterSeconds={music.trimAfterSeconds} /> : null}
      {videoScenes.map(scene => (
        <Sequence key={scene.id} from={Math.round(scene.startSeconds * FPS)} durationInFrames={Math.round(scene.durationSeconds * FPS)}>
          <SceneVideo scene={scene} />
        </Sequence>
      ))}
      {titleScenes.map((scene, i) => (
        <Sequence key={scene.id} from={Math.round(scene.startSeconds * FPS)} durationInFrames={Math.round(scene.durationSeconds * FPS)}>
          <TextOverlay text={scene.text} index={i} totalTexts={titleScenes.length} />
        </Sequence>
      ))}
      {captions?.sentences ? (
        <SentenceCaption sentences={captions.sentences as SentenceCaptionItem[]} fontSize={captions.fontSize ?? 38}
          color={captions.color ?? "#F8FAFC"}
          backgroundColor={captions.backgroundColor ?? "rgba(0,0,0,0.55)"} />
      ) : null}
    </AbsoluteFill>
  );
};
