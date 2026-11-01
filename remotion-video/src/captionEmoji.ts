// Emoji that pop next to a spoken keyword in single-word caption styles (HORMOZI, BOUNCE).
const EMOJI_BY_WORD: Record<string, string> = {
  money: "💰", cash: "💵", dollar: "💵", dollars: "💵", rich: "🤑", million: "💰", billion: "💰", price: "🏷️", prices: "🏷️",
  fire: "🔥", hot: "🔥", insane: "🤯", crazy: "🤪", mind: "🤯", wow: "😮", shocking: "😱", scary: "😱", fear: "😨",
  love: "❤️", heart: "❤️", happy: "😊", laugh: "😂", funny: "😂", sad: "😢", cry: "😢", angry: "😡",
  secret: "🤫", hidden: "🕵️", truth: "👀", lie: "🤥", lies: "🤥", wrong: "❌", right: "✅", correct: "✅", stop: "🛑",
  time: "⏰", fast: "⚡", power: "⚡", energy: "⚡", brain: "🧠", smart: "🧠", genius: "🧠", idea: "💡",
  win: "🏆", winner: "🏆", best: "🏆", top: "🏆", success: "🚀", growth: "📈", grow: "📈", launch: "🚀",
  warning: "⚠️", danger: "⚠️", dead: "💀", death: "💀", kill: "💀", die: "💀",
  space: "🚀", earth: "🌍", world: "🌍", sun: "☀️", moon: "🌙", star: "⭐", stars: "⭐",
  phone: "📱", computer: "💻", code: "👨‍💻", ai: "🤖", robot: "🤖", video: "🎬", music: "🎵", game: "🎮",
  food: "🍔", eat: "🍽️", water: "💧", health: "💪", gym: "💪", strong: "💪", sleep: "😴",
  question: "❓", why: "🤔", think: "🤔", think_: "🤔", look: "👀", watch: "👀", see: "👀", listen: "👂",
};

export const emojiForWord = (word: string): string => {
  const clean = word.toLowerCase().replace(/[^a-z]/g, "");
  return EMOJI_BY_WORD[clean] ?? "";
};
