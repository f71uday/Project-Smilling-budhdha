const pptxgen = require("pptxgenjs");
const { execFileSync } = require("child_process");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Uday";
pres.subject = "Pfizer channel engagement discovery";
pres.title = "Uday - Channel Engagement Review";
pres.company = "Project Sankalp";
pres.lang = "en-IN";

pres.defineSlideMaster({
  title: "Dark Cover",
  background: { color: "123B40" },
  objects: [
    { rect: { x: 0, y: 0, w: 13.33, h: 7.5, fill: { color: "123B40" }, line: { color: "123B40" } } },
  ],
  slideNumber: { x: 12.45, y: 7.05, w: 0.4, h: 0.22, color: "B9D6D2", fontFace: "Arial", fontSize: 9, align: "right" },
});

pres.defineSlideMaster({
  title: "Light Context",
  background: { color: "F5F8F7" },
  objects: [
    { rect: { x: 0, y: 0, w: 13.33, h: 7.5, fill: { color: "F5F8F7" }, line: { color: "F5F8F7" } } },
  ],
  slideNumber: { x: 12.45, y: 7.05, w: 0.4, h: 0.22, color: "6D7D7A", fontFace: "Arial", fontSize: 9, align: "right" },
});

pres.theme = {
  headFontFace: "Cambria",
  bodyFontFace: "Arial",
  lang: "en-IN",
};

const C = {
  ink: "173335",
  teal: "123B40",
  teal2: "1F6668",
  mint: "78BDAA",
  pale: "DDEBE7",
  white: "FFFFFF",
  offWhite: "F5F8F7",
  muted: "617573",
  coral: "D96C5F",
  gold: "E4B95E",
};

pres.addSection({ title: "Opening" });
const cover = pres.addSlide({ masterName: "Dark Cover", sectionTitle: "Opening" });

cover.addText("PROJECT SANKALP", {
  x: 0.85, y: 0.65, w: 4.2, h: 0.32,
  fontFace: "Arial", fontSize: 14, bold: true, charSpacing: 2.4,
  color: C.mint, margin: 0, isTextBox: true,
});

cover.addText("Turning channel complexity\ninto controlled decisions", {
  x: 0.85, y: 1.55, w: 7.45, h: 1.7,
  fontFace: "Cambria", fontSize: 36, bold: true,
  color: C.white, margin: 0, breakLine: false, isTextBox: true,
});

cover.addText("A data-led review of claims, sales schemes and stock controls across Pfizer's domestic channel", {
  x: 0.85, y: 3.45, w: 6.5, h: 0.92,
  fontFace: "Arial", fontSize: 18, color: "D4E5E1",
  margin: 0, breakLine: false, isTextBox: true,
});

cover.addText("Uday", {
  x: 0.85, y: 6.25, w: 2.5, h: 0.34,
  fontFace: "Arial", fontSize: 14, bold: true, color: C.white, margin: 0, isTextBox: true,
});
cover.addText("20 November 2026", {
  x: 0.85, y: 6.58, w: 2.5, h: 0.28,
  fontFace: "Arial", fontSize: 11, color: "B9D6D2", margin: 0, isTextBox: true,
});

// Cover visual: connected channel checkpoints.
const nodes = [
  { x: 9.15, y: 1.4, r: 0.58, label: "Claim", c: "78BDAA" },
  { x: 10.75, y: 2.55, r: 0.58, label: "Scheme", c: "DDEBE7" },
  { x: 9.15, y: 3.72, r: 0.58, label: "Stock", c: "E4B95E" },
  { x: 10.75, y: 4.87, r: 0.58, label: "Credit", c: "D96C5F" },
];
cover.addShape(pres.ShapeType.line, { x: 9.73, y: 1.98, w: 1.6, h: 0.57, line: { color: "83AFA8", width: 2 } });
cover.addShape(pres.ShapeType.line, { x: 10.75, y: 3.13, w: -1.6, h: 0.59, line: { color: "83AFA8", width: 2 } });
cover.addShape(pres.ShapeType.line, { x: 9.73, y: 4.30, w: 1.6, h: 0.57, line: { color: "83AFA8", width: 2 } });
nodes.forEach((n) => {
  cover.addShape(pres.ShapeType.ellipse, {
    x: n.x, y: n.y, w: n.r * 2, h: n.r * 2,
    fill: { color: n.c }, line: { color: n.c },
  });
  cover.addText(n.label, {
    x: n.x, y: n.y + 0.38, w: n.r * 2, h: 0.3,
    fontFace: "Arial", fontSize: 11, bold: true,
    color: n.c === "DDEBE7" ? C.ink : C.ink,
    align: "center", margin: 0, isTextBox: true,
  });
});
cover.addNotes("Opening slide for the Project Sankalp discovery review.");

pres.addSection({ title: "Context" });
const context = pres.addSlide({ masterName: "Light Context", sectionTitle: "Context" });

context.addText("Context & objectives", {
  x: 0.78, y: 0.48, w: 6.2, h: 0.55,
  fontFace: "Cambria", fontSize: 36, bold: true,
  color: C.ink, margin: 0, isTextBox: true,
});
context.addText("Establish where value is leaking, and what a controlled claim workflow should do", {
  x: 0.78, y: 1.12, w: 11.7, h: 0.38,
  fontFace: "Arial", fontSize: 15, color: C.muted, margin: 0, isTextBox: true,
});

// Evidence snapshot
context.addShape(pres.ShapeType.roundRect, {
  x: 0.78, y: 1.78, w: 3.15, h: 4.78,
  rectRadius: 0.12,
  fill: { color: C.teal }, line: { color: C.teal },
});
context.addText("₹79.82m", {
  x: 1.08, y: 2.18, w: 2.55, h: 0.78,
  fontFace: "Cambria", fontSize: 34, bold: true,
  color: C.white, margin: 0, align: "left", isTextBox: true,
});
context.addText("claim value in the register", {
  x: 1.08, y: 2.95, w: 2.35, h: 0.55,
  fontFace: "Arial", fontSize: 14, color: "D4E5E1", margin: 0, isTextBox: true,
});
context.addShape(pres.ShapeType.line, {
  x: 1.08, y: 3.72, w: 2.3, h: 0,
  line: { color: "7DA8A1", width: 1 },
});
context.addText("The immediate question", {
  x: 1.08, y: 4.02, w: 2.35, h: 0.32,
  fontFace: "Arial", fontSize: 13, bold: true, color: C.mint, margin: 0, isTextBox: true,
});
context.addText("Can Commercial Operations validate, prioritise and resolve claims before money and stock are exposed?", {
  x: 1.08, y: 4.42, w: 2.35, h: 1.4,
  fontFace: "Arial", fontSize: 16, bold: true, color: C.white,
  margin: 0, breakLine: false, isTextBox: true,
});

// Objective cards
const cards = [
  {
    x: 4.32, y: 1.78, w: 2.62, h: 2.18,
    num: "01", title: "Validate",
    text: "Reconcile claim, invoice, batch, stockist and SKU evidence",
    accent: "78BDAA",
  },
  {
    x: 7.12, y: 1.78, w: 2.62, h: 2.18,
    num: "02", title: "Prioritise",
    text: "Surface ageing, high-value and policy-breach work for action",
    accent: "E4B95E",
  },
  {
    x: 9.92, y: 1.78, w: 2.62, h: 2.18,
    num: "03", title: "Protect",
    text: "Reduce rework, expiry exposure and uncontrolled credit decisions",
    accent: "D96C5F",
  },
];

cards.forEach((card) => {
  context.addShape(pres.ShapeType.roundRect, {
    x: card.x, y: card.y, w: card.w, h: card.h,
    rectRadius: 0.10,
    fill: { color: C.white }, line: { color: "D6E1DE", width: 1 },
  });
  context.addText(card.num, {
    x: card.x + 0.18, y: card.y + 0.16, w: 0.55, h: 0.28,
    fontFace: "Arial", fontSize: 12, bold: true, color: C.teal2,
    margin: 0, isTextBox: true,
  });
  context.addShape(pres.ShapeType.ellipse, {
    x: card.x + card.w - 0.58, y: card.y + 0.16, w: 0.34, h: 0.34,
    fill: { color: card.accent }, line: { color: card.accent },
  });
  context.addText(card.title, {
    x: card.x + 0.18, y: card.y + 0.62, w: card.w - 0.36, h: 0.38,
    fontFace: "Cambria", fontSize: 22, bold: true, color: C.ink,
    margin: 0, isTextBox: true,
  });
  context.addText(card.text, {
    x: card.x + 0.18, y: card.y + 1.08, w: card.w - 0.36, h: 0.82,
    fontFace: "Arial", fontSize: 13.5, color: C.muted,
    margin: 0, breakLine: false, isTextBox: true,
  });
});

// Decision bands
context.addText("What success looks like", {
  x: 4.32, y: 4.28, w: 3.2, h: 0.34,
  fontFace: "Arial", fontSize: 14, bold: true, color: C.ink,
  margin: 0, isTextBox: true,
});
const outcomes = [
  ["One auditable record", "Every claim carries a traceable evidence trail"],
  ["A ranked workqueue", "Exceptions are visible before credits are processed"],
  ["Policy-first decisions", "Expiry, quantity and timing rules are applied consistently"],
];
outcomes.forEach((item, i) => {
  const y = 4.74 + i * 0.62;
  context.addShape(pres.ShapeType.ellipse, {
    x: 4.32, y: y + 0.05, w: 0.24, h: 0.24,
    fill: { color: i === 0 ? C.mint : i === 1 ? C.gold : C.coral },
    line: { color: i === 0 ? C.mint : i === 1 ? C.gold : C.coral },
  });
  context.addText([
    { text: item[0] + "  ", options: { bold: true, color: C.ink } },
    { text: item[1], options: { color: C.muted } },
  ], {
    x: 4.72, y, w: 7.82, h: 0.38,
    fontFace: "Arial", fontSize: 13.5, margin: 0, isTextBox: true,
  });
});

context.addText("Source: claim_register.csv (4,526 rows) | claim_control_analysis.py", {
  x: 4.32, y: 6.68, w: 7.8, h: 0.22,
  fontFace: "Arial", fontSize: 9, color: "7A8B88", margin: 0, isTextBox: true,
});
context.addNotes("Frame the project as a controlled claim-validation and workqueue outcome. The ₹79.82 million figure is the total claim value in the supplied register.\n\nWhy prioritise claims first: claims have immediate, measurable money exposure and can be acted on with the data already available. The register contains 4,526 claims worth ₹79.82 million, including 3,130 claims that took more than 30 days and are worth ₹52.84 million, plus 366 pending claims worth ₹9.51 million. We can therefore validate evidence, rank urgent exceptions and route claims for resolution before incorrect approvals or further delays affect credit and stock decisions.\n\nScheme and stock risks are also important, but secondary-sales evidence is incomplete. They should be added after the claim-control MVP is producing verified, auditable decisions.");

const outFile = path.join(__dirname, "Sankalp_Intro_Two_Slides.pptx");
pres.writeFile({ fileName: outFile }).then(() => {
  console.log(outFile);

  const themeFile = path.join(__dirname, "theme.json");
  const applyTheme = path.join("/Users/uday/.agents/skills/pptx/scripts", "apply_theme.js");
  execFileSync(process.execPath, [applyTheme, outFile, themeFile], {
    stdio: "inherit",
    env: { ...process.env, NODE_PATH: path.join(__dirname, "node_modules") },
  });
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
