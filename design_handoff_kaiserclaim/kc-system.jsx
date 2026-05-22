// kc-system.jsx — KaiserClaim Design System
// Tokens, icons, and shared UI components

const { useState, useEffect, useRef, useCallback, useMemo, createContext, useContext, forwardRef } = React;

// ═══════════════════════════════════════════════════════════════
// THEME TOKENS
// ═══════════════════════════════════════════════════════════════

const KC = {
  color: {
    bg: '#F8F7F4', surface: '#FFFFFF', surfaceAlt: '#F2F1EE',
    border: '#E5E3DE', borderLight: '#EEEDEA',
    text: '#1A1F36', textSec: '#6B7280', textTri: '#9CA3AF', textInv: '#FFFFFF',
    brand: '#1A1F36', accent: '#0D9488', accentHover: '#0F766E',
    accentLight: '#F0FDFA', accentMid: '#CCFBF1',
    danger: '#DC2626', dangerBg: '#FEF2F2',
    // dark mode
    darkBg: '#111318', darkSurface: '#1A1D25', darkSurfaceAlt: '#22252E',
    darkBorder: '#2E313A', darkText: '#E8E9EC', darkTextSec: '#9CA3AF',
  },
  status: {
    empfangen:     { label: 'Empfangen',             c: '#6B7280', bg: '#F3F4F6' },
    ocr:           { label: 'OCR-Verarbeitung',      c: '#A16207', bg: '#FEF9C3' },
    bereit_oegk:   { label: 'Bereit für ÖGK',       c: '#2563EB', bg: '#DBEAFE' },
    bei_oegk:      { label: 'Bei ÖGK eingereicht',  c: '#1D4ED8', bg: '#DBEAFE' },
    von_oegk:      { label: 'Von ÖGK erstattet',    c: '#4338CA', bg: '#E0E7FF' },
    bereit_merkur: { label: 'Bereit für Merkur',     c: '#C2410C', bg: '#FFEDD5' },
    bei_merkur:    { label: 'Bei Merkur eingereicht', c: '#6D28D9', bg: '#EDE9FE' },
    abgeschlossen: { label: 'Abgeschlossen',         c: '#15803D', bg: '#DCFCE7' },
  },
  r: { sm: 8, md: 12, lg: 16, xl: 20, pill: 100 },
  shadow: {
    sm: '0 1px 3px rgba(0,0,0,0.04)',
    md: '0 2px 8px rgba(0,0,0,0.06)',
    lg: '0 4px 16px rgba(0,0,0,0.08)',
    card: '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02)',
  },
};

// Standard/pharmacy pipeline steps
const PIPELINE_STANDARD = [
  'empfangen','ocr','bereit_oegk','bei_oegk','von_oegk','bereit_merkur','bei_merkur','abgeschlossen'
];
const PIPELINE_PHARMACY = [
  'empfangen','ocr','bereit_merkur','bei_merkur','abgeschlossen'
];

// ═══════════════════════════════════════════════════════════════
// DARK MODE CONTEXT
// ═══════════════════════════════════════════════════════════════

const ThemeCtx = createContext({ dark: false, accent: '#0D9488' });
function useTheme() {
  const ctx = useContext(ThemeCtx);
  return { ...ctx, accent: ctx.accent || KC.color.accent };
}
function c(light, dark) {
  const { dark: isDark } = useTheme();
  return isDark ? dark : light;
}

// ═══════════════════════════════════════════════════════════════
// ICONS (stroke-based, 24×24 viewBox)
// ═══════════════════════════════════════════════════════════════

function KCIcon({ name, size = 24, color = 'currentColor', fill = false, style = {} }) {
  const s = { width: size, height: size, flexShrink: 0, display: 'block', ...style };
  const p = { fill: 'none', stroke: color, strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' };
  const paths = {
    home: fill
      ? <><path d="M3 10.5L12 3l9 7.5" {...p}/><path d="M5 9.5V19a1 1 0 001 1h3.5v-4.5a1.5 1.5 0 011.5-1.5h2a1.5 1.5 0 011.5 1.5V20H18a1 1 0 001-1V9.5" {...p}/></>
      : <><path d="M3 10.5L12 3l9 7.5" {...p}/><path d="M5 9.5V19a1 1 0 001 1h3.5v-4.5a1.5 1.5 0 011.5-1.5h2a1.5 1.5 0 011.5 1.5V20H18a1 1 0 001-1V9.5" {...p}/></>,
    receipt: <><rect x="5" y="2" width="14" height="20" rx="1" {...p}/><path d="M9 7h6M9 11h6M9 15h3" {...p}/></>,
    barChart: <><rect x="3" y="12" width="4" height="9" rx="1" {...p}/><rect x="10" y="7" width="4" height="14" rx="1" {...p}/><rect x="17" y="3" width="4" height="18" rx="1" {...p}/></>,
    plus: <path d="M12 5v14M5 12h14" {...p}/>,
    settings: <><circle cx="12" cy="12" r="3" {...p}/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" {...p}/></>,
    camera: <><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" {...p}/><circle cx="12" cy="13" r="4" {...p}/></>,
    upload: <><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" {...p}/><polyline points="17 8 12 3 7 8" {...p}/><line x1="12" y1="3" x2="12" y2="15" {...p}/></>,
    x: <path d="M18 6L6 18M6 6l12 12" {...p}/>,
    check: <polyline points="20 6 9 17 4 12" {...p}/>,
    checkCircle: <><path d="M22 11.08V12a10 10 0 11-5.93-9.14" {...p}/><polyline points="22 4 12 14.01 9 11.01" {...p}/></>,
    chevronRight: <polyline points="9 18 15 12 9 6" {...p}/>,
    chevronDown: <polyline points="6 9 12 15 18 9" {...p}/>,
    arrowLeft: <><line x1="19" y1="12" x2="5" y2="12" {...p}/><polyline points="12 19 5 12 12 5" {...p}/></>,
    search: <><circle cx="11" cy="11" r="8" {...p}/><line x1="21" y1="21" x2="16.65" y2="16.65" {...p}/></>,
    clock: <><circle cx="12" cy="12" r="10" {...p}/><polyline points="12 6 12 12 16 14" {...p}/></>,
    send: <><line x1="22" y1="2" x2="11" y2="13" {...p}/><polygon points="22 2 15 22 11 13 2 9 22 2" {...p}/></>,
    scan: <><path d="M3 7V5a2 2 0 012-2h2M17 3h2a2 2 0 012 2v2M21 17v2a2 2 0 01-2 2h-2M7 21H5a2 2 0 01-2-2v-2" {...p}/><line x1="7" y1="12" x2="17" y2="12" {...p}/></>,
    inbox: <><polyline points="22 12 16 12 14 15 10 15 8 12 2 12" {...p}/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z" {...p}/></>,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" {...p}/>,
    lock: <><rect x="3" y="11" width="18" height="11" rx="2" {...p}/><path d="M7 11V7a5 5 0 0110 0v4" {...p}/></>,
    user: <><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" {...p}/><circle cx="12" cy="7" r="4" {...p}/></>,
    globe: <><circle cx="12" cy="12" r="10" {...p}/><line x1="2" y1="12" x2="22" y2="12" {...p}/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" {...p}/></>,
    logout: <><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" {...p}/><polyline points="16 17 21 12 16 7" {...p}/><line x1="21" y1="12" x2="9" y2="12" {...p}/></>,
    eye: <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" {...p}/><circle cx="12" cy="12" r="3" {...p}/></>,
    eyeOff: <><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" {...p}/><line x1="1" y1="1" x2="23" y2="23" {...p}/></>,
    file: <><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" {...p}/><polyline points="14 2 14 8 20 8" {...p}/></>,
    alertCircle: <><circle cx="12" cy="12" r="10" {...p}/><line x1="12" y1="8" x2="12" y2="12" {...p}/><line x1="12" y1="16" x2="12.01" y2="16" {...p}/></>,
    mail: <><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" {...p}/><polyline points="22 6 12 13 2 6" {...p}/></>,
    loader: <><line x1="12" y1="2" x2="12" y2="6" {...p} opacity=".4"/><line x1="12" y1="18" x2="12" y2="22" {...p}/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76" {...p} opacity=".5"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07" {...p} opacity=".9"/><line x1="2" y1="12" x2="6" y2="12" {...p} opacity=".6"/><line x1="18" y1="12" x2="22" y2="12" {...p} opacity=".8"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24" {...p} opacity=".7"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93" {...p} opacity=".3"/></>,
    trending: <><polyline points="23 6 13.5 15.5 8.5 10.5 1 18" {...p}/><polyline points="17 6 23 6 23 12" {...p}/></>,
    creditCard: <><rect x="1" y="4" width="22" height="16" rx="2" {...p}/><line x1="1" y1="10" x2="23" y2="10" {...p}/></>,
    edit: <><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" {...p}/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" {...p}/></>,
    filter: <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" {...p}/>,
    bell: <><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" {...p}/><path d="M13.73 21a2 2 0 01-3.46 0" {...p}/></>,
  };
  return <svg viewBox="0 0 24 24" style={s}>{paths[name] || null}</svg>;
}

// ═══════════════════════════════════════════════════════════════
// SHARED COMPONENTS
// ═══════════════════════════════════════════════════════════════

// --- Status Pill ---
function KCStatusPill({ status, size = 'sm' }) {
  const st = KC.status[status];
  if (!st) return null;
  const isSm = size === 'sm';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: isSm ? '3px 8px' : '4px 10px',
      borderRadius: KC.r.pill,
      background: st.bg, color: st.c,
      fontSize: isSm ? 11 : 12, fontWeight: 600, lineHeight: 1,
      whiteSpace: 'nowrap', letterSpacing: '0.01em',
    }}>
      {st.label}
    </span>
  );
}

// --- Money Display ---
function KCMoney({ amount, size = 'hero', showSign = false, color, animated = false }) {
  const { dark } = useTheme();
  const [displayed, setDisplayed] = useState(animated ? 0 : amount);
  useEffect(() => {
    if (!animated) { setDisplayed(amount); return; }
    let frame;
    const start = performance.now();
    const duration = 1200;
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      setDisplayed(amount * ease);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [amount, animated]);
  
  const formatted = displayed.toLocaleString('de-AT', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
  const sizes = {
    hero: { fontSize: 44, fontWeight: 700, letterSpacing: '-0.02em' },
    lg: { fontSize: 28, fontWeight: 700, letterSpacing: '-0.01em' },
    md: { fontSize: 18, fontWeight: 600 },
    sm: { fontSize: 15, fontWeight: 600 },
  };
  const s = sizes[size] || sizes.md;
  return (
    <span style={{
      ...s, color: color || (dark ? KC.color.darkText : KC.color.text),
      fontVariantNumeric: 'tabular-nums',
      fontFamily: "'Plus Jakarta Sans', sans-serif",
    }}>
      {showSign && amount > 0 ? '+' : ''}€&thinsp;{formatted}
    </span>
  );
}

// --- Card ---
function KCCard({ children, style = {}, onClick, hover = false, padding = 20 }) {
  const { dark } = useTheme();
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => hover && setHovered(true)}
      onMouseLeave={() => hover && setHovered(false)}
      style={{
        background: dark ? KC.color.darkSurface : KC.color.surface,
        border: `1px solid ${dark ? KC.color.darkBorder : KC.color.border}`,
        borderRadius: KC.r.lg,
        padding,
        boxShadow: hovered ? KC.shadow.md : KC.shadow.card,
        transition: 'box-shadow 0.2s, transform 0.2s',
        transform: hovered ? 'translateY(-1px)' : 'none',
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
    >{children}</div>
  );
}

// --- Button ---
function KCButton({ children, variant = 'primary', size = 'md', icon, loading, disabled, onClick, style = {}, fullWidth }) {
  const [pressed, setPressed] = useState(false);
  const { dark } = useTheme();
  const variants = {
    primary: {
      bg: KC.color.accent, color: '#fff',
      hoverBg: KC.color.accentHover,
    },
    secondary: {
      bg: 'transparent', color: dark ? KC.color.accent : KC.color.accent,
      border: `1.5px solid ${dark ? KC.color.darkBorder : KC.color.border}`,
    },
    ghost: {
      bg: 'transparent', color: dark ? KC.color.darkTextSec : KC.color.textSec,
    },
    danger: {
      bg: KC.color.dangerBg, color: KC.color.danger,
    },
  };
  const v = variants[variant];
  const h = size === 'lg' ? 52 : size === 'sm' ? 36 : 44;
  const fs = size === 'lg' ? 16 : size === 'sm' ? 13 : 14;
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      onMouseLeave={() => setPressed(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        height: h, padding: '0 20px',
        background: v.bg, color: v.color,
        border: v.border || 'none',
        borderRadius: KC.r.md, fontSize: fs, fontWeight: 600,
        fontFamily: 'inherit', cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transform: pressed ? 'scale(0.97)' : 'scale(1)',
        transition: 'all 0.15s ease',
        width: fullWidth ? '100%' : 'auto',
        ...style,
      }}
    >
      {loading ? (
        <span style={{ animation: 'kcSpin 0.8s linear infinite', display: 'flex' }}>
          <KCIcon name="loader" size={18} color="currentColor"/>
        </span>
      ) : icon ? <KCIcon name={icon} size={18} color="currentColor"/> : null}
      {children}
    </button>
  );
}

// --- Input ---
function KCInput({ label, value, onChange, placeholder, type = 'text', icon, error, disabled, style = {} }) {
  const { dark } = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <div style={style}>
      {label && <label style={{
        display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 600,
        color: dark ? KC.color.darkTextSec : KC.color.textSec,
      }}>{label}</label>}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        height: 48, padding: '0 14px',
        background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
        border: `1.5px solid ${focused ? KC.color.accent : error ? KC.color.danger : 'transparent'}`,
        borderRadius: KC.r.md, transition: 'border-color 0.15s',
      }}>
        {icon && <KCIcon name={icon} size={18} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>}
        <input
          type={type} value={value} onChange={e => onChange(e.target.value)}
          placeholder={placeholder} disabled={disabled}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
          style={{
            flex: 1, border: 'none', background: 'none', outline: 'none',
            fontSize: 15, fontFamily: 'inherit',
            color: dark ? KC.color.darkText : KC.color.text,
          }}
        />
      </div>
      {error && <div style={{ marginTop: 4, fontSize: 12, color: KC.color.danger }}>{error}</div>}
    </div>
  );
}

// --- Select ---
function KCSelect({ label, value, onChange, options, placeholder, style = {} }) {
  const { dark } = useTheme();
  return (
    <div style={style}>
      {label && <label style={{
        display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 600,
        color: dark ? KC.color.darkTextSec : KC.color.textSec,
      }}>{label}</label>}
      <div style={{ position: 'relative' }}>
        <select
          value={value} onChange={e => onChange(e.target.value)}
          style={{
            width: '100%', height: 48, padding: '0 36px 0 14px',
            background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
            border: '1.5px solid transparent',
            borderRadius: KC.r.md, fontSize: 15, fontFamily: 'inherit',
            color: value ? (dark ? KC.color.darkText : KC.color.text) : (dark ? KC.color.darkTextSec : KC.color.textTri),
            appearance: 'none', outline: 'none', cursor: 'pointer',
          }}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <div style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
          <KCIcon name="chevronDown" size={16} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>
        </div>
      </div>
    </div>
  );
}

// --- Progress Bar (benefits) ---
function KCProgressBar({ used, limit, height = 8, showLabel = true, style = {} }) {
  const pct = Math.min((used / limit) * 100, 110);
  const color = pct >= 100 ? '#DC2626' : pct >= 75 ? '#F59E0B' : '#16A34A';
  const remaining = Math.max(limit - used, 0);
  const { dark } = useTheme();
  return (
    <div style={style}>
      <div style={{
        height, borderRadius: height, overflow: 'hidden',
        background: dark ? KC.color.darkSurfaceAlt : '#F0EFEC',
      }}>
        <div style={{
          width: `${Math.min(pct, 100)}%`, height: '100%',
          borderRadius: height, background: color,
          transition: 'width 0.6s ease',
        }}/>
      </div>
      {showLabel && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 12, fontWeight: 500 }}>
          <span style={{ color }}>€&thinsp;{remaining.toLocaleString('de-AT')} übrig</span>
          <span style={{ color: dark ? KC.color.darkTextSec : KC.color.textTri }}>
            €&thinsp;{used.toLocaleString('de-AT')} / €&thinsp;{limit.toLocaleString('de-AT')}
          </span>
        </div>
      )}
    </div>
  );
}

// --- Vertical Stepper ---
function KCStepper({ steps, currentStep, timestamps = {} }) {
  const { dark } = useTheme();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, padding: '4px 0' }}>
      {steps.map((stepKey, i) => {
        const st = KC.status[stepKey];
        const isComplete = i < currentStep;
        const isActive = i === currentStep;
        const isLast = i === steps.length - 1;
        return (
          <div key={stepKey} style={{ display: 'flex', gap: 14, minHeight: isLast ? 'auto' : 52 }}>
            {/* Line + dot column */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 28 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 14,
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                background: isComplete ? st.c : isActive ? st.bg : (dark ? KC.color.darkSurfaceAlt : '#F0EFEC'),
                border: isActive ? `2px solid ${st.c}` : 'none',
                boxShadow: isActive ? `0 0 0 4px ${st.c}22` : 'none',
                transition: 'all 0.3s ease',
              }}>
                {isComplete ? (
                  <KCIcon name="check" size={14} color="#fff"/>
                ) : (
                  <span style={{
                    fontSize: 11, fontWeight: 700,
                    color: isActive ? st.c : (dark ? KC.color.darkTextSec : KC.color.textTri),
                  }}>{i + 1}</span>
                )}
              </div>
              {!isLast && (
                <div style={{
                  width: 2, flex: 1, minHeight: 20,
                  background: isComplete ? st.c : (dark ? KC.color.darkBorder : '#E0DFDC'),
                  transition: 'background 0.3s ease',
                }}/>
              )}
            </div>
            {/* Label column */}
            <div style={{ paddingTop: 3, paddingBottom: isLast ? 0 : 12, flex: 1 }}>
              <div style={{
                fontSize: 14, fontWeight: isActive ? 600 : isComplete ? 500 : 400,
                color: isActive ? st.c : isComplete
                  ? (dark ? KC.color.darkText : KC.color.text)
                  : (dark ? KC.color.darkTextSec : KC.color.textTri),
                transition: 'color 0.3s',
              }}>{st.label}</div>
              {(isComplete || isActive) && timestamps[stepKey] && (
                <div style={{ fontSize: 12, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginTop: 2 }}>
                  {timestamps[stepKey]}
                </div>
              )}
              {isActive && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 6,
                  padding: '3px 8px', borderRadius: KC.r.pill,
                  background: st.bg, color: st.c, fontSize: 11, fontWeight: 600,
                }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: 3, background: st.c,
                    animation: 'kcPulse 1.5s ease infinite',
                  }}/>
                  Aktiv
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// --- Drop Zone ---
function KCDropZone({ onFile, preview, onClear }) {
  const { dark } = useTheme();
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);
  const handleDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) onFile(f);
  };
  const handleSelect = (e) => {
    const f = e.target.files?.[0];
    if (f) onFile(f);
  };
  if (preview) {
    return (
      <div style={{
        borderRadius: KC.r.lg, overflow: 'hidden', position: 'relative',
        border: `1px solid ${dark ? KC.color.darkBorder : KC.color.border}`,
      }}>
        <img src={preview} alt="" style={{ width: '100%', height: 220, objectFit: 'cover', display: 'block' }}/>
        <button onClick={onClear} style={{
          position: 'absolute', top: 10, right: 10,
          width: 32, height: 32, borderRadius: 16,
          background: 'rgba(0,0,0,0.6)', border: 'none',
          display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        }}>
          <KCIcon name="x" size={16} color="#fff"/>
        </button>
      </div>
    );
  }
  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      style={{
        borderRadius: KC.r.lg, padding: 40,
        border: `2px dashed ${dragOver ? KC.color.accent : (dark ? KC.color.darkBorder : KC.color.border)}`,
        background: dragOver ? KC.color.accentLight : (dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt),
        cursor: 'pointer', transition: 'all 0.2s',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
      }}
    >
      <input ref={inputRef} type="file" accept="image/*,.pdf" capture="environment" onChange={handleSelect}
        style={{ display: 'none' }}/>
      <div style={{
        width: 56, height: 56, borderRadius: 16,
        background: dark ? KC.color.darkBorder : KC.color.accentMid,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <KCIcon name="camera" size={28} color={KC.color.accent}/>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
          Foto aufnehmen oder Datei wählen
        </div>
        <div style={{ fontSize: 13, color: dark ? KC.color.darkTextSec : KC.color.textSec, marginTop: 4 }}>
          Beleg fotografieren oder PDF hochladen
        </div>
      </div>
    </div>
  );
}

// --- Empty State ---
function KCEmptyState({ icon = 'receipt', title, message }) {
  const { dark } = useTheme();
  return (
    <div style={{ textAlign: 'center', padding: '48px 24px' }}>
      <div style={{
        width: 64, height: 64, borderRadius: 20, margin: '0 auto 16px',
        background: dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <KCIcon name={icon} size={28} color={dark ? KC.color.darkTextSec : KC.color.textTri}/>
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>{title}</div>
      <div style={{ fontSize: 14, color: dark ? KC.color.darkTextSec : KC.color.textSec, marginTop: 6 }}>{message}</div>
    </div>
  );
}

// --- Top Bar ---
function KCTopBar({ title = 'KaiserClaim', onSettings, onBack, backLabel }) {
  const { dark } = useTheme();
  return (
    <div style={{
      height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 20px', background: dark ? KC.color.darkSurface : KC.color.surface,
      borderBottom: `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}`,
      position: 'sticky', top: 0, zIndex: 100,
    }}>
      {onBack ? (
        <button onClick={onBack} style={{
          display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none',
          cursor: 'pointer', fontSize: 14, fontWeight: 500, fontFamily: 'inherit',
          color: KC.color.accent, padding: 0,
        }}>
          <KCIcon name="arrowLeft" size={20} color={KC.color.accent}/>
          {backLabel || 'Zurück'}
        </button>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8, background: KC.color.accent,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <KCIcon name="shield" size={16} color="#fff"/>
          </div>
          <span style={{
            fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em',
            color: dark ? KC.color.darkText : KC.color.brand,
          }}>
            Kaiser<span style={{ fontWeight: 500 }}>Claim</span>
          </span>
        </div>
      )}
      <div style={{ fontSize: 15, fontWeight: 600, color: dark ? KC.color.darkText : KC.color.text }}>
        {onBack ? title : ''}
      </div>
      {onSettings ? (
        <button onClick={onSettings} style={{
          background: 'none', border: 'none', cursor: 'pointer', padding: 4,
          display: 'flex', alignItems: 'center',
        }}>
          <KCIcon name="settings" size={22} color={dark ? KC.color.darkTextSec : KC.color.textSec}/>
        </button>
      ) : <div style={{ width: 28 }}/>}
    </div>
  );
}

// --- Bottom Nav ---
function KCBottomNav({ activeTab, onTabChange, onUpload }) {
  const { dark } = useTheme();
  const tabs = [
    { id: 'home', label: 'Übersicht', icon: 'home' },
    { id: 'invoices', label: 'Belege', icon: 'receipt' },
    { id: 'upload', label: '', icon: 'plus', isAction: true },
    { id: 'benefits', label: 'Leistungen', icon: 'barChart' },
    { id: 'stats', label: 'Statistik', icon: 'trending' },
  ];
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', justifyContent: 'space-around',
      height: 64, paddingTop: 6, paddingBottom: 8,
      background: dark ? KC.color.darkSurface : KC.color.surface,
      borderTop: `1px solid ${dark ? KC.color.darkBorder : KC.color.borderLight}`,
      position: 'sticky', bottom: 0, zIndex: 100,
    }}>
      {tabs.map(tab => {
        if (tab.isAction) {
          return (
            <button key="upload" onClick={onUpload} style={{
              width: 48, height: 48, borderRadius: 14,
              background: KC.color.accent, border: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', marginTop: -12, boxShadow: `0 4px 12px ${KC.color.accent}44`,
              transition: 'transform 0.15s', position: 'relative',
            }}
            onMouseDown={e => e.currentTarget.style.transform = 'scale(0.92)'}
            onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}
            onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
            >
              <KCIcon name="plus" size={24} color="#fff"/>
            </button>
          );
        }
        const active = activeTab === tab.id;
        return (
          <button key={tab.id} onClick={() => onTabChange(tab.id)} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
            background: 'none', border: 'none', cursor: 'pointer', padding: '4px 12px',
            minWidth: 56,
          }}>
            <KCIcon name={tab.icon} size={22}
              color={active ? KC.color.accent : (dark ? KC.color.darkTextSec : KC.color.textTri)}
              fill={active}
            />
            <span style={{
              fontSize: 10, fontWeight: 600, letterSpacing: '0.02em',
              color: active ? KC.color.accent : (dark ? KC.color.darkTextSec : KC.color.textTri),
            }}>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// --- Page wrapper with slide animation ---
function KCPage({ children, style = {} }) {
  const { dark } = useTheme();
  const [visible, setVisible] = useState(false);
  useEffect(() => { requestAnimationFrame(() => setVisible(true)); }, []);
  return (
    <div style={{
      flex: 1, overflowY: 'auto', overflowX: 'hidden',
      background: dark ? KC.color.darkBg : KC.color.bg,
      padding: '0 0 24px',
      opacity: visible ? 1 : 0, transform: visible ? 'translateY(0)' : 'translateY(6px)',
      transition: 'opacity 0.35s ease, transform 0.35s ease',
      ...style,
    }}>{children}</div>
  );
}

// --- Section header ---
function KCSection({ title, action, onAction, style = {} }) {
  const { dark } = useTheme();
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 20px', marginBottom: 12, ...style,
    }}>
      <h2 style={{
        fontSize: 17, fontWeight: 700, margin: 0,
        color: dark ? KC.color.darkText : KC.color.text,
      }}>{title}</h2>
      {action && (
        <button onClick={onAction} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          fontSize: 13, fontWeight: 600, color: KC.color.accent,
          fontFamily: 'inherit', padding: 0,
        }}>{action}</button>
      )}
    </div>
  );
}

// --- Family Member Filter ---
function KCFamilyFilter({ members, selected, onChange, style = {} }) {
  const { dark } = useTheme();
  return (
    <div style={{
      display: 'flex', gap: 8, overflowX: 'auto',
      WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none',
      padding: '0 20px', ...style,
    }}>
      {members.map(m => {
        const active = selected === m.id;
        return (
          <button key={m.id} onClick={() => onChange(m.id)} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 12px', borderRadius: KC.r.pill,
            background: active ? (m.id === 'all' ? KC.color.accent : m.color) : (dark ? KC.color.darkSurfaceAlt : KC.color.surfaceAlt),
            color: active ? '#fff' : (dark ? KC.color.darkTextSec : KC.color.textSec),
            border: 'none', fontSize: 13, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'inherit',
            whiteSpace: 'nowrap', flexShrink: 0,
            transition: 'all 0.2s',
          }}>
            {m.id !== 'all' && (
              <div style={{
                width: 20, height: 20, borderRadius: 10,
                background: active ? 'rgba(255,255,255,0.3)' : m.color + '22',
                color: active ? '#fff' : m.color,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 9, fontWeight: 700, lineHeight: 1,
              }}>{m.initials}</div>
            )}
            {m.name}
          </button>
        );
      })}
    </div>
  );
}

// --- Stat Card ---
function KCStatCard({ label, children, icon, color, style = {} }) {
  const { dark } = useTheme();
  return (
    <div style={{
      flex: 1, padding: '14px 16px', borderRadius: KC.r.lg,
      background: dark ? KC.color.darkSurface : KC.color.surface,
      border: `1px solid ${dark ? KC.color.darkBorder : KC.color.border}`,
      ...style,
    }}>
      <div style={{ fontSize: 12, fontWeight: 500, color: dark ? KC.color.darkTextSec : KC.color.textTri, marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || (dark ? KC.color.darkText : KC.color.text) }}>
        {children}
      </div>
    </div>
  );
}

// --- Bar Chart ---
function KCBarChart({ data, height = 140, memberColors = {}, showLegend = false }) {
  const { dark } = useTheme();
  const maxVal = Math.max(...data.map(d => d.total || d.value || 0), 1);
  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'flex-end', gap: 6, height,
        padding: '0 4px',
      }}>
        {data.map((d, i) => {
          const barH = ((d.total || d.value || 0) / maxVal) * (height - 28);
          const segments = d.segments || [];
          const hasSegments = segments.length > 0;
          return (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div style={{
                width: '100%', height: height - 28, display: 'flex', flexDirection: 'column',
                justifyContent: 'flex-end', alignItems: 'center',
              }}>
                {hasSegments ? (
                  <div style={{ width: '100%', maxWidth: 36, borderRadius: 4, overflow: 'hidden', display: 'flex', flexDirection: 'column-reverse' }}>
                    {segments.map((seg, si) => {
                      const segH = (seg.value / maxVal) * (height - 28);
                      return <div key={si} style={{ height: Math.max(segH, segH > 0 ? 2 : 0), background: memberColors[seg.memberId] || KC.color.accent, transition: 'height 0.5s ease' }}/>;
                    })}
                  </div>
                ) : (
                  <div style={{
                    width: '100%', maxWidth: 36, height: Math.max(barH, 2),
                    borderRadius: 4, background: d.color || KC.color.accent,
                    transition: 'height 0.5s ease',
                  }}/>
                )}
              </div>
              <span style={{ fontSize: 10, fontWeight: 500, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>
                {d.label}
              </span>
            </div>
          );
        })}
      </div>
      {showLegend && Object.keys(memberColors).length > 0 && (
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 12, flexWrap: 'wrap' }}>
          {Object.entries(memberColors).map(([id, color]) => (
            <div key={id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: 4, background: color }}/>
              <span style={{ fontSize: 11, color: dark ? KC.color.darkTextSec : KC.color.textTri }}>{id}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Member Avatar ---
function KCAvatar({ name, initials, color, size = 36 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: size / 2,
      background: color + '18', color: color,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.33, fontWeight: 700, flexShrink: 0,
    }}>{initials}</div>
  );
}

// Export everything
Object.assign(window, {
  KC, PIPELINE_STANDARD, PIPELINE_PHARMACY, ThemeCtx, useTheme,
  KCIcon, KCStatusPill, KCMoney, KCCard, KCButton, KCInput, KCSelect,
  KCProgressBar, KCStepper, KCDropZone, KCEmptyState,
  KCTopBar, KCBottomNav, KCPage, KCSection,
  KCFamilyFilter, KCStatCard, KCBarChart, KCAvatar,
});
