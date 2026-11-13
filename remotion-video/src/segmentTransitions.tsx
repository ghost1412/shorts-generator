// Transitions between the background segments of a video (stock clips, photos), using Remotion's official @remotion/transitions package.
// The cut points stay where the audio and the captions expect them: every segment runs a little longer under the next one, so the
// transition starts at the old cut time and the total length does not change.
import React from "react";
import { TransitionSeries, linearTiming, type TransitionPresentation } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { flip } from "@remotion/transitions/flip";
import { clockWipe } from "@remotion/transitions/clock-wipe";
import { iris } from "@remotion/transitions/iris";
import { Sequence, useVideoConfig } from "remotion";

export const SEGMENT_TRANSITIONS = ["fade", "slide", "wipe", "flip", "clock-wipe", "iris"] as const;
export type SegmentTransition = (typeof SEGMENT_TRANSITIONS)[number];

export const TRANSITION_FRAMES = 12;

// Segments must follow each other without gaps (within a few frames) for the cut times to stay put.
export const canTransition = (items: { start: number; end: number }[], fps: number) =>
  items.length > 1 && items.every((it, i) => i === 0 || Math.abs(it.start - items[i - 1].end) * fps <= 3);

export const SegmentTransitionSeries: React.FC<{
  items: { start: number; end: number }[];
  kind: SegmentTransition;
  render: (index: number, durationInFrames: number) => React.ReactNode;
}> = ({ items, kind, render }) => {
  const { fps, width, height } = useVideoConfig();
  const presentation = (
    kind === "slide" ? slide() : kind === "wipe" ? wipe() : kind === "flip" ? flip() : kind === "clock-wipe" ? clockWipe({ width, height }) : kind === "iris" ? iris({ width, height }) : fade()
  ) as unknown as TransitionPresentation<Record<string, unknown>>;
  const children: React.ReactNode[] = [];
  items.forEach((it, i) => {
    const last = i === items.length - 1;
    const base = Math.max(1, Math.round((it.end - it.start) * fps));
    const dur = base + (last ? 0 : TRANSITION_FRAMES);
    children.push(
      <TransitionSeries.Sequence key={`s${i}`} durationInFrames={dur}>
        {render(i, dur)}
      </TransitionSeries.Sequence>,
    );
    if (!last) children.push(<TransitionSeries.Transition key={`t${i}`} presentation={presentation} timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })} />);
  });
  return (
    <Sequence from={Math.round(items[0].start * fps)} layout="none">
      <TransitionSeries>{children}</TransitionSeries>
    </Sequence>
  );
};
