// "Overlay" composition: only the visual template and the intro / outro covers on a transparent background. Rendered as short alpha clips
// that FFmpeg lays over a long video (the highlights video), so a long video never has to be rendered frame by frame in the browser.
import React from "react";
import { AbsoluteFill } from "remotion";
import { z } from "zod";
import { ClockContext } from "./clock";
import { TemplateLayer, templateTextSchema, VISUAL_TEMPLATES } from "./visualTemplates";
import { TransitionLayer, TRANSITIONS } from "./transitions";

export const overlaySchema = z.object({
  visualTemplate: z.enum(VISUAL_TEMPLATES).optional(),
  templateText: templateTextSchema.optional(),
  templateAccent: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
  introAnimation: z.enum(TRANSITIONS).optional(),
  outroAnimation: z.enum(TRANSITIONS).optional(),
  animationColor: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
  hookSeconds: z.number().default(0),
  seconds: z.number().default(3), // length of this piece
  clockOffset: z.number().default(0), // where this piece starts in the whole video
  clockTotal: z.number().default(10), // length of the whole video
});

export const OverlayOnly: React.FC<z.infer<typeof overlaySchema>> = ({ visualTemplate, templateText, templateAccent, introAnimation, outroAnimation, animationColor, hookSeconds, clockOffset, clockTotal }) => (
  <ClockContext.Provider value={{ offset: clockOffset, total: clockTotal }}>
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {visualTemplate && <TemplateLayer template={visualTemplate} text={templateText} accent={templateAccent} hookSeconds={hookSeconds} />}
      {(introAnimation || outroAnimation) && <TransitionLayer intro={introAnimation} outro={outroAnimation} color={animationColor} />}
    </AbsoluteFill>
  </ClockContext.Provider>
);
