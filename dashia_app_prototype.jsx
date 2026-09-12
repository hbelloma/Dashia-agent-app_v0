import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Home, Sparkles, Cpu, TrendingUp, BarChart3, Wallet, Link2,
  ShieldCheck, Mic, Send, Play, Plus, CheckCircle2, Trophy, Lock,
  AlertTriangle, X, Eye, EyeOff, Loader2, ChevronLeft,
  GripVertical, ArrowUp, ArrowDown, Trash2,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
  CartesianGrid, LineChart, Line,
} from "recharts";

/* ============================================================
   TOKENS — paleta y tipografía (ver notas de diseño al final)
   ============================================================ */
const C = {
  bg: "#0A0D14",
  panel: "#11141F",
  panelRaised: "#191D2C",
  border: "#242A3D",
  borderSoft: "#1B2032",
  text: "#EDEFF6",
  textDim: "#8A90A8",
  textFaint: "#565C74",
  amber: "#E8A33D",
  amberDim: "#8A6A34",
  violet: "#8B7CF6",
  violetDim: "#4A4380",
  up: "#34C77B",
  down: "#E8556B",
};

const FONT_UI = '"Space Grotesk", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif';
const FONT_MONO = '"IBM Plex Mono", ui-monospace, "SFMono-Regular", Consolas, monospace';

/* ============================================================
   i18n
   ============================================================ */
const STR = {
  es: {
    appName: "Dashboard",
    tabs: { dash: "Inicio", dashia: "DASHIA", agents: "Agentes", backtest: "Backtest", stats: "Stats" },
    connectCex: "Conectar exchange", connectWallet: "Conectar Phantom",
    connected: "conectado", notConnected: "sin conectar",
    equity: "Equity total", liveMarket: "Mercado en vivo",
    myAgents: "Mis agentes", active: "activo", paused: "en pausa",
    trades: "operaciones", winRate: "acierto",
    dashiaTag: "Clasificador ANN · distancia Lorentziana",
    dashiaDesc: "Estrategia cuantitativa multi-indicador con filtro de kernel y gestión de riesgo por planes.",
    activateAgent: "Activar agente", deactivateAgent: "Pausar agente",
    riskPlan: "Plan de riesgo", venue: "Mercado", asset: "Activo",
    chatPlaceholder: "Escríbele a DASHIA…", listening: "Escuchando…",
    watchIntro: "Ver introducción",
    newAgent: "Crear agente nuevo", agentName: "Nombre del agente",
    strategyMode: "Modo de estrategia", codeMode: "Código", visualMode: "Constructor visual",
    strategyCode: "Código de la estrategia", saveAgent: "Guardar agente",
    yourAgents: "Tus agentes creados", noCustomAgents: "Aún no has creado ningún agente propio.",
    runBacktest: "Correr backtest", backtestOn: "Backtest de", period: "Periodo",
    initialCapital: "Capital inicial", finalCapital: "Capital final",
    totalReturn: "Retorno total", maxDrawdown: "Max. drawdown",
    running: "Simulando…", simulatedData: "Datos simulados para este prototipo",
    historyTitle: "Historial de operaciones", pnlOverTime: "P&L acumulado",
    side: "Lado", result: "Resultado", competitionSoon: "Competencia de agentes — próximamente",
    noWithdraw: "Solo trading, sin permiso de retiro", ipWhitelist: "Whitelist de IP activa",
    long: "Long", short: "Short",
    phantomNotDetected: "No se detectó la extensión de Phantom en este navegador",
    installPhantom: "Instalar Phantom", connecting: "Conectando…",
    phantomRejected: "Conexión rechazada en Phantom", tryAgain: "Reintentar",
    disconnect: "Desconectar", copyAddress: "Copiar dirección", copied: "¡Copiado!",
    operationalWallet: "Wallet operativa de DASHIA",
    operationalWalletDesc: "Deposita aquí un monto acotado para que el agente opere — tu wallet principal nunca entrega su llave privada.",
    mobileNote: "Esto conecta la extensión de escritorio de Phantom. La app nativa usará el protocolo de deep link de Phantom para iOS/Android.",
    addRule: "Agregar regla", rule: "Regla", addCondition: "Agregar condición",
    when: "CUANDO", then: "ENTONCES", logicAnd: "Y (todas)", logicOr: "O (alguna)",
    actionBuy: "Comprar", actionSell: "Vender", actionHold: "Esperar",
    sizeSmall: "Pequeño (2%)", sizeDefault: "Normal (5%)", sizeLarge: "Grande (10%)",
    codePreview: "Código generado", noRulesYet: "Aún no hay reglas — probá una plantilla o agregá la primera",
    ruleOrderNote: "El orden importa: se aplica la primera regla que se cumpla",
    templateOversold: "RSI sobrecomprado/sobrevendido",
    indRsi: "RSI", indSma: "Media móvil (SMA)", indEma: "Media exponencial (EMA)",
    indPrice: "Precio", indVolume: "Volumen", indTrend: "Tendencia", indPosition: "Posición actual",
    selectExchange: "Elige tu exchange", apiKeyLabel: "API Key", apiSecretLabel: "API Secret",
    testnetLabel: "Usar testnet (recomendado para probar)",
    checklistTitle: "Antes de continuar, confirma en el dashboard del exchange:",
    weexManualLabel: "Confirmo que revisé en el dashboard de Weex que esta key NO tiene permiso de retiro habilitado",
    connectButton: "Conectar", verifying: "Verificando permisos…",
    verifiedBadge: "Verificado", connectFailedTitle: "No se pudo verificar",
    backButton: "Atrás", cancelButton: "Cancelar",
    demoWarning: "Prototipo de diseño — no ingreses una API key real todavía. El backend que guarda esto cifrado de verdad aún no está desplegado.",
    addAnother: "Conectar otro exchange", connectedAccounts: "Cuentas conectadas",
    endsIn: "Termina en", noAutoVerify: "Sin verificación automática",
    testnetBadge: "Testnet", liveBadge: "Real", disconnectConfirmTitle: "¿Desconectar esta cuenta?",
    fillRequired: "Completa API Key y API Secret",
  },
  en: {
    appName: "Dashboard",
    tabs: { dash: "Home", dashia: "DASHIA", agents: "Agents", backtest: "Backtest", stats: "Stats" },
    connectCex: "Connect exchange", connectWallet: "Connect Phantom",
    connected: "connected", notConnected: "not connected",
    equity: "Total equity", liveMarket: "Live market",
    myAgents: "My agents", active: "active", paused: "paused",
    trades: "trades", winRate: "win rate",
    dashiaTag: "ANN classifier · Lorentzian distance",
    dashiaDesc: "Multi-indicator quant strategy with kernel filtering and plan-based risk management.",
    activateAgent: "Activate agent", deactivateAgent: "Pause agent",
    riskPlan: "Risk plan", venue: "Venue", asset: "Asset",
    chatPlaceholder: "Message DASHIA…", listening: "Listening…",
    watchIntro: "Watch intro",
    newAgent: "Create new agent", agentName: "Agent name",
    strategyMode: "Strategy mode", codeMode: "Code", visualMode: "Visual builder",
    strategyCode: "Strategy code", saveAgent: "Save agent",
    yourAgents: "Your custom agents", noCustomAgents: "You haven't created a custom agent yet.",
    runBacktest: "Run backtest", backtestOn: "Backtesting", period: "Period",
    initialCapital: "Initial capital", finalCapital: "Final capital",
    totalReturn: "Total return", maxDrawdown: "Max drawdown",
    running: "Simulating…", simulatedData: "Simulated data for this prototype",
    historyTitle: "Trade history", pnlOverTime: "Cumulative P&L",
    side: "Side", result: "Result", competitionSoon: "Agent competition — coming soon",
    noWithdraw: "Trade-only, no withdrawal permission", ipWhitelist: "IP whitelist active",
    long: "Long", short: "Short",
    phantomNotDetected: "Phantom extension not detected in this browser",
    installPhantom: "Install Phantom", connecting: "Connecting…",
    phantomRejected: "Connection rejected in Phantom", tryAgain: "Try again",
    disconnect: "Disconnect", copyAddress: "Copy address", copied: "Copied!",
    operationalWallet: "DASHIA operational wallet",
    operationalWalletDesc: "Deposit a capped amount here for the agent to trade with — your main wallet never hands over its private key.",
    mobileNote: "This connects Phantom's desktop extension. The native app will use Phantom's deep-link protocol for iOS/Android.",
    addRule: "Add rule", rule: "Rule", addCondition: "Add condition",
    when: "WHEN", then: "THEN", logicAnd: "AND (all)", logicOr: "OR (any)",
    actionBuy: "Buy", actionSell: "Sell", actionHold: "Wait",
    sizeSmall: "Small (2%)", sizeDefault: "Normal (5%)", sizeLarge: "Large (10%)",
    codePreview: "Generated code", noRulesYet: "No rules yet — try a template or add your first one",
    ruleOrderNote: "Order matters: the first matching rule applies",
    templateOversold: "RSI overbought/oversold",
    indRsi: "RSI", indSma: "Moving average (SMA)", indEma: "Exponential MA (EMA)",
    indPrice: "Price", indVolume: "Volume", indTrend: "Trend", indPosition: "Current position",
    selectExchange: "Choose your exchange", apiKeyLabel: "API Key", apiSecretLabel: "API Secret",
    testnetLabel: "Use testnet (recommended for testing)",
    checklistTitle: "Before continuing, confirm on the exchange dashboard:",
    weexManualLabel: "I confirm I checked on the Weex dashboard that this key does NOT have withdrawal permission",
    connectButton: "Connect", verifying: "Verifying permissions…",
    verifiedBadge: "Verified", connectFailedTitle: "Couldn't verify",
    backButton: "Back", cancelButton: "Cancel",
    demoWarning: "Design prototype — don't enter a real API key yet. The backend that actually encrypts and stores this isn't deployed yet.",
    addAnother: "Connect another exchange", connectedAccounts: "Connected accounts",
    endsIn: "Ends in", noAutoVerify: "No automatic verification",
    testnetBadge: "Testnet", liveBadge: "Live", disconnectConfirmTitle: "Disconnect this account?",
    fillRequired: "Fill in API Key and API Secret",
  },
};

/* ============================================================
   MOCK DATA
   ============================================================ */
const MARKET_SEED = [
  { sym: "BTC", price: 61234, chg: 2.31 },
  { sym: "ETH", price: 3021, chg: 1.02 },
  { sym: "SOL", price: 148.2, chg: 4.87 },
  { sym: "LTC", price: 84.1, chg: -0.65 },
  { sym: "XRP", price: 0.612, chg: -1.14 },
  { sym: "ARB", price: 0.78, chg: 3.02 },
  { sym: "XAU", price: 2412.3, chg: 0.21 },
  { sym: "WIF", price: 2.41, chg: 12.4 },
];

const AGENTS_SEED = [
  { id: "dashia", name: "DASHIA", builtIn: true, active: true, pnlPct: 8.4, trades: 12, winRate: 66.7, venue: "Binance · Futuros", risk: "WALK" },
];

const TRADE_HISTORY = [
  { id: 1, date: "2026-09-01", agent: "DASHIA", asset: "BTC", side: "long", pnl: 214.5 },
  { id: 2, date: "2026-09-02", agent: "DASHIA", asset: "SOL", side: "short", pnl: -58.2 },
  { id: 3, date: "2026-09-03", agent: "DASHIA", asset: "ETH", side: "long", pnl: 132.9 },
  { id: 4, date: "2026-09-05", agent: "DASHIA", asset: "BTC", side: "short", pnl: 91.0 },
  { id: 5, date: "2026-09-06", agent: "DASHIA", asset: "ARB", side: "long", pnl: 47.3 },
  { id: 6, date: "2026-09-08", agent: "DASHIA", asset: "SOL", side: "long", pnl: -22.1 },
];

let pnlAcc = 0;
const PNL_CURVE = TRADE_HISTORY.map((t) => {
  pnlAcc += t.pnl;
  return { date: t.date.slice(5), pnl: Math.round(pnlAcc) };
});

const CHAT_SEED_ES = [
  { from: "dashia", text: "Hola, soy DASHIA. Opero con un clasificador ANN de distancia Lorentziana sobre BTC, ETH, SOL y algunas más. ¿Quieres que active el plan WALK en Binance?" },
];
const CHAT_SEED_EN = [
  { from: "dashia", text: "Hi, I'm DASHIA. I trade with a Lorentzian-distance ANN classifier across BTC, ETH, SOL and more. Want me to activate the WALK plan on Binance?" },
];

/* ============================================================
   MEDIA — foto real y miniaturas de los videos de introducción
   (incrustadas como data URI; los .mp4 completos no entran en
   un artifact por tamaño, se comparten aparte en el chat)
   ============================================================ */
const AVATAR_IMG = "data:image/jpeg;base64,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";
const INTRO_THUMB = {
  es: { img: "data:image/jpeg;base64,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", duration: "0:59" },
  en: { img: "data:image/jpeg;base64,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", duration: "0:42" },
};

/* ============================================================
   UI PRIMITIVES
   ============================================================ */
function Card({ children, style, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: 16,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function Pill({ children, tone = "neutral" }) {
  const tones = {
    neutral: { bg: C.panelRaised, color: C.textDim, border: C.border },
    up: { bg: "rgba(52,199,123,0.12)", color: C.up, border: "rgba(52,199,123,0.35)" },
    down: { bg: "rgba(232,85,107,0.12)", color: C.down, border: "rgba(232,85,107,0.35)" },
    amber: { bg: "rgba(232,163,61,0.12)", color: C.amber, border: "rgba(232,163,61,0.35)" },
    violet: { bg: "rgba(139,124,246,0.14)", color: C.violet, border: "rgba(139,124,246,0.35)" },
  };
  const s = tones[tone];
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontFamily: FONT_MONO, fontSize: 11, padding: "3px 8px",
      borderRadius: 999, background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>
      {children}
    </span>
  );
}

function Button({ children, onClick, variant = "primary", full, icon: Icon, disabled }) {
  const variants = {
    primary: { background: C.amber, color: "#1A1204", border: "none" },
    ghost: { background: "transparent", color: C.text, border: `1px solid ${C.border}` },
    violet: { background: C.violet, color: "#120E30", border: "none" },
  };
  const s = variants[variant];
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        ...s,
        width: full ? "100%" : undefined,
        display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
        fontFamily: FONT_UI, fontWeight: 600, fontSize: 14,
        padding: "11px 16px", borderRadius: 12, cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.5 : 1, transition: "transform .12s ease, opacity .12s ease",
      }}
      className="dashia-btn"
    >
      {Icon && <Icon size={16} strokeWidth={2.25} />}
      {children}
    </button>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontFamily: FONT_UI, fontSize: 13, fontWeight: 600, color: C.textDim,
      marginBottom: 10, letterSpacing: 0.1,
    }}>
      {children}
    </div>
  );
}

/* Avatar real de DASHIA, con anillo animado cuando "habla" */
function AvatarOrb({ size = 88, speaking = false }) {
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      {speaking && (
        <div style={{
          position: "absolute", inset: -6, borderRadius: "50%",
          border: `2px solid ${C.violet}`, opacity: 0.5,
          animation: "dashiaPulse 1.6s ease-out infinite",
        }} />
      )}
      <img
        src={AVATAR_IMG}
        alt="DASHIA"
        style={{
          width: size, height: size, borderRadius: "50%", objectFit: "cover",
          boxShadow: `0 0 0 1px ${C.border}, 0 8px 24px rgba(139,124,246,0.25)`,
          display: "block",
        }}
      />
    </div>
  );
}

/* Tarjeta del video de bienvenida (miniatura real; el .mp4 completo
   se comparte aparte en el chat — no cabe incrustado en un artifact) */
function VideoIntroCard({ lang, t }) {
  const [toast, setToast] = useState(false);
  const thumb = INTRO_THUMB[lang] || INTRO_THUMB.es;

  function handleClick() {
    setToast(true);
    setTimeout(() => setToast(false), 2200);
  }

  return (
    <div style={{ position: "relative" }}>
      <div
        onClick={handleClick}
        style={{
          position: "relative", width: 168, height: 94, borderRadius: 12, overflow: "hidden",
          border: `1px solid ${C.border}`, cursor: "pointer",
        }}
      >
        <img src={thumb.img} alt="DASHIA intro" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
        <div style={{
          position: "absolute", inset: 0, background: "rgba(10,13,20,0.28)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: "50%", background: "rgba(10,13,20,0.55)",
            border: `1px solid rgba(255,255,255,0.4)`, display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Play size={13} color="#fff" fill="#fff" style={{ marginLeft: 1 }} />
          </div>
        </div>
        <span style={{
          position: "absolute", right: 6, bottom: 5, fontFamily: FONT_MONO, fontSize: 9.5,
          color: "#fff", background: "rgba(10,13,20,0.65)", borderRadius: 5, padding: "1px 5px",
        }}>
          {thumb.duration}
        </span>
      </div>
      {toast && (
        <div style={{
          position: "absolute", top: -34, left: 0, right: 0, textAlign: "center",
          fontFamily: FONT_UI, fontSize: 10.5, color: C.textDim, background: C.panelRaised,
          border: `1px solid ${C.border}`, borderRadius: 8, padding: "5px 8px", whiteSpace: "nowrap",
        }}>
          {lang === "es" ? "Video completo adjunto en el chat" : "Full video attached in chat"}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   TOP BAR
   ============================================================ */
function TopBar({ t, lang, setLang, conn }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "14px 18px 10px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{
          width: 22, height: 22, borderRadius: 6, background: C.amber,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <TrendingUp size={13} color="#1A1204" strokeWidth={2.5} />
        </div>
        <span style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 15, color: C.text, letterSpacing: 0.2 }}>
          {t.appName}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div title={conn.cex ? t.connected : t.notConnected}
             style={{ width: 7, height: 7, borderRadius: "50%", background: conn.cex ? C.up : C.textFaint }} />
        <div title={conn.wallet ? t.connected : t.notConnected}
             style={{ width: 7, height: 7, borderRadius: "50%", background: conn.wallet ? C.up : C.textFaint }} />
        <div style={{
          display: "flex", background: C.panelRaised, borderRadius: 999,
          border: `1px solid ${C.border}`, padding: 2,
        }}>
          {["es", "en"].map((l) => (
            <button key={l} onClick={() => setLang(l)} style={{
              border: "none", cursor: "pointer", padding: "3px 9px", borderRadius: 999,
              fontFamily: FONT_MONO, fontSize: 11, fontWeight: 600,
              background: lang === l ? C.amber : "transparent",
              color: lang === l ? "#1A1204" : C.textDim,
            }}>
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   PHANTOM — conexión real vía window.phantom.solana (no un mock)
   Nota: esto es el patrón estándar de conexión web/desktop. Solo
   funciona si la extensión de Phantom está instalada en el navegador
   donde se ve este prototipo. La app nativa iOS/Android usará el
   protocolo de deep link de Phantom en su lugar, que es distinto y
   queda pendiente de construir aparte.
   ============================================================ */
function getPhantomProvider() {
  if (typeof window === "undefined") return null;
  const provider = window?.phantom?.solana;
  return provider?.isPhantom ? provider : null;
}

function truncateAddress(addr) {
  return addr ? `${addr.slice(0, 4)}…${addr.slice(-4)}` : "";
}

function usePhantom() {
  const [available, setAvailable] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [publicKey, setPublicKey] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const provider = getPhantomProvider();
    setAvailable(!!provider);
    if (!provider) return;

    const onConnect = (pk) => { setPublicKey(pk.toString()); setError(null); };
    const onDisconnect = () => setPublicKey(null);
    provider.on?.("connect", onConnect);
    provider.on?.("disconnect", onDisconnect);

    // Reconexión silenciosa si el usuario ya autorizó este sitio antes
    provider.connect?.({ onlyIfTrusted: true })
      .then((resp) => setPublicKey(resp.publicKey.toString()))
      .catch(() => {});

    return () => {
      provider.removeListener?.("connect", onConnect);
      provider.removeListener?.("disconnect", onDisconnect);
    };
  }, []);

  async function connect() {
    const provider = getPhantomProvider();
    if (!provider) { setError("not-detected"); return; }
    setConnecting(true);
    setError(null);
    try {
      const resp = await provider.connect(); // abre el popup REAL de Phantom
      setPublicKey(resp.publicKey.toString());
    } catch (e) {
      setError(e?.message?.includes("reject") ? "rejected" : (e?.message || "error"));
    } finally {
      setConnecting(false);
    }
  }

  async function disconnect() {
    const provider = getPhantomProvider();
    try { await provider?.disconnect(); } catch (e) { /* noop */ }
    setPublicKey(null);
  }

  return { available, connecting, publicKey, error, connect, disconnect };
}

/* Wallet operativa de ejemplo — en producción la genera el backend
   (ver solana_connector/wallet.py) y es distinta por usuario/agente. */
const EXAMPLE_OPERATIONAL_WALLET = "7xKXtg2CW3xkT7ZUyv3RnUfZBFxQNqQmYLZjXvj9pump";

function PhantomPanel({ t, phantom }) {
  const [copied, setCopied] = useState("");

  function copy(text, key) {
    try { navigator.clipboard.writeText(text); } catch (e) { /* noop */ }
    setCopied(key);
    setTimeout(() => setCopied(""), 1500);
  }

  if (phantom.publicKey) {
    return (
      <Card style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.up }} />
            <span style={{ fontFamily: FONT_MONO, fontSize: 13, color: C.text }}>
              {truncateAddress(phantom.publicKey)}
            </span>
          </div>
          <button onClick={() => copy(phantom.publicKey, "main")} style={{
            background: "transparent", border: "none", color: C.textDim, cursor: "pointer",
            fontFamily: FONT_UI, fontSize: 11,
          }}>
            {copied === "main" ? t.copied : t.copyAddress}
          </button>
        </div>

        <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 12 }}>
          <div style={{ fontFamily: FONT_UI, fontSize: 12, fontWeight: 600, color: C.text }}>
            {t.operationalWallet}
          </div>
          <div style={{ fontFamily: FONT_UI, fontSize: 11, color: C.textDim, marginTop: 3, lineHeight: 1.4 }}>
            {t.operationalWalletDesc}
          </div>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            background: C.panelRaised, borderRadius: 9, padding: "7px 10px", marginTop: 8,
          }}>
            <span style={{ fontFamily: FONT_MONO, fontSize: 11.5, color: C.violet }}>
              {truncateAddress(EXAMPLE_OPERATIONAL_WALLET)}
            </span>
            <button onClick={() => copy(EXAMPLE_OPERATIONAL_WALLET, "op")} style={{
              background: "transparent", border: "none", color: C.textDim, cursor: "pointer",
              fontFamily: FONT_UI, fontSize: 11,
            }}>
              {copied === "op" ? t.copied : t.copyAddress}
            </button>
          </div>
        </div>

        <Button variant="ghost" onClick={phantom.disconnect}>{t.disconnect}</Button>
      </Card>
    );
  }

  return (
    <Card style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {phantom.available ? (
        <>
          <Button icon={Wallet} full onClick={phantom.connect} disabled={phantom.connecting}>
            {phantom.connecting ? t.connecting : t.connectWallet}
          </Button>
          {phantom.error && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontFamily: FONT_UI, fontSize: 11, color: C.down }}>
                {phantom.error === "rejected" ? t.phantomRejected : phantom.error}
              </span>
              <button onClick={phantom.connect} style={{
                background: "transparent", border: "none", color: C.violet, cursor: "pointer",
                fontFamily: FONT_UI, fontSize: 11, fontWeight: 600,
              }}>
                {t.tryAgain}
              </button>
            </div>
          )}
        </>
      ) : (
        <>
          <div style={{ fontFamily: FONT_UI, fontSize: 12, color: C.textDim }}>{t.phantomNotDetected}</div>
          <Button variant="ghost" icon={Wallet} full
                  onClick={() => window.open("https://phantom.app/download", "_blank")}>
            {t.installPhantom}
          </Button>
        </>
      )}
      <div style={{ fontFamily: FONT_UI, fontSize: 10, color: C.textFaint, lineHeight: 1.4 }}>
        {t.mobileNote}
      </div>
    </Card>
  );
}

/* ============================================================
   BÓVEDA DE EXCHANGES — formulario real + window.storage
   (equivalente en el navegador a credentials_vault del backend Python;
   ver nota honesta sobre las diferencias en el propio componente)
   ============================================================ */
const EXCHANGE_INFO = {
  binance: {
    name: "Binance", accent: C.amber, autoVerify: true,
    checklist: {
      es: ["Habilitar \"Spot & Margin Trading\" y/o \"Futures\"", "NO habilitar \"Enable Withdrawals\"", "Activar whitelist de IP"],
      en: ['Enable "Spot & Margin Trading" and/or "Futures"', 'Do NOT enable "Enable Withdrawals"', "Turn on IP whitelist"],
    },
  },
  bybit: {
    name: "Bybit", accent: "#F7A600", autoVerify: true,
    checklist: {
      es: ["Marcar \"Contract Trade\" y/o \"Spot Trade\"", "NO marcar \"Withdrawal\"", "Activar whitelist de IP"],
      en: ['Check "Contract Trade" and/or "Spot Trade"', 'Do NOT check "Withdrawal"', "Turn on IP whitelist"],
    },
  },
  weex: {
    name: "Weex", accent: C.violet, autoVerify: false,
    checklist: { es: [], en: [] },
  },
};

function useExchangeConnections() {
  const [connections, setConnections] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const result = await window.storage.get("exchange_connections", false);
        setConnections(result ? JSON.parse(result.value) : []);
      } catch (e) {
        setConnections([]);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  async function persist(next) {
    setConnections(next);
    try {
      await window.storage.set("exchange_connections", JSON.stringify(next), false);
    } catch (e) { /* si falla el guardado persistente, se queda en memoria igual */ }
  }

  async function addConnection(conn) {
    await persist([...connections.filter((c) => c.exchange !== conn.exchange), conn]);
  }

  async function removeConnection(exchange) {
    await persist(connections.filter((c) => c.exchange !== exchange));
  }

  return { connections, loaded, addConnection, removeConnection };
}

function maskKey(key) {
  return key.length > 4 ? key.slice(-4) : key;
}

function ExchangeConnectFlow({ t, lang, exchanges, onClose }) {
  const [step, setStep] = useState("select");   // select | form | verifying | result
  const [selected, setSelected] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [testnet, setTestnet] = useState(true);
  const [weexAck, setWeexAck] = useState(false);
  const [error, setError] = useState("");
  const [resultOk, setResultOk] = useState(true);

  function pickExchange(id) {
    setSelected(id);
    setApiKey(""); setApiSecret(""); setWeexAck(false); setError("");
    setStep("form");
  }

  async function submit() {
    if (!apiKey.trim() || !apiSecret.trim()) { setError(t.fillRequired); return; }
    const info = EXCHANGE_INFO[selected];
    if (!info.autoVerify && !weexAck) { setError(t.weexManualLabel); return; }

    setStep("verifying");
    // Simulado: acá es donde, con el backend real desplegado, se llamaría a
    // credentials_vault.connect_and_verify(). No hay backend vivo todavía —
    // ver aviso en pantalla y en la respuesta del chat.
    await new Promise((r) => setTimeout(r, 1200));

    const verified = info.autoVerify ? true : weexAck;
    await exchanges.addConnection({
      exchange: selected, maskedKey: maskKey(apiKey.trim()), testnet,
      verified, connectedAt: new Date().toISOString(),
    });
    setApiKey(""); setApiSecret("");  // el secreto nunca se guarda, ni "cifrado falso" en el cliente
    setResultOk(true);
    setStep("result");
  }

  const info = selected ? EXCHANGE_INFO[selected] : null;

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(5,6,10,0.7)", zIndex: 50,
      display: "flex", alignItems: "flex-end", justifyContent: "center",
    }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: "100%", maxWidth: 390, maxHeight: "88%", overflowY: "auto",
        background: C.panel, borderTopLeftRadius: 24, borderTopRightRadius: 24,
        border: `1px solid ${C.border}`, borderBottom: "none", padding: 20,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          {step === "form" ? (
            <button onClick={() => setStep("select")} style={{ background: "none", border: "none", color: C.textDim, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
              <ChevronLeft size={16} /> {t.backButton}
            </button>
          ) : <span />}
          <button onClick={onClose} style={{ background: "none", border: "none", color: C.textDim, cursor: "pointer" }}>
            <X size={18} />
          </button>
        </div>

        {step === "select" && (
          <>
            <SectionLabel>{t.selectExchange}</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {Object.entries(EXCHANGE_INFO).map(([id, ex]) => {
                const already = exchanges.connections.find((c) => c.exchange === id);
                return (
                  <button key={id} onClick={() => pickExchange(id)} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    background: C.panelRaised, border: `1px solid ${C.border}`, borderRadius: 12,
                    padding: "12px 14px", cursor: "pointer", textAlign: "left",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: ex.accent }} />
                      <span style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 13.5, color: C.text }}>{ex.name}</span>
                    </div>
                    {already ? <Pill tone={already.verified ? "up" : "amber"}>{already.verified ? t.verifiedBadge : t.connectFailedTitle}</Pill>
                              : <span style={{ color: C.textFaint, fontSize: 12 }}>＋</span>}
                  </button>
                );
              })}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-start", marginTop: 16, padding: 10, background: "rgba(232,163,61,0.08)", border: `1px solid rgba(232,163,61,0.3)`, borderRadius: 10 }}>
              <AlertTriangle size={14} color={C.amber} style={{ flexShrink: 0, marginTop: 1 }} />
              <span style={{ fontFamily: FONT_UI, fontSize: 10.5, color: C.textDim, lineHeight: 1.4 }}>{t.demoWarning}</span>
            </div>
          </>
        )}

        {step === "form" && info && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: info.accent }} />
              <span style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 15, color: C.text }}>{info.name}</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div>
                <div style={{ fontFamily: FONT_UI, fontSize: 11, color: C.textDim, marginBottom: 4 }}>{t.apiKeyLabel}</div>
                <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} style={inputStyle} spellCheck={false} />
              </div>
              <div>
                <div style={{ fontFamily: FONT_UI, fontSize: 11, color: C.textDim, marginBottom: 4 }}>{t.apiSecretLabel}</div>
                <div style={{ position: "relative" }}>
                  <input type={showSecret ? "text" : "password"} value={apiSecret}
                         onChange={(e) => setApiSecret(e.target.value)}
                         style={{ ...inputStyle, paddingRight: 36 }} spellCheck={false} />
                  <button onClick={() => setShowSecret((s) => !s)} style={{
                    position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                    background: "none", border: "none", color: C.textFaint, cursor: "pointer",
                  }}>
                    {showSecret ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", marginTop: 4 }}>
                <input type="checkbox" checked={testnet} onChange={(e) => setTestnet(e.target.checked)} />
                <span style={{ fontFamily: FONT_UI, fontSize: 12, color: C.textDim }}>{t.testnetLabel}</span>
              </label>

              {info.autoVerify ? (
                <div style={{ background: C.panelRaised, borderRadius: 10, padding: 12, marginTop: 4 }}>
                  <div style={{ fontFamily: FONT_UI, fontSize: 11, fontWeight: 600, color: C.textDim, marginBottom: 6 }}>{t.checklistTitle}</div>
                  {info.checklist[lang].map((item, i) => (
                    <div key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start", marginBottom: 4 }}>
                      <CheckCircle2 size={13} color={C.up} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span style={{ fontFamily: FONT_UI, fontSize: 11.5, color: C.text }}>{item}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <label style={{
                  display: "flex", gap: 8, alignItems: "flex-start", cursor: "pointer", marginTop: 4,
                  background: "rgba(139,124,246,0.08)", border: `1px solid rgba(139,124,246,0.3)`, borderRadius: 10, padding: 12,
                }}>
                  <input type="checkbox" checked={weexAck} onChange={(e) => setWeexAck(e.target.checked)} style={{ marginTop: 2 }} />
                  <span style={{ fontFamily: FONT_UI, fontSize: 11.5, color: C.text, lineHeight: 1.4 }}>{t.weexManualLabel}</span>
                </label>
              )}

              {error && <div style={{ fontFamily: FONT_UI, fontSize: 11.5, color: C.down }}>{error}</div>}

              <Button full onClick={submit}>{t.connectButton}</Button>
            </div>
          </>
        )}

        {step === "verifying" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 0" }}>
            <Loader2 size={28} color={C.violet} className="dashia-spin" />
            <span style={{ fontFamily: FONT_UI, fontSize: 13, color: C.textDim, marginTop: 12 }}>{t.verifying}</span>
          </div>
        )}

        {step === "result" && info && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "24px 0", gap: 10 }}>
            <CheckCircle2 size={36} color={C.up} />
            <span style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 15, color: C.text }}>{info.name} — {t.verifiedBadge}</span>
            <Button variant="ghost" onClick={onClose}>{t.cancelButton}</Button>
          </div>
        )}
      </div>
    </div>
  );
}

function ConnectedExchangesPanel({ t, lang, exchanges }) {
  const [flowOpen, setFlowOpen] = useState(false);
  return (
    <div>
      {exchanges.connections.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 10 }}>
          {exchanges.connections.map((c) => {
            const info = EXCHANGE_INFO[c.exchange];
            return (
              <Card key={c.exchange} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: info.accent }} />
                  <div>
                    <div style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 12.5, color: C.text }}>{info.name}</div>
                    <div style={{ fontFamily: FONT_MONO, fontSize: 10, color: C.textFaint }}>{t.endsIn} ••{c.maskedKey}</div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Pill tone={c.testnet ? "neutral" : "amber"}>{c.testnet ? t.testnetBadge : t.liveBadge}</Pill>
                  <Pill tone={c.verified ? "up" : "neutral"}>{c.verified ? t.verifiedBadge : t.noAutoVerify}</Pill>
                  <button onClick={() => exchanges.removeConnection(c.exchange)} style={{ background: "none", border: "none", color: C.textFaint, cursor: "pointer" }}>
                    <X size={14} />
                  </button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
      <Button variant="ghost" icon={Link2} full onClick={() => setFlowOpen(true)}>
        {exchanges.connections.length > 0 ? t.addAnother : t.connectCex}
      </Button>
      {flowOpen && <ExchangeConnectFlow t={t} lang={lang} exchanges={exchanges} onClose={() => setFlowOpen(false)} />}
    </div>
  );
}

/* ============================================================
   DASHBOARD
   ============================================================ */
function DashboardScreen({ t, lang, conn, agents, market, phantom, exchanges }) {
  return (
    <div style={{ padding: "4px 18px 18px", display: "flex", flexDirection: "column", gap: 18 }}>
      <Card style={{ background: `linear-gradient(155deg, ${C.panelRaised}, ${C.panel})` }}>
        <div style={{ fontFamily: FONT_MONO, fontSize: 12, color: C.textDim }}>{t.equity}</div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 32, fontWeight: 600, color: C.text, marginTop: 4 }}>
          $12,450.30
        </div>
        <div style={{ marginTop: 6 }}><Pill tone="up">▲ 2.34% (24h)</Pill></div>
      </Card>

      <ConnectedExchangesPanel t={t} lang={lang} exchanges={exchanges} />

      <PhantomPanel t={t} phantom={phantom} />

      <div>
        <SectionLabel>{t.liveMarket}</SectionLabel>
        <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4 }}>
          {market.map((m) => (
            <div key={m.sym} style={{
              minWidth: 92, background: C.panel, border: `1px solid ${C.border}`,
              borderRadius: 12, padding: "10px 12px", flexShrink: 0,
            }}>
              <div style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 12, color: C.text }}>{m.sym}</div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 12.5, color: C.textDim, marginTop: 3 }}>
                {m.price >= 100 ? m.price.toLocaleString(undefined, { maximumFractionDigits: 0 }) : m.price}
              </div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 11, color: m.chg >= 0 ? C.up : C.down, marginTop: 2 }}>
                {m.chg >= 0 ? "▲" : "▼"} {Math.abs(m.chg).toFixed(2)}%
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <SectionLabel>{t.myAgents}</SectionLabel>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {agents.map((a) => (
            <Card key={a.id} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              {a.builtIn ? <AvatarOrb size={40} /> : (
                <div style={{
                  width: 40, height: 40, borderRadius: "50%", background: C.panelRaised,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Cpu size={17} color={C.textDim} />
                </div>
              )}
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 14, color: C.text }}>{a.name}</span>
                  <Pill tone={a.active ? "up" : "neutral"}>{a.active ? t.active : t.paused}</Pill>
                </div>
                <div style={{ fontFamily: FONT_MONO, fontSize: 11.5, color: C.textDim, marginTop: 3 }}>
                  {a.venue} · {a.trades} {t.trades} · {a.winRate}% {t.winRate}
                </div>
              </div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 600, color: a.pnlPct >= 0 ? C.up : C.down }}>
                {a.pnlPct >= 0 ? "+" : ""}{a.pnlPct}%
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   DASHIA (chat + control del agente)
   ============================================================ */
function DashiaScreen({ t, lang, active, setActive, risk, setRisk }) {
  const [messages, setMessages] = useState(lang === "es" ? CHAT_SEED_ES : CHAT_SEED_EN);
  const [input, setInput] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { setMessages(lang === "es" ? CHAT_SEED_ES : CHAT_SEED_EN); }, [lang]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  function send() {
    if (!input.trim()) return;
    const userMsg = { from: "user", text: input.trim() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setSpeaking(true);
    setTimeout(() => {
      const reply = lang === "es"
        ? "Anotado. En la app real esto llega a mi motor (distancia Lorentziana + kernel) y te respondo con la señal actual sobre el activo que me indiques."
        : "Got it. In the real app this reaches my engine (Lorentzian distance + kernel) and I reply with the current signal for whichever asset you point me to.";
      setMessages((m) => [...m, { from: "dashia", text: reply }]);
      setSpeaking(false);
    }, 900);
  }

  return (
    <div style={{ padding: "4px 18px 18px", display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "10px 0 14px" }}>
        <AvatarOrb size={84} speaking={speaking} />
        <div style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 18, color: C.text, marginTop: 10 }}>DASHIA</div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 11, color: C.violet, marginTop: 2 }}>{t.dashiaTag}</div>
        <div style={{ fontFamily: FONT_UI, fontSize: 12.5, color: C.textDim, textAlign: "center", marginTop: 8, maxWidth: 260 }}>
          {t.dashiaDesc}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <VideoIntroCard lang={lang} t={t} />
        </div>
      </div>

      <Card style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: FONT_UI, fontSize: 12.5, color: C.textDim }}>{t.riskPlan}</span>
          <select value={risk} onChange={(e) => setRisk(e.target.value)} style={{
            background: C.panelRaised, color: C.text, border: `1px solid ${C.border}`,
            borderRadius: 8, fontFamily: FONT_MONO, fontSize: 12, padding: "4px 8px",
          }}>
            {["COOK", "WALK", "HAWK", "ALLIN"].map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <Button variant={active ? "ghost" : "violet"} onClick={() => setActive((a) => !a)}>
          {active ? t.deactivateAgent : t.activateAgent}
        </Button>
      </Card>

      <div style={{
        flex: 1, minHeight: 220, background: C.panel, border: `1px solid ${C.border}`,
        borderRadius: 16, padding: 14, display: "flex", flexDirection: "column", gap: 10, overflowY: "auto",
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.from === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "80%", padding: "9px 12px", borderRadius: 14,
              fontFamily: FONT_UI, fontSize: 13, lineHeight: 1.4,
              background: m.from === "user" ? C.amberDim : C.panelRaised,
              color: m.from === "user" ? "#1A1204" : C.text,
              borderTopRightRadius: m.from === "user" ? 4 : 14,
              borderTopLeftRadius: m.from === "user" ? 14 : 4,
            }}>
              {m.text}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button onClick={() => setListening((l) => !l)} style={{
          width: 42, height: 42, borderRadius: 12, border: `1px solid ${listening ? C.violet : C.border}`,
          background: listening ? "rgba(139,124,246,0.15)" : C.panel, color: listening ? C.violet : C.textDim,
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, cursor: "pointer",
        }}>
          <Mic size={17} />
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={listening ? t.listening : t.chatPlaceholder}
          style={{
            flex: 1, background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12,
            padding: "0 14px", color: C.text, fontFamily: FONT_UI, fontSize: 13, outline: "none",
          }}
        />
        <button onClick={send} style={{
          width: 42, height: 42, borderRadius: 12, border: "none", background: C.amber,
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, cursor: "pointer",
        }}>
          <Send size={16} color="#1A1204" />
        </button>
      </div>
    </div>
  );
}

/* ============================================================
   AGENTES (crear agente propio)
   ============================================================ */
/* ============================================================
   CONSTRUCTOR VISUAL DE AGENTES — compila al MISMO DSL que valida
   agent_sandbox/dsl_interpreter.py (whitelist sobre AST, sin eval/exec).
   Lo que se arma acá con clics es texto plano; la seguridad real sigue
   viviendo del lado del backend, esto solo evita tener que escribirlo
   a mano.
   ============================================================ */
const INDICATOR_DEFS = [
  { id: "rsi", labelKey: "indRsi", needsPeriod: true, kind: "number" },
  { id: "sma", labelKey: "indSma", needsPeriod: true, kind: "number" },
  { id: "ema", labelKey: "indEma", needsPeriod: true, kind: "number" },
  { id: "price", labelKey: "indPrice", needsPeriod: false, kind: "number" },
  { id: "volume", labelKey: "indVolume", needsPeriod: false, kind: "number" },
  { id: "trend", labelKey: "indTrend", needsPeriod: false, kind: "string", values: ["up", "down", "flat"] },
  { id: "position", labelKey: "indPosition", needsPeriod: false, kind: "string", values: ["none", "long", "short"] },
];

function describeCategoricalValue(indicatorId, value, lang) {
  const dict = {
    trend: { up: { es: "Alcista", en: "Up" }, down: { es: "Bajista", en: "Down" }, flat: { es: "Lateral", en: "Flat" } },
    position: { none: { es: "Sin posición", en: "No position" }, long: { es: "Long", en: "Long" }, short: { es: "Short", en: "Short" } },
  };
  return dict[indicatorId]?.[value]?.[lang] || value;
}

let __uidCounter = 0;
function uid() { return `id-${Date.now()}-${__uidCounter++}`; }

function newCondition() {
  return {
    id: uid(), leftIndicator: "rsi", leftPeriod: 14, operator: "<",
    rightMode: "number", rightNumber: 30, rightIndicator: "sma", rightPeriod: 50,
    rightCategorical: "up",
  };
}
function newRule() {
  return { id: uid(), conditions: [newCondition()], logic: "and", action: { type: "buy", size: "default" } };
}

const RULE_TEMPLATES = {
  oversold: () => [
    { id: uid(), logic: "and", action: { type: "buy", size: "default" },
      conditions: [{ id: uid(), leftIndicator: "rsi", leftPeriod: 14, operator: "<",
                     rightMode: "number", rightNumber: 30, rightIndicator: "sma", rightPeriod: 50, rightCategorical: "up" }] },
    { id: uid(), logic: "and", action: { type: "sell", size: "default" },
      conditions: [{ id: uid(), leftIndicator: "rsi", leftPeriod: 14, operator: ">",
                     rightMode: "number", rightNumber: 70, rightIndicator: "sma", rightPeriod: 50, rightCategorical: "up" }] },
  ],
};

// Compila las reglas al DSL real — misma gramática que valida dsl_interpreter.py
function operandText(indicatorId, period) {
  const def = INDICATOR_DEFS.find((d) => d.id === indicatorId);
  if (!def) return indicatorId;
  return def.needsPeriod ? `${indicatorId}(${period})` : `${indicatorId}()`;
}
function conditionText(cond) {
  const leftDef = INDICATOR_DEFS.find((d) => d.id === cond.leftIndicator);
  const left = operandText(cond.leftIndicator, cond.leftPeriod);
  let right;
  if (leftDef && leftDef.kind === "string") right = `"${cond.rightCategorical}"`;
  else if (cond.rightMode === "indicator") right = operandText(cond.rightIndicator, cond.rightPeriod);
  else right = String(cond.rightNumber);
  return `${left} ${cond.operator} ${right}`;
}
function ruleText(rule) {
  const condsText = rule.conditions.map(conditionText).join(` ${rule.logic} `);
  const action = rule.action.type === "hold" ? "hold()" : `${rule.action.type}(size=risk.${rule.action.size})`;
  return `if ${condsText}:\n    ${action}`;
}
function compileRulesToDSL(rules) {
  if (!rules.length) return "// Agrega al menos una regla para generar el código";
  return rules.map(ruleText).join("\n\n");
}

const miniSelectStyle = {
  background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8,
  padding: "6px 8px", color: C.text, fontFamily: FONT_UI, fontSize: 11.5, outline: "none",
};
const iconBtnStyle = {
  background: "transparent", border: `1px solid ${C.border}`, borderRadius: 7,
  width: 26, height: 26, display: "flex", alignItems: "center", justifyContent: "center",
  color: C.textFaint, cursor: "pointer", flexShrink: 0,
};
const ghostSmallBtn = {
  background: "transparent", border: `1px solid ${C.border}`, borderRadius: 8,
  padding: "6px 10px", color: C.textDim, fontFamily: FONT_UI, fontSize: 11, cursor: "pointer",
};
function microToggleStyle(active) {
  return {
    border: "none", borderRadius: 6, padding: "4px 8px", cursor: "pointer",
    background: active ? C.violet : "transparent", color: active ? "#120E30" : C.textFaint,
    fontFamily: FONT_MONO, fontSize: 11, fontWeight: 700,
  };
}

function ConditionRow({ cond, onChange, onRemove, lang, t }) {
  const leftDef = INDICATOR_DEFS.find((d) => d.id === cond.leftIndicator);
  const isCategorical = leftDef.kind === "string";
  const ops = isCategorical ? ["==", "!="] : ["<", ">", "<=", ">=", "==", "!="];

  return (
    <div style={{ background: C.bg, border: `1px solid ${C.borderSoft}`, borderRadius: 10, padding: 8, display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <select value={cond.leftIndicator} onChange={(e) => {
          const newDef = INDICATOR_DEFS.find((d) => d.id === e.target.value);
          onChange({
            leftIndicator: e.target.value,
            rightMode: newDef.kind === "string" ? "categorical" : "number",
            rightCategorical: newDef.kind === "string" ? newDef.values[0] : cond.rightCategorical,
            operator: newDef.kind === "string" ? "==" : cond.operator,
          });
        }} style={{ ...miniSelectStyle, flex: leftDef.needsPeriod ? 2 : 1 }}>
          {INDICATOR_DEFS.map((d) => <option key={d.id} value={d.id}>{t[d.labelKey]}</option>)}
        </select>
        {leftDef.needsPeriod && (
          <input type="number" min="1" value={cond.leftPeriod}
                 onChange={(e) => onChange({ leftPeriod: Math.max(1, parseInt(e.target.value) || 1) })}
                 style={{ ...miniSelectStyle, width: 52, textAlign: "center" }} />
        )}
        <button onClick={onRemove} style={iconBtnStyle}><Trash2 size={13} /></button>
      </div>

      <select value={cond.operator} onChange={(e) => onChange({ operator: e.target.value })} style={miniSelectStyle}>
        {ops.map((op) => <option key={op} value={op}>{op}</option>)}
      </select>

      {isCategorical ? (
        <select value={cond.rightCategorical} onChange={(e) => onChange({ rightCategorical: e.target.value })} style={miniSelectStyle}>
          {leftDef.values.map((v) => <option key={v} value={v}>{describeCategoricalValue(leftDef.id, v, lang)}</option>)}
        </select>
      ) : (
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <div style={{ display: "flex", background: C.panel, borderRadius: 8, padding: 2, flexShrink: 0 }}>
            <button onClick={() => onChange({ rightMode: "number" })} style={microToggleStyle(cond.rightMode === "number")}>#</button>
            <button onClick={() => onChange({ rightMode: "indicator" })} style={microToggleStyle(cond.rightMode === "indicator")}>~</button>
          </div>
          {cond.rightMode === "number" ? (
            <input type="number" value={cond.rightNumber}
                   onChange={(e) => onChange({ rightNumber: parseFloat(e.target.value) || 0 })}
                   style={{ ...miniSelectStyle, flex: 1 }} />
          ) : (
            <>
              <select value={cond.rightIndicator} onChange={(e) => onChange({ rightIndicator: e.target.value })} style={{ ...miniSelectStyle, flex: 2 }}>
                {INDICATOR_DEFS.filter((d) => d.kind === "number").map((d) => <option key={d.id} value={d.id}>{t[d.labelKey]}</option>)}
              </select>
              {INDICATOR_DEFS.find((d) => d.id === cond.rightIndicator)?.needsPeriod && (
                <input type="number" min="1" value={cond.rightPeriod}
                       onChange={(e) => onChange({ rightPeriod: Math.max(1, parseInt(e.target.value) || 1) })}
                       style={{ ...miniSelectStyle, width: 52 }} />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function RuleCard({ rule, index, total, t, lang, onUpdate, onRemove, onMove, dragHandlers }) {
  function updateCondition(condId, patch) {
    onUpdate({ ...rule, conditions: rule.conditions.map((c) => (c.id === condId ? { ...c, ...patch } : c)) });
  }
  function addCondition() {
    onUpdate({ ...rule, conditions: [...rule.conditions, newCondition()] });
  }
  function removeCondition(condId) {
    onUpdate({ ...rule, conditions: rule.conditions.filter((c) => c.id !== condId) });
  }

  return (
    <div
      draggable
      onDragStart={dragHandlers.onDragStart}
      onDragOver={dragHandlers.onDragOver}
      onDrop={dragHandlers.onDrop}
      onDragEnd={dragHandlers.onDragEnd}
      style={{
        background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, padding: 12,
        opacity: dragHandlers.isDragging ? 0.4 : 1, transition: "opacity .15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, cursor: "grab" }}>
          <GripVertical size={14} color={C.textFaint} />
          <span style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 12.5, color: C.text }}>{t.rule} {index + 1}</span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <button onClick={() => onMove(-1)} disabled={index === 0} style={{ ...iconBtnStyle, opacity: index === 0 ? 0.3 : 1 }}><ArrowUp size={13} /></button>
          <button onClick={() => onMove(1)} disabled={index === total - 1} style={{ ...iconBtnStyle, opacity: index === total - 1 ? 0.3 : 1 }}><ArrowDown size={13} /></button>
          <button onClick={onRemove} style={iconBtnStyle}><Trash2 size={13} /></button>
        </div>
      </div>

      <div style={{ fontFamily: FONT_MONO, fontSize: 9.5, color: C.textFaint, marginBottom: 6, letterSpacing: 0.5 }}>{t.when}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {rule.conditions.map((cond) => (
          <ConditionRow key={cond.id} cond={cond} lang={lang} t={t}
                        onChange={(patch) => updateCondition(cond.id, patch)}
                        onRemove={() => removeCondition(cond.id)} />
        ))}
      </div>

      {rule.conditions.length > 1 && (
        <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
          <button onClick={() => onUpdate({ ...rule, logic: "and" })} style={toggleStyle(rule.logic === "and")}>{t.logicAnd}</button>
          <button onClick={() => onUpdate({ ...rule, logic: "or" })} style={toggleStyle(rule.logic === "or")}>{t.logicOr}</button>
        </div>
      )}

      <button onClick={addCondition} style={{ ...ghostSmallBtn, marginTop: 8 }}>+ {t.addCondition}</button>

      <div style={{ fontFamily: FONT_MONO, fontSize: 9.5, color: C.textFaint, margin: "12px 0 6px", letterSpacing: 0.5 }}>{t.then}</div>
      <div style={{ display: "flex", gap: 6 }}>
        <select value={rule.action.type} onChange={(e) => onUpdate({ ...rule, action: { ...rule.action, type: e.target.value } })} style={{ ...miniSelectStyle, flex: 1 }}>
          <option value="buy">{t.actionBuy}</option>
          <option value="sell">{t.actionSell}</option>
          <option value="hold">{t.actionHold}</option>
        </select>
        {rule.action.type !== "hold" && (
          <select value={rule.action.size} onChange={(e) => onUpdate({ ...rule, action: { ...rule.action, size: e.target.value } })} style={{ ...miniSelectStyle, flex: 1 }}>
            <option value="small">{t.sizeSmall}</option>
            <option value="default">{t.sizeDefault}</option>
            <option value="large">{t.sizeLarge}</option>
          </select>
        )}
      </div>
    </div>
  );
}

function VisualAgentBuilder({ rules, setRules, t, lang }) {
  const [dragIndex, setDragIndex] = useState(null);
  const [overIndex, setOverIndex] = useState(null);

  function updateRule(id, updated) { setRules(rules.map((r) => (r.id === id ? updated : r))); }
  function removeRule(id) { setRules(rules.filter((r) => r.id !== id)); }
  function moveRule(index, dir) {
    const target = index + dir;
    if (target < 0 || target >= rules.length) return;
    const next = [...rules];
    [next[index], next[target]] = [next[target], next[index]];
    setRules(next);
  }
  function addRule() { setRules([...rules, newRule()]); }
  function applyTemplate(key) { setRules(RULE_TEMPLATES[key]()); }

  function handleDrop() {
    if (dragIndex === null || overIndex === null || dragIndex === overIndex) {
      setDragIndex(null); setOverIndex(null); return;
    }
    const next = [...rules];
    const [moved] = next.splice(dragIndex, 1);
    next.splice(overIndex, 0, moved);
    setRules(next);
    setDragIndex(null); setOverIndex(null);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {rules.length === 0 && (
        <div style={{ border: `1px dashed ${C.border}`, borderRadius: 10, padding: 16, textAlign: "center" }}>
          <div style={{ fontFamily: FONT_UI, fontSize: 12, color: C.textFaint, marginBottom: 10 }}>{t.noRulesYet}</div>
          <button onClick={() => applyTemplate("oversold")} style={ghostSmallBtn}>{t.templateOversold}</button>
        </div>
      )}

      {rules.map((rule, i) => (
        <RuleCard
          key={rule.id} rule={rule} index={i} total={rules.length} t={t} lang={lang}
          onUpdate={(updated) => updateRule(rule.id, updated)}
          onRemove={() => removeRule(rule.id)}
          onMove={(dir) => moveRule(i, dir)}
          dragHandlers={{
            isDragging: dragIndex === i,
            onDragStart: () => setDragIndex(i),
            onDragOver: (e) => { e.preventDefault(); setOverIndex(i); },
            onDrop: handleDrop,
            onDragEnd: () => { setDragIndex(null); setOverIndex(null); },
          }}
        />
      ))}

      {rules.length > 0 && (
        <div style={{ fontFamily: FONT_UI, fontSize: 10, color: C.textFaint, textAlign: "center" }}>{t.ruleOrderNote}</div>
      )}

      <Button variant="ghost" icon={Plus} full onClick={addRule}>{t.addRule}</Button>

      <div>
        <div style={{ fontFamily: FONT_UI, fontSize: 11, color: C.textDim, marginBottom: 6 }}>{t.codePreview}</div>
        <pre style={{
          background: C.panelRaised, border: `1px solid ${C.border}`, borderRadius: 10, padding: 10,
          fontFamily: FONT_MONO, fontSize: 10.5, color: C.violet, overflowX: "auto", margin: 0, whiteSpace: "pre",
        }}>
          {compileRulesToDSL(rules)}
        </pre>
      </div>
    </div>
  );
}

const CODE_PLACEHOLDER = `// Ejemplo simplificado — tu lógica va aquí
if rsi(14) < 30 and trend == "up":
    buy(size = risk.default)

if rsi(14) > 70:
    sell()
`;

function AgentsScreen({ t, lang, agents, setAgents }) {
  const [mode, setMode] = useState("code");
  const [name, setName] = useState("");
  const [asset, setAsset] = useState("BTC");
  const [venue, setVenue] = useState("Binance (CEX)");
  const [code, setCode] = useState(CODE_PLACEHOLDER);
  const [rules, setRules] = useState([]);

  const customAgents = agents.filter((a) => !a.builtIn);

  function save() {
    if (!name.trim()) return;
    const strategyCode = mode === "visual" ? compileRulesToDSL(rules) : code;
    setAgents((prev) => [...prev, {
      id: `custom-${Date.now()}`, name: name.trim(), builtIn: false, active: false,
      pnlPct: 0, trades: 0, winRate: 0, venue, risk: "COOK", strategyCode,
    }]);
    setName("");
  }

  return (
    <div style={{ padding: "4px 18px 18px", display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <SectionLabel>{t.yourAgents}</SectionLabel>
        {customAgents.length === 0 ? (
          <Card style={{ color: C.textFaint, fontFamily: FONT_UI, fontSize: 12.5 }}>{t.noCustomAgents}</Card>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {customAgents.map((a) => (
              <Card key={a.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontFamily: FONT_UI, fontWeight: 700, fontSize: 13, color: C.text }}>{a.name}</span>
                <Pill>{a.venue}</Pill>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Card>
        <SectionLabel>{t.newAgent}</SectionLabel>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t.agentName} style={inputStyle} />

          <div style={{ display: "flex", gap: 10 }}>
            <select value={asset} onChange={(e) => setAsset(e.target.value)} style={{ ...inputStyle, flex: 1 }}>
              {["BTC", "ETH", "SOL", "LTC", "XRP", "ARB", "XAU", "Memecoin"].map((a) => <option key={a}>{a}</option>)}
            </select>
            <select value={venue} onChange={(e) => setVenue(e.target.value)} style={{ ...inputStyle, flex: 1 }}>
              {["Binance (CEX)", "Bybit (CEX)", "Weex (CEX)", "Jupiter (DEX)", "Raydium (DEX)"].map((v) => <option key={v}>{v}</option>)}
            </select>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => setMode("code")} style={toggleStyle(mode === "code")}>{t.codeMode}</button>
            <button onClick={() => setMode("visual")} style={toggleStyle(mode === "visual")}>{t.visualMode}</button>
          </div>

          {mode === "code" ? (
            <textarea
              value={code} onChange={(e) => setCode(e.target.value)} spellCheck={false}
              style={{
                ...inputStyle, fontFamily: FONT_MONO, fontSize: 12, height: 130, resize: "vertical",
                lineHeight: 1.5, whiteSpace: "pre",
              }}
            />
          ) : (
            <VisualAgentBuilder rules={rules} setRules={setRules} t={t} lang={lang} />
          )}

          <Button icon={Plus} full onClick={save}>{t.saveAgent}</Button>
        </div>
      </Card>

      <Card style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
        <Trophy size={17} color={C.amber} style={{ flexShrink: 0, marginTop: 1 }} />
        <div style={{ fontFamily: FONT_UI, fontSize: 12, color: C.textDim }}>{t.competitionSoon}</div>
      </Card>
    </div>
  );
}

const inputStyle = {
  background: C.panelRaised, border: `1px solid ${C.border}`, borderRadius: 10,
  padding: "9px 12px", color: C.text, fontFamily: FONT_UI, fontSize: 13, outline: "none", width: "100%",
  boxSizing: "border-box",
};
function toggleStyle(activeState) {
  return {
    flex: 1, padding: "8px 0", borderRadius: 9, border: `1px solid ${activeState ? C.violet : C.border}`,
    background: activeState ? "rgba(139,124,246,0.14)" : "transparent",
    color: activeState ? C.violet : C.textDim, fontFamily: FONT_UI, fontSize: 12.5, fontWeight: 600,
    cursor: "pointer",
  };
}

/* ============================================================
   BACKTESTING
   ============================================================ */
function genCurve(seed) {
  let v = 10000, x = seed;
  const rand = () => { x = (x * 9301 + 49297) % 233280; return x / 233280; };
  const out = [{ i: 0, equity: v }];
  for (let i = 1; i <= 40; i++) {
    v = v * (1 + (rand() - 0.46) * 0.035);
    out.push({ i, equity: Math.round(v) });
  }
  return out;
}

function BacktestScreen({ t }) {
  const [asset, setAsset] = useState("BTC");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  function run() {
    setRunning(true);
    setResult(null);
    setTimeout(() => {
      const curve = genCurve(asset.length * 17 + 3);
      const final = curve[curve.length - 1].equity;
      const peak = Math.max(...curve.map((c) => c.equity));
      const trough = Math.min(...curve.map((c) => c.equity));
      setResult({
        curve, final,
        totalReturn: (((final / 10000) - 1) * 100).toFixed(2),
        maxDD: (((trough - peak) / peak) * 100).toFixed(2),
      });
      setRunning(false);
    }, 900);
  }

  return (
    <div style={{ padding: "4px 18px 18px", display: "flex", flexDirection: "column", gap: 16 }}>
      <Card>
        <SectionLabel>{t.backtestOn} DASHIA</SectionLabel>
        <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
          <select value={asset} onChange={(e) => setAsset(e.target.value)} style={{ ...inputStyle, flex: 1 }}>
            {["BTC", "ETH", "SOL", "LTC", "XRP", "ARB", "XAU"].map((a) => <option key={a}>{a}</option>)}
          </select>
          <select style={{ ...inputStyle, flex: 1 }} defaultValue="90d">
            <option value="30d">30d</option><option value="90d">90d</option><option value="1y">1y</option>
          </select>
        </div>
        <Button icon={Play} full onClick={run} disabled={running}>{running ? t.running : t.runBacktest}</Button>
      </Card>

      {result && (
        <>
          <Card>
            <div style={{ height: 170 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={result.curve} margin={{ top: 6, right: 6, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={C.amber} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={C.amber} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={C.borderSoft} vertical={false} />
                  <XAxis dataKey="i" hide />
                  <YAxis tick={{ fill: C.textFaint, fontSize: 10, fontFamily: FONT_MONO }} width={46}
                         domain={["dataMin - 200", "dataMax + 200"]} />
                  <Tooltip contentStyle={{ background: C.panelRaised, border: `1px solid ${C.border}`, borderRadius: 8, fontFamily: FONT_MONO, fontSize: 11 }} />
                  <Area type="monotone" dataKey="equity" stroke={C.amber} strokeWidth={2} fill="url(#eqFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 10, color: C.textFaint, marginTop: 6, textAlign: "center" }}>
              {t.simulatedData}
            </div>
          </Card>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <StatBox label={t.finalCapital} value={`$${result.final.toLocaleString()}`} />
            <StatBox label={t.totalReturn} value={`${result.totalReturn}%`} tone={result.totalReturn >= 0 ? "up" : "down"} />
            <StatBox label={t.initialCapital} value="$10,000" />
            <StatBox label={t.maxDrawdown} value={`${result.maxDD}%`} tone="down" />
          </div>
        </>
      )}
    </div>
  );
}

function StatBox({ label, value, tone }) {
  const color = tone === "up" ? C.up : tone === "down" ? C.down : C.text;
  return (
    <Card>
      <div style={{ fontFamily: FONT_MONO, fontSize: 10.5, color: C.textDim }}>{label}</div>
      <div style={{ fontFamily: FONT_MONO, fontSize: 18, fontWeight: 600, color, marginTop: 4 }}>{value}</div>
    </Card>
  );
}

/* ============================================================
   STATS / HISTORIAL
   ============================================================ */
function StatsScreen({ t }) {
  const totalPnl = TRADE_HISTORY.reduce((s, tr) => s + tr.pnl, 0);
  const wins = TRADE_HISTORY.filter((tr) => tr.pnl > 0).length;

  return (
    <div style={{ padding: "4px 18px 18px", display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <StatBox label={t.totalReturn} value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(0)}`} tone={totalPnl >= 0 ? "up" : "down"} />
        <StatBox label={t.winRate} value={`${((wins / TRADE_HISTORY.length) * 100).toFixed(0)}%`} />
      </div>

      <Card>
        <SectionLabel>{t.pnlOverTime}</SectionLabel>
        <div style={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={PNL_CURVE} margin={{ top: 4, right: 6, left: -22, bottom: 0 }}>
              <CartesianGrid stroke={C.borderSoft} vertical={false} />
              <XAxis dataKey="date" tick={{ fill: C.textFaint, fontSize: 9, fontFamily: FONT_MONO }} />
              <YAxis tick={{ fill: C.textFaint, fontSize: 9, fontFamily: FONT_MONO }} width={42} />
              <Tooltip contentStyle={{ background: C.panelRaised, border: `1px solid ${C.border}`, borderRadius: 8, fontFamily: FONT_MONO, fontSize: 11 }} />
              <Line type="monotone" dataKey="pnl" stroke={C.violet} strokeWidth={2} dot={{ r: 2.5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div>
        <SectionLabel>{t.historyTitle}</SectionLabel>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {TRADE_HISTORY.slice().reverse().map((tr) => (
            <Card key={tr.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: 12 }}>
              <div>
                <div style={{ fontFamily: FONT_UI, fontWeight: 600, fontSize: 12.5, color: C.text }}>
                  {tr.asset} <span style={{ color: C.textFaint, fontWeight: 400 }}>· {tr.agent}</span>
                </div>
                <div style={{ fontFamily: FONT_MONO, fontSize: 10.5, color: C.textFaint, marginTop: 2 }}>{tr.date}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Pill tone={tr.side === "long" ? "up" : "down"}>{tr.side === "long" ? t.long : t.short}</Pill>
                <span style={{
                  fontFamily: FONT_MONO, fontSize: 13, fontWeight: 600, minWidth: 58, textAlign: "right",
                  color: tr.pnl >= 0 ? C.up : C.down,
                }}>
                  {tr.pnl >= 0 ? "+" : ""}{tr.pnl.toFixed(1)}
                </span>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   TAB BAR
   ============================================================ */
function TabBar({ t, tab, setTab }) {
  const items = [
    { id: "dash", label: t.tabs.dash, icon: Home },
    { id: "dashia", label: t.tabs.dashia, icon: Sparkles },
    { id: "agents", label: t.tabs.agents, icon: Cpu },
    { id: "backtest", label: t.tabs.backtest, icon: TrendingUp },
    { id: "stats", label: t.tabs.stats, icon: BarChart3 },
  ];
  return (
    <div style={{
      display: "flex", borderTop: `1px solid ${C.border}`, background: C.bg,
      padding: "8px 6px calc(env(safe-area-inset-bottom, 8px))",
    }}>
      {items.map((it) => {
        const isActive = tab === it.id;
        const Icon = it.icon;
        return (
          <button key={it.id} onClick={() => setTab(it.id)} style={{
            flex: 1, background: "transparent", border: "none", cursor: "pointer",
            display: "flex", flexDirection: "column", alignItems: "center", gap: 3, padding: "4px 0",
          }}>
            <Icon size={19} strokeWidth={isActive ? 2.4 : 1.8} color={isActive ? C.amber : C.textFaint} />
            <span style={{
              fontFamily: FONT_UI, fontSize: 9.5, fontWeight: isActive ? 700 : 500,
              color: isActive ? C.text : C.textFaint,
            }}>
              {it.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ============================================================
   ROOT APP
   ============================================================ */
export default function App() {
  const [lang, setLang] = useState("es");
  const t = useMemo(() => STR[lang], [lang]);
  const [tab, setTab] = useState("dash");
  const exchanges = useExchangeConnections();
  const phantom = usePhantom();
  const conn = { cex: exchanges.connections.some((c) => c.verified), wallet: phantom.publicKey };
  const [agents, setAgents] = useState(AGENTS_SEED);
  const [dashiaActive, setDashiaActive] = useState(true);
  const [risk, setRisk] = useState("WALK");
  const [market, setMarket] = useState(MARKET_SEED);

  useEffect(() => {
    setAgents((prev) => prev.map((a) => a.id === "dashia" ? { ...a, active: dashiaActive } : a));
  }, [dashiaActive]);

  useEffect(() => {
    const id = setInterval(() => {
      setMarket((prev) => prev.map((m) => ({
        ...m,
        price: +(m.price * (1 + (Math.random() - 0.5) * 0.004)).toFixed(m.price < 10 ? 3 : 1),
        chg: +(m.chg + (Math.random() - 0.5) * 0.15).toFixed(2),
      })));
    }, 2400);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{
      minHeight: "100vh", background: "#05060A", display: "flex",
      alignItems: "center", justifyContent: "center", padding: 20, boxSizing: "border-box",
    }}>
      <style>{`
        * { box-sizing: border-box; }
        .dashia-btn:active { transform: scale(0.97); }
        .dashia-btn:focus-visible { outline: 2px solid ${C.violet}; outline-offset: 2px; }
        input:focus, select:focus, textarea:focus { border-color: ${C.violet} !important; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 4px; }
        @keyframes dashiaPulse { 0% { transform: scale(0.9); opacity: 0.55; } 100% { transform: scale(1.35); opacity: 0; } }
        @keyframes dashiaSpin { to { transform: rotate(360deg); } }
        .dashia-spin { animation: dashiaSpin 0.9s linear infinite; }
      `}</style>

      <div style={{
        width: 390, height: 780, maxHeight: "92vh", background: C.bg,
        borderRadius: 36, border: `8px solid #000`, boxShadow: "0 30px 80px rgba(0,0,0,0.6)",
        display: "flex", flexDirection: "column", overflow: "hidden", position: "relative",
        fontFamily: FONT_UI,
      }}>
        <TopBar t={t} lang={lang} setLang={setLang} conn={conn} />

        {(conn.cex || conn.wallet) && (
          <div style={{ display: "flex", gap: 6, padding: "0 18px 8px", flexWrap: "wrap" }}>
            {conn.cex && <Pill tone="up"><ShieldCheck size={11} />&nbsp;{t.noWithdraw}</Pill>}
            {conn.wallet && <Pill tone="violet"><Lock size={11} />&nbsp;{truncateAddress(conn.wallet)}</Pill>}
          </div>
        )}

        <div style={{ flex: 1, overflowY: "auto" }}>
          {tab === "dash" && <DashboardScreen t={t} lang={lang} conn={conn} agents={agents} market={market} phantom={phantom} exchanges={exchanges} />}
          {tab === "dashia" && <DashiaScreen t={t} lang={lang} active={dashiaActive} setActive={setDashiaActive} risk={risk} setRisk={setRisk} />}
          {tab === "agents" && <AgentsScreen t={t} lang={lang} agents={agents} setAgents={setAgents} />}
          {tab === "backtest" && <BacktestScreen t={t} />}
          {tab === "stats" && <StatsScreen t={t} />}
        </div>

        <TabBar t={t} tab={tab} setTab={setTab} />
      </div>
    </div>
  );
}
