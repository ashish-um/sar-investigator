// ── DOM References & Global State ──────────────────────────────────
const investigateBtn = document.getElementById('investigate-btn');
const alertSelect = document.getElementById('alert-select');
const alertInput = document.getElementById('alert-input');
const outputContainer = document.getElementById('output-container');
const statusIndicator = document.getElementById('status-indicator');
const runningIndicator = document.getElementById('running-indicator');

let currentThinkingBlock = null;
let loadedAlerts = {};
let fullOutputLog = "";
let lastVerdictData = null;

const evidenceDrawer = document.getElementById('evidence-drawer');
const drawerOverlay = document.getElementById('drawer-overlay');
const drawerTitle = document.getElementById('drawer-title');
const drawerSubtitle = document.getElementById('drawer-subtitle');
const drawerContent = document.getElementById('drawer-content');
