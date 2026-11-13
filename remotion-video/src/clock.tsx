// A clock for pieces rendered on their own: an overlay clip made for seconds 1190-1200 of a 20 minute video still has to know it is at
// the end of the video (end-card timing, progress bar). Without a provider the layers use the composition's own time.
import { createContext } from "react";

export const ClockContext = createContext<{ offset: number; total: number } | null>(null);
